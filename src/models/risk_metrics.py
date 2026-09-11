"""Daily portfolio metrics; zero risk-free rate and zero downside target."""
import numpy as np
import pandas as pd


def risk_metrics(equity, benchmark=None):
    equity = equity.sort_index().astype(float)
    returns = equity.pct_change().dropna()
    if returns.empty:
        return {}
    std = returns.std()
    downside = np.sqrt(np.mean(np.minimum(returns, 0) ** 2))
    drawdown = equity / equity.cummax() - 1
    max_dd = abs(drawdown.min())
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else None
    streak = longest = 0
    for below in drawdown < -1e-12:
        streak = streak + 1 if below else 0
        longest = max(longest, streak)
    tail_cutoff = returns.quantile(.05)
    result = {
        'annualized_volatility': std * np.sqrt(252) if pd.notna(std) else None,
        'sortino_ratio': returns.mean() / downside * np.sqrt(252) if downside > 0 else None,
        'calmar_ratio': cagr / max_dd if max_dd > 0 and cagr is not None else None,
        'positive_day_rate': (returns > 0).mean(),
        'best_day': returns.max(), 'worst_day': returns.min(),
        'daily_return_p05': tail_cutoff,
        'expected_shortfall_return': returns[returns <= tail_cutoff].mean(),
        'longest_underwater_sessions': longest,
    }
    if benchmark is not None:
        aligned = pd.concat([returns.rename('strategy'), benchmark.sort_index().pct_change().rename('benchmark')], axis=1).dropna()
        active = aligned.strategy - aligned.benchmark
        tracking = active.std()
        variance = aligned.benchmark.var()
        result.update({
            'tracking_error': tracking * np.sqrt(252) if pd.notna(tracking) else None,
            'information_ratio': active.mean() / tracking * np.sqrt(252) if pd.notna(tracking) and tracking > 1e-12 else None,
            'beta': aligned.strategy.cov(aligned.benchmark) / variance if pd.notna(variance) and variance > 1e-12 else None,
            'benchmark_correlation': aligned.strategy.corr(aligned.benchmark) if aligned.strategy.std() > 1e-12 and aligned.benchmark.std() > 1e-12 else None,
        })
    return {key: (float(value) if value is not None and np.isfinite(value) else None) for key, value in result.items()}
