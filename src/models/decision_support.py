"""Historical criteria checks and a fixed initial stock/cash benchmark."""
import math
import numpy as np
import pandas as pd
from src.models.backtest import metrics


def stock_cash_benchmark(full_stock, capital, stock_weight):
    if capital <= 0 or not 0 <= stock_weight <= 1:
        raise ValueError('Capital must be positive and stock allocation between zero and one')
    # Entry costs scale with the invested sleeve; reserved cash earns zero.
    # There is no rebalancing, so stock exposure drifts after the initial purchase.
    return full_stock * stock_weight + capital * (1 - stock_weight)


def vol_target_benchmark(full_stock, capital, target_vol, window=20, trade_cost=.0015):
    """Stock exposure = target volatility / trailing realized volatility, capped at 100%, rest in cash.

    Exposure uses the previous session's volatility estimate and starts in cash until the window fills.
    trade_cost is fee plus slippage per unit of exposure traded; cash earns zero.
    """
    if capital <= 0 or target_vol <= 0:
        raise ValueError('Capital and target volatility must be positive')
    returns = full_stock.pct_change().fillna(0)
    realized = returns.rolling(window).std() * np.sqrt(252)
    weight = (target_vol / realized).clip(upper=1).shift(1).fillna(0)
    net = weight * returns - weight.diff().abs().fillna(weight.abs()) * trade_cost
    return capital * (1 + net).cumprod()


def criteria_table(curves, capital, minimum_return, maximum_drawdown):
    if not 0 <= maximum_drawdown <= 1:
        raise ValueError('Maximum drawdown must be between zero and one')
    rows=[]
    for name in curves:
        stats=metrics(curves[name],capital)
        annual=stats['annualized_return']
        return_ok=None if annual is None or not math.isfinite(annual) else annual >= minimum_return
        risk_ok=abs(stats['max_drawdown']) <= maximum_drawdown
        rows.append({'Portfolio':name, 'Annualized return':annual, 'Maximum drawdown':stats['max_drawdown'],
                     'Ending value':float(curves[name].iloc[-1]),
                     'Return target':'Unavailable' if return_ok is None else ('Met' if return_ok else 'Missed'),
                     'Drawdown limit':'Met' if risk_ok else 'Missed',
                     'Overall':'Unavailable' if return_ok is None else ('Both met' if return_ok and risk_ok else 'Not met')})
    return pd.DataFrame(rows)
