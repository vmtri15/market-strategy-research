"""Local end-of-day paper account. No broker connectivity or real orders."""
from contextlib import contextmanager
import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'data/paper.db'
MODEL = ROOT / 'models/paper_model.pkl'
SYMBOLS = ['AAPL', 'MSFT', 'SPY']


@contextmanager
def connect(db=DB):
    conn = sqlite3.connect(db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), cash REAL, initial REAL, paused INTEGER, last_date TEXT, model_hash TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, shares REAL NOT NULL, mark REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, symbol TEXT, signal_date TEXT, side TEXT, confidence REAL, status TEXT, fill_date TEXT, quantity REAL, price REAL, fee REAL, reason TEXT, UNIQUE(symbol,signal_date));
    CREATE TABLE IF NOT EXISTS snapshots (date TEXT PRIMARY KEY, cash REAL, invested REAL, equity REAL);
    CREATE TABLE IF NOT EXISTS observed_bars (date TEXT, symbol TEXT, open REAL, close REAL, PRIMARY KEY(date,symbol));
    CREATE TABLE IF NOT EXISTS signals (date TEXT, symbol TEXT, signal INTEGER, confidence REAL, PRIMARY KEY(date,symbol));
    CREATE TABLE IF NOT EXISTS events (time TEXT, status TEXT, message TEXT);
    ''')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def log(conn, status, message):
    conn.execute('INSERT INTO events VALUES (?,?,?)',(datetime.now(timezone.utc).isoformat(),status,message))


def initialize(capital=10000., db=DB, source=None, model_path=MODEL):
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError('Starting balance must be positive')
    with connect(db) as c:
        if c.execute('SELECT 1 FROM account').fetchone():
            return
        source = Path(source or ROOT / 'models/model.pkl')
        shutil.copyfile(source,model_path)
        digest=hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
        c.execute('INSERT INTO account VALUES (1,?,?,1,NULL,?,?)',(capital,capital,digest,datetime.now(timezone.utc).isoformat()))
        c.executemany('INSERT INTO positions VALUES (?,0,0)',[(s,) for s in SYMBOLS])
        log(c,'initialized','Virtual account created paused; frozen model copied. No real orders.')


def set_paused(paused, db=DB):
    with connect(db) as c:
        c.execute('UPDATE account SET paused=? WHERE id=1',(int(paused),))
        if paused:
            c.execute("UPDATE orders SET status='cancelled', reason='Cancelled when account paused' WHERE status='pending'")
        log(c,'paused' if paused else 'resumed','Pending orders cancelled' if paused else 'Daily processing enabled')


def process_day(bars, signals, day, previous_session, db=DB):
    """One atomic, idempotent completed-session update using validated bars."""
    day=str(pd.Timestamp(day).date())
    with connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        account=c.execute('SELECT * FROM account').fetchone()
        if account is None:
            raise ValueError('Initialize the account first')
        if account['paused']:
            log(c,'skipped','Account paused'); return 'paused'
        if account['last_date'] and day <= account['last_date']:
            log(c,'skipped','Session already processed'); return 'duplicate'
        if set(bars)!=set(SYMBOLS) or set(signals)!=set(SYMBOLS):
            raise ValueError('Missing securities')
        for symbol in SYMBOLS:
            values=[bars[symbol]['open'],bars[symbol]['close']]
            signal,confidence=signals[symbol]
            if not all(np.isfinite(v) and v>0 for v in values) or signal not in [-1,0,1] or not np.isfinite(confidence) or not 0<=confidence<=1:
                raise ValueError('Invalid prices or signals')
        if account['last_date'] and account['last_date'] != str(pd.Timestamp(previous_session).date()) and c.execute("SELECT 1 FROM orders WHERE status='pending'").fetchone():
            c.execute('UPDATE account SET paused=1')
            c.execute("UPDATE orders SET status='cancelled',reason='Missed processing session' WHERE status='pending'")
            log(c,'error','Missed session; paused rather than backfilling trades. Review and resume.'); return 'gap'
        cash=account['cash']
        positions={r['symbol']:r['shares'] for r in c.execute('SELECT * FROM positions')}
        opening_equity=cash+sum(positions[s]*bars[s]['open'] for s in SYMBOLS)
        # Process sells before buys. Each new position gets at most 30% opening equity.
        orders=c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY CASE side WHEN 'Sell' THEN 0 ELSE 1 END,symbol").fetchall()
        for order in orders:
            symbol=order['symbol']; side=order['side']; quantity=0.; fill=bars[symbol]['open']*(1.0005 if side=='Buy' else .9995)
            if order['signal_date'] != str(pd.Timestamp(previous_session).date()):
                c.execute("UPDATE orders SET status='cancelled',reason='Signal expired' WHERE id=?",(order['id'],)); continue
            if side=='Buy' and positions[symbol]==0:
                quantity=min(cash,opening_equity*.30)/(fill*1.001)
            elif side=='Sell':
                quantity=positions[symbol]
            if quantity<=0:
                c.execute("UPDATE orders SET status='cancelled',reason='No eligible cash or position' WHERE id=?",(order['id'],)); continue
            fee=quantity*fill*.001
            cash += (-quantity*fill-fee) if side=='Buy' else quantity*fill-fee
            positions[symbol]+=quantity if side=='Buy' else -quantity
            c.execute("UPDATE orders SET status='filled',fill_date=?,quantity=?,price=?,fee=?,reason='Prior close signal; simulated next open' WHERE id=?",(day,quantity,fill,fee,order['id']))
        for symbol in SYMBOLS:
            c.execute('UPDATE positions SET shares=?,mark=? WHERE symbol=?',(positions[symbol],bars[symbol]['close'],symbol))
            signal,confidence=signals[symbol]
            c.execute('INSERT INTO observed_bars VALUES (?,?,?,?)',(day,symbol,bars[symbol]['open'],bars[symbol]['close']))
            c.execute('INSERT INTO signals VALUES (?,?,?,?)',(day,symbol,int(signal),float(confidence)))
            if signal==1 and positions[symbol]==0 or signal==-1 and positions[symbol]>0:
                c.execute("INSERT INTO orders(symbol,signal_date,side,confidence,status) VALUES (?,?,?,?,'pending')",(symbol,day,'Buy' if signal==1 else 'Sell',float(confidence)))
        invested=sum(positions[s]*bars[s]['close'] for s in SYMBOLS)
        c.execute('INSERT INTO snapshots VALUES (?,?,?,?)',(day,max(cash,0),invested,cash+invested))
        c.execute('UPDATE account SET cash=?,last_date=? WHERE id=1',(max(cash,0),day))
        log(c,'processed',f'{day}: recorded closing signals and eligible simulated fills')
    return 'processed'


def fetch_day(now=None):
    print('Checking the exchange calendar and latest market data…', flush=True)
    import exchange_calendars as xcals
    import yfinance as yf
    from src.features.build_features import add_indicators
    now=pd.Timestamp(now or datetime.now(timezone.utc))
    calendar=xcals.get_calendar('XNYS')
    date=now.tz_convert('America/New_York').date().isoformat()
    if not calendar.is_session(date):
        raise ValueError('Not an exchange session; no update needed')
    if now < calendar.session_close(date)+pd.Timedelta(minutes=60):
        raise ValueError('Wait until one hour after market close for daily data')
    previous=str(calendar.previous_session(date).date())
    bundle=joblib.load(MODEL)
    bars, signals={},{}
    for symbol in SYMBOLS:
        print(f'Downloading {symbol} prices…', flush=True)
        frame=yf.Ticker(symbol).history(period='1y',auto_adjust=False,actions=True)
        if frame.empty:
            raise ValueError(f'No data returned for {symbol}')
        frame.index=pd.to_datetime(frame.index).tz_localize(None).normalize()
        if str(frame.index[-1].date())!=date or frame.index.duplicated().any():
            raise ValueError(f'Stale or duplicate bars for {symbol}')
        with connect() as c:
            last=c.execute('SELECT last_date FROM account').fetchone()['last_date']
        actions=frame.loc[frame.index > pd.Timestamp(last)] if last else frame.iloc[-1:]
        if ((actions['Stock Splits']!=0)|(actions['Dividends']!=0)).any():
            raise ValueError(f'{symbol} corporate action requires review before updating virtual positions')
        if len(frame)<100 or frame[['Open','High','Low','Close','Adj Close']].isna().any().any():
            raise ValueError(f'Incomplete price history for {symbol}')
        feature=pd.DataFrame({'Date':frame.index,'symbol':symbol,'close':frame['Adj Close'].to_numpy()})
        features=add_indicators(feature).iloc[[-1]][bundle['features']]
        if not np.isfinite(features.to_numpy()).all():
            raise ValueError(f'Invalid indicators for {symbol}')
        probability=bundle['model'].predict_proba(features)[0]
        signals[symbol]=(int(bundle['model'].classes_[probability.argmax()]),float(probability.max()))
        bars[symbol]={'open':float(frame.iloc[-1].Open),'close':float(frame.iloc[-1].Close)}
        label={1: 'Buy', 0: 'Hold', -1: 'Sell'}[signals[symbol][0]]
        print(f'{symbol}: {label} signal ({signals[symbol][1]:.0%} model confidence).', flush=True)
    return bars,signals,date,previous


def run_daily():
    initialize()
    print('Starting paper-trading update…', flush=True)
    with connect() as c:
        account=c.execute('SELECT * FROM account').fetchone()
        if account['paused']:
            log(c,'skipped','Account paused'); return 'paused'
        if hashlib.sha256(MODEL.read_bytes()).hexdigest()!=account['model_hash']:
            set_paused(True); raise ValueError('Frozen model changed; account paused')
    try:
        bars,signals,date,previous=fetch_day()
        result = process_day(bars,signals,date,previous)
        print(f'Paper-trading update finished: {result}.', flush=True)
        return result
    except Exception as exc:
        with connect() as c:
            log(c,'skipped' if str(exc).startswith(('Not an exchange session','Wait until')) else 'error',str(exc))
        if str(exc).startswith(('Not an exchange session','Wait until')):
            return 'skipped'
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['init','run','pause','resume','check'])
    args=parser.parse_args()
    initialize()
    if args.action in ['pause','resume']:
        set_paused(args.action=='pause')
    elif args.action=='run':
        print(run_daily())
    elif args.action=='check':
        bars,signals,date,previous=fetch_day()
        print(f'Validated current session {date} for {len(bars)} symbols; no account changes')
