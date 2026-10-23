"""Fetch all symbols before replacing the saved price table."""
import sqlite3
from pathlib import Path
import pandas as pd
import yfinance as yf
import yaml


def validate_prices(prices, max_gap_days=5, max_jump=.4):
    """Raise on bad prices, long date gaps, mismatched calendars, or jumps that look like unadjusted splits."""
    if (prices[['open', 'high', 'low', 'close']] <= 0).any().any() or (prices.high < prices.low).any():
        raise ValueError('Non-positive prices or high below low')
    frame = prices.assign(Date=pd.to_datetime(prices.Date)).sort_values(['symbol', 'Date'])
    for symbol, group in frame.groupby('symbol'):
        if (group.Date.diff().dt.days > max_gap_days).any():
            raise ValueError(f'{symbol}: gap longer than {max_gap_days} days')
        if (group.close.pct_change().abs() > max_jump).any():
            raise ValueError(f'{symbol}: one-day move over {max_jump:.0%}; check for an unadjusted split')
    if frame.groupby('symbol').Date.apply(frozenset).nunique() > 1:
        raise ValueError('Symbols do not share the same trading dates')


def main():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)['data']
    parts = []
    for symbol in config['symbols']:
        df = yf.download(symbol, start=config['start_date'], interval=config['interval'], auto_adjust=True)
        if df.empty:
            raise ValueError(f'No data for {symbol}; existing database retained')
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower).reset_index()
        df['symbol'] = symbol
        parts.append(df[['Date', 'open', 'high', 'low', 'close', 'volume', 'symbol']])
    prices = pd.concat(parts, ignore_index=True).drop_duplicates(['symbol', 'Date'])
    if prices[['open', 'high', 'low', 'close', 'volume']].isna().any().any():
        raise ValueError('Missing price data; existing database retained')
    validate_prices(prices)
    Path(config['database']).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config['database']) as conn:
        prices.to_sql('price_data_staging', conn, if_exists='replace', index=False)
        conn.execute('DROP TABLE IF EXISTS price_data')
        conn.execute('ALTER TABLE price_data_staging RENAME TO price_data')
        conn.execute('CREATE UNIQUE INDEX price_symbol_date ON price_data(symbol, Date)')
    print(f'Stored {len(prices):,} unique price records')


if __name__ == '__main__':
    main()
