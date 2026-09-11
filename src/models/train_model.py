"""Chronological holdout with labels purged at the cutoff."""
import json
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib
import yaml

FEATURES = ['rsi', 'macd', 'macd_signal', 'ema_20', 'ema_50']


def split_data(df, test_fraction=0.2):
    dates = sorted(df['Date'].unique())
    cutoff = pd.Timestamp(dates[int(len(dates) * (1 - test_fraction))])
    train = df[(df.Date < cutoff) & (df.target_date < cutoff)].copy()
    test = df[(df.Date >= cutoff) & df.future_return.notna()].copy()
    if train.empty or test.empty:
        raise ValueError('Insufficient data for chronological train/test split')
    return train, test, cutoff


def train_model():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    df = pd.read_csv('data/processed/features.csv', parse_dates=['Date', 'target_date'])
    train, test, cutoff = split_data(df)
    model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    model.fit(train[FEATURES], train.signal)
    report = classification_report(test.signal, model.predict(test[FEATURES]), output_dict=True, zero_division=0)
    bundle = {'model': model, 'features': FEATURES, 'test_start': cutoff.isoformat(),
              'train_rows': len(train), 'test_rows': len(test)}
    joblib.dump(bundle, config['model']['save_path'])
    with open('models/evaluation.json', 'w') as f:
        json.dump({k: v for k, v in bundle.items() if k != 'model'} | {'classification': report}, f, indent=2)
    print(f'Trained on {len(train):,} rows; tested on {len(test):,} rows from {cutoff.date()}')
    print(f'Holdout accuracy: {report["accuracy"]:.3f}')


if __name__ == '__main__':
    train_model()
