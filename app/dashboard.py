"""Interactive research dashboard, using saved predictions and evaluation results."""
import sys
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'app'))
from src.models.research import PREDICTIONS, DB, list_runs, save_run, evaluate
from src.models.business_report import build_report
from src.models.risk_metrics import risk_metrics
from src.models.portfolio_details import portfolio_details
from src.models.decision_support import stock_cash_benchmark, criteria_table

st.set_page_config(page_title='Market Lab | Strategy Explorer', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem; padding-bottom:3rem; max-width:1440px;}
h1 {letter-spacing:-1.5px; font-weight:750 !important;}
[data-testid="stMetric"] {border:1px solid #dce4ec; border-radius:12px; padding:18px;}
[data-testid="stSidebar"] {border-right:1px solid #e2e8f0;}
</style>''', unsafe_allow_html=True)


def chart(frame, columns, percent=False):
    data = frame[columns].rename_axis('Date').reset_index().melt('Date', var_name='Series', value_name='Value')
    plot = alt.Chart(data).mark_line(strokeWidth=2.5).encode(
        x=alt.X('Date:T', title=None),
        y=alt.Y('Value:Q', title=None, axis=alt.Axis(format='.0%' if percent else ',.0f'), scale=alt.Scale(zero=False)),
        color=alt.Color('Series:N', scale=alt.Scale(range=['#0d9488', '#64748b', '#e59f38']), legend=alt.Legend(orient='top', title=None)),
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


def portfolio_panel(data, confidence=0., fee=.001, slippage=.0005, capital=10000., key='portfolio'):
    history, ledger, composition, summary = portfolio_details(data, confidence, fee, slippage, capital)
    decision_panel(history, composition, capital, key)
    st.subheader('Where did the money go?')
    positions, trades = st.tabs(['Cash and holdings', 'Executed trades'])
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
    a,b,c=st.columns(3)
    target=a.number_input('Minimum annualized return (%)',min_value=-100.,max_value=1000.,value=10.,step=1.,key=key+'_target')
    limit=b.number_input('Maximum acceptable drawdown (%)',min_value=0.,max_value=100.,value=15.,step=1.,key=key+'_limit')
    weight=c.slider('Simple benchmark: initial stocks (%)',0,100,60,5,key=key+'_weight')
    allocation=capital/history.symbol.nunique()
    full=history.pivot(index='Date',columns='symbol',values='benchmark_equity').ffill().fillna(allocation).sum(axis=1)
    name=f'{weight}% stocks / {100-weight}% cash (initial)'
    curves=pd.DataFrame({'Model strategy':composition.sum(axis=1),'100% buy and hold':full,
                         name:stock_cash_benchmark(full,capital,weight/100)})
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
    with st.expander('Compare all three portfolio paths',expanded=True):
        chart(curves,list(curves.columns))
    strategy=result.iloc[0]
    simple=result.iloc[2]
    return_gap=strategy['Annualized return']-simple['Annualized return'] if pd.notna(strategy['Annualized return']) and pd.notna(simple['Annualized return']) else None
    drawdown_gap=strategy['Maximum drawdown']-simple['Maximum drawdown']
    if return_gap is not None:
        st.write(f"Compared with the simple stock/cash portfolio, the model’s annualized return differed by **{return_gap*100:+.1f} percentage points** and its drawdown reduction was **{drawdown_gap*100:+.1f} percentage points**. Positive drawdown reduction means a smaller decline.")
    st.caption('This tests whether a simpler allocation offers a useful alternative; it does not establish that timing or the model caused the difference. Same securities, first eligible entry dates, and proportional entry costs. Cash earns zero; no rebalancing or forced liquidation. Thresholds apply only to the displayed historical period, not future outcomes.')
    st.download_button('Download criteria comparison',result.to_csv(index=False),'criteria_comparison.csv',key=key+'_criteria_download')


st.sidebar.markdown('## MARKET LAB')
st.sidebar.caption('Strategy research workspace')
page = st.sidebar.radio('Explore', ['Overview', 'Stock explorer', 'Scenario lab', 'Saved comparisons', 'Paper trading'])
st.sidebar.divider()
st.sidebar.caption('AAPL · MSFT · SPY\n\nHistorical research • Prices through Oct 2025')
st.title(page)
if page == 'Paper trading':
    from paper_page import render
    render()
    st.stop()
if not PREDICTIONS.exists():
    st.info('Run make research to prepare dashboard data.')
    st.stop()
predictions = pd.read_csv(PREDICTIONS, parse_dates=['Date'])
runs = list_runs()
for metric_key in ['annualized_volatility','sortino_ratio','positive_day_rate','beta']:
    if metric_key not in runs.columns:
        runs[metric_key] = float('nan')
if runs.empty:
    st.info('No saved research runs. Run make research first.')
    st.stop()

if page == 'Overview':
    text, annual, sensitivity, base = build_report(runs)
    st.caption(f"DEFAULT WALK-FORWARD STRATEGY  /  {base.start} — {base.end}")
    st.subheader('Lower drawdowns. A measurable return tradeoff.')
    st.write('Compare the model with an equally allocated buy-and-hold portfolio, then explore how assumptions change the result.')
    cards(base)
    with sqlite3.connect(DB) as conn:
        curve = pd.read_sql('SELECT date, equity, benchmark FROM curves WHERE run_id=? ORDER BY date', conn, params=[base.run_id], parse_dates=['date']).set_index('date')
    balance, downside = st.tabs(['Portfolio growth', 'Drawdown'])
    with balance:
        chart(curve.rename(columns={'equity':'Strategy', 'benchmark':'Buy and hold'}), ['Strategy','Buy and hold'])
    with downside:
        dd = curve / curve.cummax() - 1
        chart(dd.rename(columns={'equity':'Strategy', 'benchmark':'Buy and hold'}), ['Strategy','Buy and hold'], True)
    portfolio_panel(predictions[predictions.Date.between(pd.Timestamp(base.start),pd.Timestamp(base.end))], base.confidence,base.fee,base.slippage,base.capital,key='overview')
    risk_panel(curve.equity, curve.benchmark)
    left, right = st.columns([2,1])
    with left:
        st.subheader('Year-by-year performance')
        data = annual[['Period','Strategy return (%)','Buy-and-hold return (%)']].melt('Period', var_name='Portfolio', value_name='Return')
        st.altair_chart(alt.Chart(data).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(x='Period:N', xOffset='Portfolio:N', y=alt.Y('Return:Q',title='Total return (%)'), color=alt.Color('Portfolio:N',scale=alt.Scale(range=['#0d9488','#64748b'])), tooltip=['Period','Portfolio',alt.Tooltip('Return:Q',format='.1f')]).properties(height=260), width='stretch')
    with right:
        st.subheader('What to take away')
        st.write(f"**{(annual['Return difference (pp)'] > 0).sum()} of {len(annual)} periods** beat buy-and-hold on return.")
        st.write(f"**{(annual['Drawdown reduction (pp)'] > 0).sum()} of {len(annual)} periods** had smaller drawdowns.")
        st.caption('Annual portfolios restart in cash. 2025 is partial. These comparisons do not establish a future advantage.')
    with st.expander('Methodology and full report'):
        st.markdown(text)
        st.download_button('Download report', text, 'business_report.md')

elif page == 'Stock explorer':
    st.caption('Explore historical prices and model signals by security.')
    one, two = st.columns([1,3])
    symbol = one.selectbox('Security', sorted(predictions.symbol.unique()))
    dates = two.date_input('Period', (predictions.Date.min().date(), predictions.Date.max().date()), min_value=predictions.Date.min().date(), max_value=predictions.Date.max().date())
    if len(dates) != 2:
        st.info('Choose a start and end date.'); st.stop()
    selected = predictions[(predictions.symbol == symbol) & predictions.Date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))].copy()
    if selected.empty:
        st.info('No trading data in this date range.'); st.stop()
    a,b,c = st.columns(3)
    a.metric('Last historical close', f"${selected.close.iloc[-1]:,.2f}")
    b.metric('Price change in selected range', f'{selected.close.iloc[-1]/selected.close.iloc[0]-1:+.1%}')
    c.metric('Trading observations', f'{len(selected):,}')
    price = alt.Chart(selected).mark_line(color='#0d9488').encode(x='Date:T',y=alt.Y('close:Q',scale=alt.Scale(zero=False),title='Close ($)'),tooltip=['Date:T',alt.Tooltip('close:Q',format='.2f')])
    signal_rows = selected[selected.predicted_signal != 0].copy()
    signal_rows['Signal'] = signal_rows.predicted_signal.map({1:'Buy',-1:'Sell'})
    markers = alt.Chart(signal_rows).mark_point(size=35, opacity=.6).encode(x='Date:T',y='close:Q',color=alt.Color('Signal:N',scale=alt.Scale(domain=['Buy','Sell'],range=['#2563eb','#e66a4e'])),tooltip=['Date:T','Signal',alt.Tooltip('confidence:Q',format='.0%')])
    st.altair_chart((price+markers).properties(height=380).interactive(), width='stretch')
    st.caption('Markers are model signals at the close, not executed trades. Orders may execute at the next available open. Confidence is uncalibrated.')
    with st.expander('View and download signal history'):
        history = selected[['Date','close','predicted_signal','confidence']].rename(columns={'predicted_signal':'Signal'})
        history.Signal = history.Signal.map({1:'Buy',0:'Hold',-1:'Sell'})
        st.dataframe(history.sort_values('Date',ascending=False),hide_index=True)
        st.download_button('Download signals',history.to_csv(index=False),f'{symbol}_signals.csv')

elif page == 'Scenario lab':
    st.caption('Change assumptions, run a backtest, and save the result for comparison.')
    with st.form('scenario'):
        left,right = st.columns(2)
        with left:
            symbols = st.multiselect('Securities',sorted(predictions.symbol.unique()),default=sorted(predictions.symbol.unique()))
            dates = st.date_input('Period',(predictions.Date.min().date(),predictions.Date.max().date()),min_value=predictions.Date.min().date(),max_value=predictions.Date.max().date())
            capital = st.number_input('Starting capital ($)',min_value=100.,value=10000.,step=100.)
        with right:
            confidence = st.slider('Minimum signal confidence',0.,1.,0.,.05,help='Lower-confidence predictions become hold signals.')
            fee = st.number_input('Fee per order (basis points)',min_value=0.,max_value=100.,value=10.)
            slip = st.number_input('Slippage per order (basis points)',min_value=0.,max_value=100.,value=5.)
        submitted = st.form_submit_button('Run and save scenario',type='primary')
    st.caption('1 basis point = 0.01%. Each run starts in cash. Models are fixed annual models; these controls do not retrain them.')
    if submitted:
        if not symbols or len(dates)!=2:
            st.error('Choose at least one security and a complete date range.')
        else:
            chosen=predictions[predictions.symbol.isin(symbols)&predictions.Date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
            try:
                st.session_state.result=save_run(chosen,confidence,fee/10000,slip/10000,capital)
                st.session_state.portfolio_inputs=(chosen.copy(),confidence,fee/10000,slip/10000,capital)
            except ValueError as exc:
                st.error(str(exc))
    if 'result' in st.session_state:
        rid,curve,stats=st.session_state.result
        st.success(f'Saved run {rid}. Results reflect the last submitted settings.')
        cards(stats)
        chart(curve.rename(columns={'equity':'Strategy','benchmark_equity':'Buy and hold'}),['Strategy','Buy and hold'])
        if 'portfolio_inputs' in st.session_state:
            portfolio_panel(*st.session_state.portfolio_inputs,key='scenario')
        risk_panel(curve.equity, curve.benchmark_equity)
        st.download_button('Download portfolio history',curve.to_csv(),'portfolio.csv')

else:
    st.caption('Inspect saved runs and compare sensitivity to confidence, fees, and slippage.')
    scope=st.selectbox('Run group',sorted(runs.scope.unique()),index=sorted(runs.scope.unique()).index('development'))
    visible=runs[runs.scope==scope].copy()
    st.metric('Saved runs in this group',len(visible))
    if scope=='development':
        st.caption('1,000 parameter combinations on 2021–2023 data. These are sensitivity runs, not independent experiments.')
    scatter=alt.Chart(visible).mark_circle(size=65,opacity=.65).encode(x=alt.X('max_drawdown:Q',title='Maximum drawdown',axis=alt.Axis(format='.0%')),y=alt.Y('annualized_return:Q',title='Annualized return',axis=alt.Axis(format='.0%')),color=alt.Color('confidence:Q',title='Confidence',scale=alt.Scale(scheme='tealblues')),tooltip=['run_id',alt.Tooltip('annualized_return:Q',format='.1%'),alt.Tooltip('max_drawdown:Q',format='.1%'),'confidence','fee','slippage']).properties(height=320).interactive()
    st.altair_chart(scatter,width='stretch')
    ids=st.multiselect('Compare up to three runs',visible.run_id.tolist(),max_selections=3)
    if ids:
        compare=visible[visible.run_id.isin(ids)].set_index('run_id')
        st.dataframe(compare[['start','end','confidence','fee','slippage','annualized_return','benchmark_annualized_return','max_drawdown','annualized_volatility','sortino_ratio','positive_day_rate','beta','trade_count']].T.astype(str),width='stretch')
        st.caption('Check periods and assumptions before comparing. A high historical return is not a forecast.')
    with st.expander('All saved results',expanded=not bool(ids)):
        st.dataframe(visible[['run_id','start','end','confidence','fee','slippage','annualized_return','max_drawdown','trade_count']],hide_index=True)
    st.download_button('Export this group',visible.to_csv(index=False),'scenario_comparison.csv')

st.divider()
st.caption('Historical simulation • Fees and slippage included • Later-period data was previously inspected • No live prices')
