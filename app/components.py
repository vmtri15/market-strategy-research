"""Reusable dashboard panels: charts, metric cards, risk, portfolio and criteria views."""
import altair as alt
import pandas as pd
import streamlit as st

from src.models.risk_metrics import risk_metrics
from src.models.portfolio_details import portfolio_details
from src.models.decision_support import stock_cash_benchmark, criteria_table, vol_target_benchmark


def chart(frame, columns, percent=False):
    data = frame[columns].rename_axis('Date').reset_index().melt('Date', var_name='Series', value_name='Value')
    plot = alt.Chart(data).mark_line(strokeWidth=2.5).encode(
        x=alt.X('Date:T', title=None),
        y=alt.Y('Value:Q', title=None, axis=alt.Axis(format='.0%' if percent else ',.0f'), scale=alt.Scale(zero=False)),
        color=alt.Color('Series:N', scale=alt.Scale(range=['#0d9488', '#64748b', '#e59f38', '#7c3aed']), legend=alt.Legend(orient='top', title=None)),
        tooltip=[alt.Tooltip('Date:T', format='%b %d, %Y'), 'Series:N', alt.Tooltip('Value:Q', format='.2%' if percent else ',.2f')]
    ).properties(height=340).interactive()
    st.altair_chart(plot, width='stretch')


def cards(stats):
    for col, label, key in zip(st.columns(4), ['Annualized return', 'Total return', 'Maximum drawdown', 'Orders executed'], ['annualized_return','total_return','max_drawdown','trade_count']):
        value = stats[key]
        col.metric(label, f'{int(value):,}' if key == 'trade_count' else ('N/A' if pd.isna(value) else f'{value:.1%}'))


def risk_panel(equity, benchmark):
    strategy = risk_metrics(equity, benchmark)
    reference = risk_metrics(benchmark)
    st.subheader('Risk and consistency')
    specs = [
        ('Annualized volatility', 'annualized_volatility', '.1%', 'Daily return variability scaled by the square root of 252. Lower means less fluctuation.'),
        ('Sortino ratio', 'sortino_ratio', '.2f', 'Average daily return relative to downside deviation, annualized; target return is zero.'),
        ('Calmar ratio', 'calmar_ratio', '.2f', 'Annualized growth divided by the absolute maximum drawdown.'),
        ('Positive days', 'positive_day_rate', '.1%', 'Share of observed daily returns above zero, including flat days in the denominator. This is not trade win rate.'),
        ('Best day', 'best_day', '.2%', 'Highest observed daily portfolio return.'),
        ('Worst day', 'worst_day', '.2%', 'Lowest observed daily portfolio return.'),
        ('Longest time below peak', 'longest_underwater_sessions', '.0f', 'Consecutive observed sessions below the previous peak, including an unrecovered period at the end.'),
        ('Worst-tail average return', 'expected_shortfall_return', '.2%', 'Average daily return at or below the historical fifth percentile; an observed tail statistic, not a forecast.'),
    ]
    for start in (0, 4):
        for col, (label,key,fmt,help_text) in zip(st.columns(4), specs[start:start+4]):
            value = strategy.get(key)
            col.metric(label, 'N/A' if value is None else format(value,fmt), help=help_text)
    with st.expander('Benchmark-relative metrics and full comparison'):
        relative = [('Beta', 'beta', '.2f', 'Sensitivity to daily changes in this equal-weight initial-allocation benchmark.'),
                    ('Correlation', 'benchmark_correlation', '.2f', 'How closely daily returns move together, from -1 to 1.'),
                    ('Tracking error', 'tracking_error', '.1%', 'Annualized variability of the daily strategy-minus-benchmark return.'),
                    ('Information ratio', 'information_ratio', '.2f', 'Annualized mean active daily return divided by tracking error.')]
        for col,(label,key,fmt,help_text) in zip(st.columns(4),relative):
            value=strategy.get(key)
            col.metric(label, 'N/A' if value is None else format(value,fmt), help=help_text)
        table = pd.DataFrame([{'Metric':label, 'Strategy':'N/A' if strategy.get(key) is None else format(strategy[key],fmt),
            'Buy and hold':'N/A' if reference.get(key) is None else format(reference[key],fmt)} for label,key,fmt,_ in specs])
        st.dataframe(table,hide_index=True,width='stretch')
    st.caption('Daily metrics use observed portfolio valuation dates, including carried-forward valuations. Annualization assumes 252 sessions. Ratios with zero denominators show N/A; cash returns are zero.')


