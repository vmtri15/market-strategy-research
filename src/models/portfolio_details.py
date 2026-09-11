"""Auditable positions and trades from the same backtest execution engine."""
import pandas as pd
from src.models.backtest import simulate_symbol


def portfolio_details(df, confidence=0., fee=.001, slippage=.0005, capital=10000.):
    if df.empty:
        raise ValueError('No observations for portfolio breakdown')
    data=df.copy()
    data.loc[data.confidence < confidence,'predicted_signal']=0
    allocation=capital/data.symbol.nunique()
    history=pd.concat([simulate_symbol(group,allocation,fee,slippage) for _,group in data.groupby('symbol')])
    history=history.sort_values(['Date','symbol'])
    values={}
    for key in ['cash','holdings_value','equity']:
        values[key]=history.pivot(index='Date',columns='symbol',values=key).ffill().fillna(0 if key=='holdings_value' else allocation)
    composition=pd.DataFrame({'Cash':values['cash'].sum(axis=1),'Invested':values['holdings_value'].sum(axis=1)})
    ledger=history[history.action!='None'][['Date','symbol','action','signal_date','execution_confidence','quantity','open','execution_price','fee','slippage_cost','cash','shares','equity']].copy()
    ledger['reason']=ledger.action.map({'Buy':'Prior close predicted Buy; no position held.','Sell':'Prior close predicted Sell; position held.'})
    summary=history.groupby('symbol').agg(ending_cash=('cash','last'),ending_shares=('shares','last'),holdings_value=('holdings_value','last'),ending_equity=('equity','last'),fees=('fee','sum'),slippage_cost=('slippage_cost','sum'))
    summary['starting_allocation']=allocation
    summary['net_gain']=summary.ending_equity-allocation
    summary['portfolio_return_contribution_pp']=summary.net_gain/capital*100
    return history,ledger,composition,summary
