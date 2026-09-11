"""Annual expanding-window evaluation and reproducible cost/confidence scenarios."""
import argparse
import hashlib
import itertools
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from src.models.backtest import metrics, simulate_symbol
from src.models.train_model import FEATURES
from src.models.risk_metrics import risk_metrics

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'data/research.db'
PREDICTIONS = ROOT / 'data/processed/walk_forward.csv'


def annual_splits(df, first_year=2021):
    for year in range(first_year, df.Date.dt.year.max() + 1):
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year + 1, month=1, day=1)
        train = df[(df.Date < start) & (df.target_date < start) & df.future_return.notna()]
        test = df[(df.Date >= start) & (df.Date < end)]
        if len(train) and len(test):
            yield year, train, test


def walk_forward():
    df = pd.read_csv(ROOT / 'data/processed/features.csv', parse_dates=['Date', 'target_date'])
    output, folds = [], []
    for year, train, test in annual_splits(df):
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        model.fit(train[FEATURES], train.signal)
        test = test.copy()
        probabilities = model.predict_proba(test[FEATURES])
        test['predicted_signal'] = model.classes_[probabilities.argmax(axis=1)]
        test['confidence'] = probabilities.max(axis=1)
        test['fold'] = year
        labeled = test.future_return.notna()
        folds.append({'year': year, 'train_rows': len(train), 'test_rows': len(test),
                      'train_last_label': str(train.target_date.max()),
                      'test_start': str(test.Date.min()), 'test_end': str(test.Date.max()),
                      'accuracy': accuracy_score(test.loc[labeled, 'signal'], test.loc[labeled, 'predicted_signal'])})
        output.append(test)
        print(f'Completed fold {year}: {len(train)} training, {len(test)} test rows', flush=True)
    if not output:
        raise ValueError('No walk-forward folds available')
    pd.concat(output).to_csv(PREDICTIONS, index=False)
    with sqlite3.connect(DB) as conn:
        pd.DataFrame(folds).to_sql('folds', conn, if_exists='replace', index=False)
    return pd.concat(output)


def evaluate(df, confidence=.0, fee=.001, slippage=.0005, capital=10000.):
    if df.empty or df.Date.nunique() < 2:
        raise ValueError('Select a period with at least two trading dates')
    if not (0 <= confidence <= 1 and 0 <= fee < 1 and 0 <= slippage < 1 and capital > 0):
        raise ValueError('Invalid scenario parameters')
    df = df.copy()
    df.loc[df.confidence < confidence, 'predicted_signal'] = 0
    allocation = capital / df.symbol.nunique()
    result = pd.concat([simulate_symbol(g, allocation, fee, slippage) for _, g in df.groupby('symbol')])
    curve = pd.DataFrame({key: result.pivot(index='Date', columns='symbol', values=key).ffill().fillna(allocation).sum(axis=1)
                          for key in ['equity', 'benchmark_equity']})
    stats = metrics(curve.equity, capital)
    stats.update(risk_metrics(curve.equity, curve.benchmark_equity))
    benchmark = metrics(curve.benchmark_equity, capital)
    benchmark.update(risk_metrics(curve.benchmark_equity))
    stats.update({'benchmark_' + k: v for k, v in benchmark.items()})
    stats['trade_count'] = int(result.groupby('symbol').trade_count.max().sum())
    return curve, stats


def save_run(df, confidence=0., fee=.001, slippage=.0005, capital=10000., scope='custom', db=DB, store_curve=True):
    fingerprint = hashlib.sha256(pd.util.hash_pandas_object(df.sort_values(['symbol', 'Date']), index=False).values.tobytes()).hexdigest()
    params = dict(confidence=float(confidence), fee=float(fee), slippage=float(slippage), capital=float(capital),
                  scope=scope, start=str(df.Date.min().date()), end=str(df.Date.max().date()), data_hash=fingerprint, engine_version=1)
    run_id = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
    curve, stats = evaluate(df, confidence, fee, slippage, capital)
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, parameters TEXT NOT NULL, metrics TEXT NOT NULL)')
        conn.execute('INSERT OR REPLACE INTO runs VALUES (?, ?, ?)', (run_id, json.dumps(params), json.dumps(stats, allow_nan=False)))
        if store_curve:
            conn.execute('CREATE TABLE IF NOT EXISTS curves (run_id TEXT, date TEXT, equity REAL, benchmark REAL, PRIMARY KEY(run_id,date))')
            conn.executemany('INSERT OR REPLACE INTO curves VALUES (?, ?, ?, ?)',
                             [(run_id, str(date), row.equity, row.benchmark_equity) for date, row in curve.iterrows()])
    return run_id, curve, stats


def list_runs(db=DB):
    if not Path(db).exists():
        return pd.DataFrame()
    with sqlite3.connect(db) as conn:
        if not conn.execute("SELECT name FROM sqlite_master WHERE name='runs'").fetchone():
            return pd.DataFrame()
        rows = conn.execute('SELECT run_id, parameters, metrics FROM runs').fetchall()
    return pd.DataFrame([{'run_id': rid, **json.loads(p), **json.loads(m)} for rid, p, m in rows])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-predictions', action='store_true')
    args = parser.parse_args()
    df = pd.read_csv(PREDICTIONS, parse_dates=['Date']) if args.reuse_predictions else walk_forward()
    development = df[df.Date < '2024-01-01']
    # Fixed grid on development years only; later years are not used for ranking.
    grid = itertools.product([0., .4, .5, .6, .7], np.linspace(0, .003, 10), np.linspace(0, .002, 20))
    for i, (confidence, fee, slippage) in enumerate(grid, 1):
        save_run(development, confidence, fee, slippage, scope='development', store_curve=False)
        if i % 100 == 0:
            print(f'Saved {i}/1000 development scenarios', flush=True)
    for year, group in df.groupby('fold'):
        save_run(group, scope=f'annual_default_{year}')
    _, _, stats = save_run(df[df.Date >= '2024-01-01'], scope='later_period_default')
    print('Later-period default (not selected from grid):', json.dumps(stats), flush=True)


if __name__ == '__main__':
    main()
