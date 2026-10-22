# Business performance report

## Decision question
Does this model justify its added complexity compared with buying and holding an equally allocated AAPL, MSFT, and SPY portfolio?

## Executive finding
The default strategy did not beat buy-and-hold on annualized return. Retain it as a research prototype for studying downside tradeoffs; these results do not support replacing the benchmark.

## Comparable results: 2024-01-02 through 2026-10-22
These results use the fixed default annual walk-forward models, not the original single-split backtest or the best scenario from the grid.

| Measure | Strategy | Buy and hold |
|---|---:|---:|
| Starting capital | $10,000 | $10,000 |
| Ending account value | $13,887 | $16,750 |
| Total return | 38.9% | 67.5% |
| Annualized return | 12.4% | 20.2% |
| Maximum drawdown | -19.1% | -23.9% |
| Sharpe ratio | 0.90 | 1.10 |

Annualized return difference: **-7.8 percentage points**. Drawdown reduction: **+4.8 percentage points** (positive means a smaller peak-to-trough decline). Ending-value difference: **$-2,863** on the same starting capital.

## Consistency across periods
The default strategy exceeded benchmark total return in **1 of 6 annual periods** and had a smaller maximum drawdown in **6 of 6 periods**. Each annual comparison starts with fresh capital; the latest period is partial. These observations are descriptive, not a statistical significance test.

## Sensitivity analysis
**1,000 development scenarios** vary confidence thresholds, transaction fees, and slippage on 2021–2023 predictions. Returns are summarized within each confidence threshold across the cost assumptions. The ranges are sensitivity ranges, not confidence intervals or probabilities. No winning configuration is selected for the later-period comparison.

## Proposed next decision
Define an acceptable return sacrifice for a smaller drawdown before evaluating additional data. Compare the model against a simple lower-equity-exposure benchmark to determine whether holding cash explains the apparent risk benefit. Then assess the fixed rule on new data and record whether it meets those predeclared criteria.

## Definitions and boundaries
- Annualized return expresses growth as a yearly compound rate; total return is the actual change over the displayed period.
- Maximum drawdown is the largest decline from a previous account-value peak.
- Sharpe compares average daily returns with their variability, using a zero risk-free rate.
- Both sides include 0.10% transaction fees and 0.05% slippage per order. The benchmark pays entry costs; open positions are marked to close, without forced exit fees.
- Fractional shares, no taxes, no interest on cash, and no market-impact model. Original saved price-adjustment provenance is unverified.
- Later-period data was already inspected during development; it is not a pristine final test. Scenario runs reuse historical predictions and are not independent experiments.
- Source: SQLite research.db, fixed run b687386d26079fb73f6d. Saved data ends 2026-10-22; this is a historical report.