def portfolio_panel(data, confidence=0., fee=.001, slippage=.0005, capital=10000., key='portfolio', containers=None):
    criteria_box, money_box = containers or (st.container(), st.container())
    history, ledger, composition, summary = portfolio_details(data, confidence, fee, slippage, capital)
    with criteria_box:
        decision_panel(history, composition, capital, key)
    with money_box:
        st.subheader('Where did the money go?')
        positions, trades = st.tabs(['Cash and holdings', 'Executed trades'])
        _money_tabs(positions, trades, history, ledger, composition, summary, key)


def _money_tabs(positions, trades, history, ledger, composition, summary, key):
    with positions:
        a,b,c = st.columns(3)
        a.metric('Average stock exposure', f"{(composition.Invested / composition.sum(axis=1)).mean():.1%}", help='Mean end-of-session invested value divided by portfolio equity. Not intraday exposure.')
        b.metric('Total fees paid', f"${summary.fees.sum():,.2f}")
        c.metric('Execution slippage', f"${summary.slippage_cost.sum():,.2f}", help='Share quantity times the difference between the open and simulated fill price. This is embedded in execution prices, not an extra fee.')
        stacked=composition.rename_axis('Date').reset_index().melt('Date',var_name='Allocation',value_name='Value')
        st.altair_chart(alt.Chart(stacked).mark_area().encode(x='Date:T', y=alt.Y('Value:Q',stack='zero',title='Account value ($)'),color=alt.Color('Allocation:N',scale=alt.Scale(domain=['Cash','Invested'],range=['#94a3b8','#0d9488'])),tooltip=['Date:T','Allocation',alt.Tooltip('Value:Q',format=',.2f')]).properties(height=260),width='stretch')
        st.write('Ending positions and contribution by stock')
        st.dataframe(summary.round(3),width='stretch')
        st.caption('Net gain includes realized and unrealized changes after trading costs. Contributions sum to portfolio total return in percentage points. Fees and slippage are already reflected in account values; do not subtract them again.')
        st.download_button('Download daily holdings',history.to_csv(index=False),'daily_holdings.csv',key=key+'_holdings')
    with trades:
        if ledger.empty:
            st.info('No orders were executed with these settings. The account stayed in cash.')
        else:
            st.caption('Orders use the previous available closing signal and execute at the next open. Click an execution below to inspect its details.')
            labels=[f"{row.Date.date()} · {row.symbol} · {row.action}" for row in ledger.itertuples()]
            selected=st.selectbox('Inspect an execution',range(len(ledger)),format_func=lambda i:labels[i],key=key+'_trade')
            trade=ledger.iloc[selected]
            confidence_text='unavailable' if pd.isna(trade.execution_confidence) else f'{trade.execution_confidence:.0%}'
            st.write(f"**{trade.action} {trade.quantity:,.4f} shares of {trade.symbol} at ${trade.execution_price:,.2f}.** Signal: {pd.Timestamp(trade.signal_date).date()} · confidence: {confidence_text}.")
            st.write(f"{trade.reason} Fee: ${trade.fee:,.2f}. Slippage impact: ${trade.slippage_cost:,.2f}.")
            st.caption('Cash and shares are after this execution; equity is this stock allocation marked at that day’s close. Confidence is uncalibrated.')
            st.dataframe(ledger.sort_values('Date',ascending=False),hide_index=True,width='stretch')
        st.download_button('Download trade ledger',ledger.to_csv(index=False),'trade_ledger.csv',key=key+'_ledger')


