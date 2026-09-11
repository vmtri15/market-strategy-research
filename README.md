# Market Strategy Research Dashboard

A Python, SQLite, and Streamlit application for evaluating model-driven stock signals against simple investment benchmarks. It analyzes historical AAPL, MSFT, and SPY prices, lets users test trading assumptions, and supports a separate virtual paper-trading account.

This is a **research and decision-support tool**, not investment advice or a real-money trading system.

## What it answers

- Did the strategy improve returns or reduce downside relative to buy-and-hold?
- What trades would have occurred, what did they cost, and where was the portfolio invested?
- How do trading fees, slippage, and confidence thresholds affect results?
- Does the strategy meet a user's selected return and drawdown criteria?
- How does a model-timed strategy compare with holding less stock and more cash?

## Dashboard

The Streamlit app includes five pages:

| Page | Purpose |
| --- | --- |
| **Overview** | Portfolio growth, drawdowns, annual comparisons, risk metrics, and decision criteria. |
| **Stock explorer** | Historical price and Buy/Hold/Sell signal history for each security. |
| **Scenario lab** | Runs and saves custom historical simulations with selected securities, dates, costs, capital, and confidence threshold. |
| **Saved comparisons** | Compares the return-risk tradeoffs of saved scenarios. |
| **Paper trading** | Tracks a virtual account, simulated orders, holdings, and processing events using a frozen model. |

## Method

1. Downloads daily OHLCV data for AAPL, MSFT, and SPY into SQLite.
2. Builds RSI, MACD, and 20-day/50-day EMA features separately for each security.
3. Labels five-session returns as Buy (>2%), Hold, or Sell (<-2%).
4. Trains a 200-tree Random Forest model using chronological splits that purge labels crossing the test cutoff.
5. Evaluates the model through annual expanding-window walk-forward tests.
6. Simulates next-open execution with 0.10% transaction costs and 0.05% slippage per side.

## Historical findings

The saved default walk-forward comparison covers January 2024 through October 2025. It uses $10,000 of starting capital, equal initial allocation among the three securities, and no scenario selected for its later-period return.

| Metric | Strategy | Buy and hold |
| --- | ---: | ---: |
| Ending account value | $13,064 | $14,794 |
| Total return | 30.6% | 47.9% |
| Annualized return | 15.8% | 24.0% |
| Maximum drawdown | -21.3% | -23.9% |
| Sharpe ratio | 1.00 | 1.20 |

The strategy produced a smaller maximum drawdown, but did **not** outperform buy-and-hold on return. It exceeded buy-and-hold return in 1 of 5 annual walk-forward periods and had a smaller drawdown in all 5. These results are descriptive historical observations, not a forecast.

## Validation and scenario analysis

- **5 annual walk-forward periods:** 2021–2025; 2025 is partial.
- **1,000 sensitivity scenarios:** combinations of confidence thresholds, transaction fees, and slippage on 2021–2023 predictions.
- **20 automated tests:** feature isolation, label purging, execution timing, trading costs, risk metrics, trade reconciliation, paper-account limits, duplicate prevention, and pause behavior.

The 1,000 scenarios are sensitivity tests on the same historical predictions. They are not 1,000 independent models, and choosing the best historical scenario would not establish future performance.

## Run locally

```bash
git clone https://github.com/vmtri15/market-prediction-system.git
cd market-prediction-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Rebuild the historical research artifacts
make run-features
make train
make research

# Start the dashboard
make app
```

Open the local URL shown by Streamlit. To verify the codebase:

```bash
make test
```

To download fresh market data before rebuilding features, run `make run-data`. This replaces the local price database.

## Paper trading

Paper trading is a separate virtual account with $10,000 of simulated capital. It does not connect to a broker or place real orders.

```bash
# Check the current market data without changing the account
make paper-check

# Process the latest completed market session
make paper
```

The paper account uses a frozen copy of the trained model. Signals are created at a session close and can fill at the next session open. New positions are limited to 30% of opening account equity per security; shorting and leverage are disabled. The process pauses when data is missing, a split/dividend requires review, or a pending order would need to be backfilled.

## Project structure

```text
app/                 Streamlit dashboard and paper-trading page
data/                SQLite price data and generated research artifacts
reports/             Generated business report and CSV summaries
src/data/            Market-data ingestion
src/features/        Technical-indicator and target generation
src/models/          Training, backtesting, walk-forward research, and metrics
src/paper/           Virtual paper-trading engine
tests/               Automated validation
```

## Limitations

- Historical prices end in October 2025; paper-trading results begin only after account creation.
- The model confidence score is not calibrated.
- Simulations assume fractional shares, fixed fees/slippage, zero interest on cash, no taxes, and no market impact.
- Corporate actions pause the paper account for review; automated dividend and split accounting is not implemented.
- No live broker integration or real-time/intraday execution is included.

## Tech stack

Python · Pandas · scikit-learn · SQLite · yfinance · TA · Streamlit · Altair
