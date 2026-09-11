"""Build indicators independently per symbol, retaining label end dates."""
import pandas as pd
import sqlite3
import yaml
import ta


def add_indicators(df):
    parts = []
    for _, group in df.groupby('symbol'):
        group = group.sort_values('Date').copy()
        close = group['close']
        group['rsi'] = ta.momentum.RSIIndicator(close).rsi()
        macd = ta.trend.MACD(close)
        group['macd'] = macd.macd()
        group['macd_signal'] = macd.macd_signal()
        group['macd_hist'] = macd.macd_diff()
        for window in (20, 50):
            group[f'ema_{window}'] = ta.trend.EMAIndicator(close, window=window).ema_indicator()
        parts.append(group)
    return pd.concat(parts, ignore_index=True)


def add_target(df, horizon=5, threshold=0.02):
    df = df.sort_values(['symbol', 'Date']).copy()
    groups = df.groupby('symbol')
    df['target_date'] = groups['Date'].shift(-horizon)
    df['future_return'] = groups['close'].shift(-horizon) / df['close'] - 1
    df['signal'] = 0
    df.loc[df.future_return > threshold, 'signal'] = 1
    df.loc[df.future_return < -threshold, 'signal'] = -1
    return df


def main():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    with sqlite3.connect(config['data']['database']) as conn:
        df = pd.read_sql('SELECT * FROM price_data', conn)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.drop_duplicates(['symbol', 'Date']).sort_values(['symbol', 'Date'])
    df = add_target(add_indicators(df), config['features']['prediction_horizon'])
    # Retain the final unlabeled rows for inference and mark-to-market.
    df = df.dropna(subset=['rsi', 'macd', 'macd_signal', 'ema_20', 'ema_50'])
    df.to_csv('data/processed/features.csv', index=False)
    print(f'Saved {len(df):,} feature rows')


if __name__ == '__main__':
    main()
