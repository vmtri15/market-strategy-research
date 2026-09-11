import pandas as pd
import streamlit as st
from src.paper.engine import initialize,connect,set_paused,run_daily


def render():
    initialize()
    st.caption('VIRTUAL ACCOUNT · No broker connection or real-money orders')
    with connect() as c:
        account=dict(c.execute('SELECT * FROM account').fetchone())
        positions=pd.read_sql('SELECT * FROM positions',c)
        snapshots=pd.read_sql('SELECT * FROM snapshots ORDER BY date',c,parse_dates=['date'])
        orders=pd.read_sql('SELECT * FROM orders ORDER BY id DESC',c)
        observed=pd.read_sql('SELECT * FROM observed_bars ORDER BY date',c,parse_dates=['date'])
        events=pd.read_sql('SELECT * FROM events ORDER BY rowid DESC LIMIT 50',c)
    st.info(('Paused' if account['paused'] else 'Enabled')+f" · Last processed session: {account['last_date'] or 'None'}")
    a,b=st.columns(2)
    if a.button('Resume paper account' if account['paused'] else 'Pause and cancel pending orders'):
        set_paused(not account['paused']);st.rerun()
    if b.button('Process latest completed session',disabled=bool(account['paused'])):
        try:
            result=run_daily()
            st.session_state['paper_status']=result
            st.rerun()
        except Exception as exc:
            st.error(f'No update completed: {exc}')
    if 'paper_status' in st.session_state:
        st.caption('Last requested update: '+st.session_state['paper_status'])
    a,b,c=st.columns(3)
    invested=(positions.shares*positions.mark).sum()
    a.metric('Virtual cash',f"${account['cash']:,.2f}")
    b.metric('Holdings at last processed close',f'${invested:,.2f}')
    c.metric('Account value',f"${account['cash']+invested:,.2f}")
    if snapshots.empty:
        st.write('No sessions processed yet. The first successful update records closing signals; eligible fills begin on a later session. Existing backtests are not imported as paper performance.')
    else:
        curve=snapshots.set_index('date')[['equity']].copy()
        curve['Buy and hold']=account['initial']
        # Benchmark invests at the first recorded opening after account inception.
        for symbol in positions.symbol:
            eligible=observed[(observed.symbol==symbol)&(observed.date>curve.index.min())]
            if not eligible.empty:
                shares=account['initial']/len(positions)/(eligible.iloc[0]['open']*1.0005*1.001)
                marks=eligible.set_index('date')['close'].reindex(curve.index).ffill()
                sleeve=(shares*marks).fillna(account['initial']/len(positions))
                curve['Buy and hold']+=sleeve-account['initial']/len(positions)
        st.line_chart(curve.rename(columns={'equity':'Paper strategy'}))
        st.caption('Benchmark starts at the first recorded opening after inception, with equal initial stock allocation and the same entry costs. Both paths mark positions at the close.')
    holdings,queue,log=st.tabs(['Holdings','Orders','Processing log'])
    with holdings:
        st.dataframe(positions,hide_index=True)
    with queue:
        st.dataframe(orders,hide_index=True)
        st.download_button('Download paper orders',orders.to_csv(index=False),'paper_orders.csv')
    with log:
        st.dataframe(events,hide_index=True)
    with st.expander('Execution rules and limitations'):
        st.write('Starts with $10,000 virtual cash. New purchases are limited to 30% of opening account equity per security and available cash. Positions may drift above this limit; there is no forced rebalance. No shorts or leverage. Fees: 0.10%; slippage: 0.05% per side.')
        st.write('Run at least one hour after market close. Prior-session signals fill at the next open, recorded retrospectively after the session closes. No intraday execution. A missed session cancels pending orders and pauses processing; review and resume to continue without inventing missed fills.')
        st.write('A frozen copy of the existing model generates signals. This is an older research model, not evidence of live profitability. Split or dividend events block updates for review; automated corporate-action accounting is not implemented. Data errors are recorded without partial trades.')
        st.caption('Frozen model SHA-256: '+account['model_hash'])
