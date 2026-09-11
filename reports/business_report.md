# Business performance report

## Decision question
Does this model justify its added complexity compared with buying and holding an equally allocated AAPL, MSFT, and SPY portfolio?

## Executive finding
The default strategy did not beat buy-and-hold on annualized return. Retain it as a research prototype for studying downside tradeoffs; these results do not support replacing the benchmark.

## Comparable results: 2024-01-02 through 2025-10-29
These results use the fixed default annual walk-forward models, not the original single-split backtest or the best scenario from the grid.

| Measure | Strategy | Buy and hold |
|---|---:|---:|
| Starting capital | $10,000 | $10,000 |
| Ending account value | $13,064 | $14,794 |
| Total return | 30.6% | 47.9% |
| Annualized return | 15.8% | 24.0% |
| Maximum drawdown | -21.3% | -23.9% |
| Sharpe ratio | 1.00 | 1.20 |

Annualized return difference: **-8.2 percentage points**. Drawdown reduction: **+2.6 percentage points** (positive means a smaller peak-to-trough decline). Ending-value difference: **$-1,730** on the same starting capital.

## Consistency across periods
The default strategy exceeded benchmark total return in **1 of 5 annual periods** and had a smaller maximum drawdown in **5 of 5 periods**. Each annual comparison starts with fresh capital; 2025 is partial. These observations are descriptive, not a statistical significance test.

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
- Source: SQLite research.db, fixed run 42768b6ddf0e7a450ff4. Saved data ends in October 2025; this is a historical report.