def decision_panel(history, composition, capital, key):
    st.subheader('Does this meet my criteria?')
    st.caption('Choose historical evaluation thresholds. Defaults are examples, not recommended investment targets.')
    a,b,c,d=st.columns(4)
    target=a.number_input('Minimum annualized return (%)',min_value=-100.,max_value=1000.,value=10.,step=1.,key=key+'_target')
    limit=b.number_input('Maximum acceptable drawdown (%)',min_value=0.,max_value=100.,value=15.,step=1.,key=key+'_limit')
    weight=c.slider('Simple benchmark: initial stocks (%)',0,100,60,5,key=key+'_weight')
    vol=d.slider('Volatility target (% a year)',5,30,15,5,key=key+'_vol',help='Model-free benchmark: holds fewer stocks when recent daily swings are large, more when calm. Fully invested at most; no leverage.')
    allocation=capital/history.symbol.nunique()
    full=history.pivot(index='Date',columns='symbol',values='benchmark_equity').ffill().fillna(allocation).sum(axis=1)
    name=f'{weight}% stocks / {100-weight}% cash (initial)'
    curves=pd.DataFrame({'Model strategy':composition.sum(axis=1),'100% buy and hold':full,
                         name:stock_cash_benchmark(full,capital,weight/100),
                         f'Volatility target {vol}%':vol_target_benchmark(full,capital,vol/100)})
    result=criteria_table(curves,capital,target/100,limit/100)
    display=result.copy()
    for column in ['Annualized return','Maximum drawdown']:
        display[column]=display[column].map(lambda value:'N/A' if pd.isna(value) else f'{value:.1%}')
    display['Ending value']=display['Ending value'].map(lambda value:f'${value:,.0f}')
    st.dataframe(display,hide_index=True,width='stretch')
    passed=result[result.Overall=='Both met'].Portfolio.tolist()
    if passed:
        st.success('Met both criteria in this period: '+', '.join(passed)+'.')
    else:
        st.info('No portfolio met both criteria in this period.')
    stock_fraction=(composition.Invested/composition.sum(axis=1)).mean()
    st.caption(f'Model average end-of-session stock exposure: {stock_fraction:.1%}. The simple benchmark starts at {weight}% stocks; its exposure drifts with prices. It is not an exact exposure-matched portfolio.')
    with st.expander('Compare all portfolio paths',expanded=True):
        chart(curves,list(curves.columns))
    strategy=result.iloc[0]
    simple=result.iloc[2]
    return_gap=strategy['Annualized return']-simple['Annualized return'] if pd.notna(strategy['Annualized return']) and pd.notna(simple['Annualized return']) else None
    drawdown_gap=strategy['Maximum drawdown']-simple['Maximum drawdown']
    if return_gap is not None:
        st.write(f"Compared with the simple stock/cash portfolio, the model’s annualized return differed by **{return_gap*100:+.1f} percentage points** and its drawdown reduction was **{drawdown_gap*100:+.1f} percentage points**. Positive drawdown reduction means a smaller decline.")
    st.caption('Volatility target: exposure = target ÷ trailing 20-day realized volatility (capped at 100%, set from the prior session, starting in cash), with 0.15% cost per unit of exposure traded. It uses no model. In longer historical tests (SPY 2000–2025, 32 large caps 2013–2025) it cut maximum drawdown substantially but usually earned less than buy-and-hold.')
    st.caption('This tests whether a simpler allocation offers a useful alternative; it does not establish that timing or the model caused the difference. Same securities, first eligible entry dates, and proportional entry costs. Cash earns zero; no rebalancing or forced liquidation. Thresholds apply only to the displayed historical period, not future outcomes.')
    st.download_button('Download criteria comparison',result.to_csv(index=False),'criteria_comparison.csv',key=key+'_criteria_download')
