"""Fetch all symbols before replacing the saved price table."""
import sqlite3
from pathlib import Path
import pandas as pd
import yfinance as yf
import yaml


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
    Path(config['database']).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config['database']) as conn:
        prices.to_sql('price_data_staging', conn, if_exists='replace', index=False)
        conn.execute('DROP TABLE IF EXISTS price_data')
        conn.execute('ALTER TABLE price_data_staging RENAME TO price_data')
        conn.execute('CREATE UNIQUE INDEX price_symbol_date ON price_data(symbol, Date)')
    print(f'Stored {len(prices):,} unique price records')


if __name__ == '__main__':
    main()
