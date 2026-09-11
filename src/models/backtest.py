"""Long-only, equal initial allocation, next-open execution on holdout data."""
import json
import numpy as np
import pandas as pd
import joblib
import yaml


def simulate_symbol(df, initial_balance, transaction_cost, slippage):
    df = df.sort_values('Date').copy()
    cash, shares, trades = initial_balance, 0.0, 0
    previous_signal = 0
    equity, counts, details = [], [], []
    previous_date, previous_confidence = None, None
    for row in df.itertuples():
        action, quantity, fill, fee, slip_cost = 'None', 0.0, None, 0.0, 0.0
        if previous_signal == 1 and shares == 0:
            fill = row.open * (1 + slippage)
            shares = cash / (fill * (1 + transaction_cost))
            quantity = shares
            action = 'Buy'
            fee = shares * fill * transaction_cost
            slip_cost = shares * (fill - row.open)
            cash = 0.0
            trades += 1
        elif previous_signal == -1 and shares > 0:
            action, quantity = 'Sell', shares
            fill = row.open * (1 - slippage)
            fee = shares * fill * transaction_cost
            slip_cost = shares * (row.open - fill)
            cash = shares * fill * (1 - transaction_cost)
            shares = 0.0
            trades += 1
        equity.append(cash + shares * row.close)
        counts.append(trades)
        details.append(dict(action=action, quantity=quantity, execution_price=fill, fee=fee,
                            slippage_cost=slip_cost, cash=cash, shares=shares, holdings_value=shares * row.close,
                            signal_date=previous_date, execution_confidence=previous_confidence))
        previous_signal = row.predicted_signal
        previous_date = row.Date
        previous_confidence = getattr(row, 'confidence', None)
    df['equity'] = equity
    df['trade_count'] = counts
    for key in details[0] if details else []:
        df[key] = [item[key] for item in details]
    # Benchmark starts at the same first executable open as the strategy.
    df['benchmark_equity'] = float(initial_balance)
    if len(df) > 1:
        benchmark_shares = initial_balance / (df.iloc[1]['open'] * (1 + slippage) * (1 + transaction_cost))
        df.loc[df.index[1:], 'benchmark_equity'] = benchmark_shares * df.iloc[1:]['close']
    return df


def metrics(equity, initial_balance):
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    drawdown = equity / equity.cummax() - 1
    std = returns.std()
    return {'total_return': float(equity.iloc[-1] / initial_balance - 1),
            'annualized_return': float((equity.iloc[-1] / initial_balance) ** (1 / years) - 1) if years > 0 else None,
            'max_drawdown': float(drawdown.min()),
            'sharpe_ratio': float(np.sqrt(252) * returns.mean() / std) if pd.notna(std) and std > 0 else None}


def run_backtest():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    bundle = joblib.load(config['model']['save_path'])
    df = pd.read_csv('data/processed/features.csv', parse_dates=['Date'])
    df = df[df.Date >= pd.Timestamp(bundle['test_start'])].copy()
    df['predicted_signal'] = bundle['model'].predict(df[bundle['features']])
    settings = config['backtest']
    initial = settings['initial_balance']
    allocation = initial / df.symbol.nunique()
    result = pd.concat([simulate_symbol(group, allocation, settings['transaction_cost'], settings.get('slippage', 0.0005))
                        for _, group in df.groupby('symbol')], ignore_index=True)
    # Forward fill an asset's last valuation on dates when only other assets have a bar.
    portfolio = pd.DataFrame({col: result.pivot(index='Date', columns='symbol', values=col).ffill().fillna(allocation).sum(axis=1)
                              for col in ['equity', 'benchmark_equity']})
    report = {'start': str(portfolio.index.min().date()), 'end': str(portfolio.index.max().date()),
              'strategy': metrics(portfolio.equity, initial), 'benchmark': metrics(portfolio.benchmark_equity, initial),
              'trade_count': int(result.groupby('symbol').trade_count.max().sum()),
              'transaction_cost': settings['transaction_cost'], 'slippage': settings.get('slippage', 0.0005)}
    result.to_csv('data/processed/backtest_results.csv', index=False)
    portfolio.to_csv('data/processed/portfolio.csv')
    with open('data/processed/metrics.json', 'w') as f:
        json.dump(report, f, indent=2, allow_nan=False)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run_backtest()
