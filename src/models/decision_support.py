"""Historical criteria checks and a fixed initial stock/cash benchmark."""
import math
import pandas as pd
from src.models.backtest import metrics


def stock_cash_benchmark(full_stock, capital, stock_weight):
    if capital <= 0 or not 0 <= stock_weight <= 1:
        raise ValueError('Capital must be positive and stock allocation between zero and one')
    # Entry costs scale with the invested sleeve; reserved cash earns zero.
    # There is no rebalancing, so stock exposure drifts after the initial purchase.
    return full_stock * stock_weight + capital * (1 - stock_weight)


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
