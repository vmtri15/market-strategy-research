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
from src.models.research import PREDICTIONS, DB, list_runs, save_run
from src.models.business_report import build_report
from components import chart, cards, risk_panel, portfolio_panel

st.set_page_config(page_title='Market Lab | Strategy Explorer', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem; padding-bottom:3rem; max-width:1440px;}
h1 {letter-spacing:-1.5px; font-weight:750 !important;}
[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.25); border-radius:12px; padding:16px 18px; background:rgba(128,128,128,.04);}
[data-testid="stMetricLabel"] p {font-size:.75rem; text-transform:uppercase; letter-spacing:.03em; opacity:.75; white-space:normal;}
[data-testid="stMetricValue"] {font-weight:700; font-size:clamp(1.2rem,2.2vw,2rem); overflow:visible;}
[data-testid="stMetricValue"] > div {overflow:visible; text-overflow:clip; white-space:normal;}
[data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.25);}
h2, h3 {margin-top:1.5rem !important;}
[data-baseweb="tab-list"] {gap:.5rem;}
footer, #MainMenu {visibility:hidden;}
@media (max-width:640px) {
  .block-container {padding:1rem .75rem 2rem;}
  [data-testid="stMetric"] {padding:10px 12px;}
  h1 {font-size:1.7rem !important;}
}
</style>''', unsafe_allow_html=True)


st.sidebar.markdown('## MARKET LAB')
st.sidebar.caption('Strategy research workspace')
ICONS = {'Overview':'🏠','Stock explorer':'🔎','Scenario lab':'🧪','Saved comparisons':'🗂️','Paper trading':'📝'}
page = st.sidebar.radio('Explore', list(ICONS), format_func=lambda name: f'{ICONS[name]}  {name}')
st.sidebar.divider()
@st.cache_data
def data_status(mtime):
    frame = pd.read_csv(PREDICTIONS, usecols=['Date', 'symbol'], parse_dates=['Date'])
    return ' · '.join(sorted(frame.symbol.unique())), frame.Date.max().date()


if PREDICTIONS.exists():
    names, last = data_status(PREDICTIONS.stat().st_mtime)
    st.sidebar.caption(f'{names}\n\nHistorical research • Prices through {last:%b %d, %Y}')
st.title(f'{ICONS[page]} {page}')
if page == 'Paper trading':
    from paper_page import render
    render()
    st.stop()
if not PREDICTIONS.exists():
    st.warning('No research data yet. Run `make research` in the project folder, then refresh this page.')
    st.stop()
predictions = pd.read_csv(PREDICTIONS, parse_dates=['Date'])
runs = list_runs()
for metric_key in ['annualized_volatility','sortino_ratio','positive_day_rate','beta']:
    if metric_key not in runs.columns:
        runs[metric_key] = float('nan')
if runs.empty:
    st.warning('No saved research runs. Run `make research` first, or save one from the Scenario lab.')
    st.stop()

if page == 'Overview':
    text, annual, sensitivity, base = build_report(runs)
    st.caption(f"DEFAULT WALK-FORWARD STRATEGY  /  {base.start} — {base.end}")
    with sqlite3.connect(DB) as conn:
        curve = pd.read_sql('SELECT date, equity, benchmark FROM curves WHERE run_id=? ORDER BY date', conn, params=[base.run_id], parse_dates=['date']).set_index('date')
    dd = curve / curve.cummax() - 1
    st.subheader(f"{base.annualized_return:.1%} a year vs {base.benchmark_annualized_return:.1%} for buy-and-hold")
    st.write(f"Worst drawdown {dd.equity.min():.1%} vs {dd.benchmark.min():.1%}. Historical results only, not a forecast.")
    cards(base)
    growth, criteria, money, risk, yearly, report = st.tabs(['Growth', 'Criteria check', 'Holdings & trades', 'Risk', 'Year by year', 'Report'])
    with growth:
        balance, downside = st.tabs(['Portfolio growth', 'Drawdown'])
        with balance:
            chart(curve.rename(columns={'equity':'Strategy', 'benchmark':'Buy and hold'}), ['Strategy','Buy and hold'])
        with downside:
            chart(dd.rename(columns={'equity':'Strategy', 'benchmark':'Buy and hold'}), ['Strategy','Buy and hold'], True)
    portfolio_panel(predictions[predictions.Date.between(pd.Timestamp(base.start),pd.Timestamp(base.end))], base.confidence,base.fee,base.slippage,base.capital,key='overview',containers=(criteria,money))
    with risk:
        risk_panel(curve.equity, curve.benchmark)
    with yearly:
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
    with report:
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
        st.dataframe(history.sort_values('Date',ascending=False),hide_index=True,width='stretch',
                     column_config={'close':st.column_config.NumberColumn('Close',format='dollar'),'confidence':st.column_config.ProgressColumn('Confidence',min_value=0,max_value=1,format='percent')})
        st.download_button('Download signals',history.to_csv(index=False),f'{symbol}_signals.csv')

elif page == 'Scenario lab':
    st.caption('Change assumptions, run a backtest, and save the result for comparison.')
    form_col, result_col = st.columns([1,2], gap='large')
    with form_col, st.form('scenario'):
        symbols = st.multiselect('Securities',sorted(predictions.symbol.unique()),default=sorted(predictions.symbol.unique()))
        dates = st.date_input('Period',(predictions.Date.min().date(),predictions.Date.max().date()),min_value=predictions.Date.min().date(),max_value=predictions.Date.max().date())
        capital = st.number_input('Starting capital ($)',min_value=100.,value=10000.,step=100.)
        confidence = st.slider('Minimum signal confidence',0.,1.,0.,.05,help='Lower-confidence predictions become hold signals.')
        fee = st.number_input('Fee per order (basis points)',min_value=0.,max_value=100.,value=10.)
        slip = st.number_input('Slippage per order (basis points)',min_value=0.,max_value=100.,value=5.)
        submitted = st.form_submit_button('Run and save scenario',type='primary')
        st.caption('1 basis point = 0.01%. Each run starts in cash. Models are fixed annual models; these controls do not retrain them.')
    with result_col:
        if submitted:
            if not symbols or len(dates)!=2:
                st.error('Choose at least one security and a complete date range.')
            else:
                chosen=predictions[predictions.symbol.isin(symbols)&predictions.Date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
                try:
                    with st.spinner('Running backtest...'):
                        st.session_state.result=save_run(chosen,confidence,fee/10000,slip/10000,capital)
                        st.session_state.portfolio_inputs=(chosen.copy(),confidence,fee/10000,slip/10000,capital)
                except ValueError as exc:
                    st.error(str(exc))
        if 'result' in st.session_state:
            rid,curve,stats=st.session_state.result
            st.success(f'Saved run {rid}. Results reflect the last submitted settings.')
            cards(stats)
            growth, criteria, money, risk = st.tabs(['Growth', 'Criteria check', 'Holdings & trades', 'Risk'])
            with growth:
                chart(curve.rename(columns={'equity':'Strategy','benchmark_equity':'Buy and hold'}),['Strategy','Buy and hold'])
                st.download_button('Download portfolio history',curve.to_csv(),'portfolio.csv')
            if 'portfolio_inputs' in st.session_state:
                portfolio_panel(*st.session_state.portfolio_inputs,key='scenario',containers=(criteria,money))
            with risk:
                risk_panel(curve.equity, curve.benchmark_equity)
        else:
            st.info('Pick your assumptions on the left and run a scenario to see results here.')

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
        pct = lambda label: st.column_config.NumberColumn(label, format='percent')
        st.dataframe(visible[['run_id','start','end','confidence','fee','slippage','annualized_return','max_drawdown','trade_count']],hide_index=True,width='stretch',
                     column_config={'annualized_return':pct('Annualized return'),'max_drawdown':pct('Max drawdown'),'fee':st.column_config.NumberColumn('Fee',format='percent'),'slippage':st.column_config.NumberColumn('Slippage',format='percent'),'confidence':st.column_config.ProgressColumn('Confidence',min_value=0,max_value=1,format='percent'),'trade_count':st.column_config.NumberColumn('Orders',format='%d')})
    st.download_button('Export this group',visible.to_csv(index=False),'scenario_comparison.csv')

st.divider()
st.caption('Historical simulation • Fees and slippage included • Later-period data was previously inspected • No live prices')
