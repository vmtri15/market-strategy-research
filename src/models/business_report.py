"""Decision-focused reporting from saved, fixed-parameter research runs."""
from pathlib import Path
from src.models.research import ROOT, list_runs


def build_report(runs):
    defaults = runs[runs.scope == 'later_period_default']
    if len(defaults) != 1:
        raise ValueError('Expected one later-period default run; regenerate research outputs.')
    base = defaults.iloc[0]
    annual = runs[runs.scope.str.startswith('annual_default_')].copy().sort_values('start')
    dev = runs[runs.scope == 'development'].copy()
    if annual.empty or dev.empty:
        raise ValueError('Annual and development scenarios are required.')
    annual['Period'] = annual.scope.str.replace('annual_default_', '', regex=False)
    annual['Strategy return (%)'] = annual.total_return * 100
    annual['Buy-and-hold return (%)'] = annual.benchmark_total_return * 100
    annual['Strategy maximum drawdown (%)'] = annual.max_drawdown * 100
    annual['Buy-and-hold maximum drawdown (%)'] = annual.benchmark_max_drawdown * 100
    annual['Return difference (pp)'] = (annual.total_return - annual.benchmark_total_return) * 100
    annual['Drawdown reduction (pp)'] = (annual.max_drawdown - annual.benchmark_max_drawdown) * 100
    annual['Period'] += annual.apply(lambda r: ' (partial)' if r.end[5:7] != '12' else '', axis=1)
    yearly = annual[['Period', 'start', 'end', 'Strategy return (%)', 'Buy-and-hold return (%)', 'Strategy maximum drawdown (%)', 'Buy-and-hold maximum drawdown (%)', 'Return difference (pp)', 'Drawdown reduction (pp)']]
    dev['excess_return'] = dev.annualized_return - dev.benchmark_annualized_return
    sensitivity = dev.groupby('confidence').agg(scenarios=('run_id', 'count'),
        minimum_annualized_return=('annualized_return', 'min'), median_annualized_return=('annualized_return', 'median'),
        maximum_annualized_return=('annualized_return', 'max'), worst_drawdown=('max_drawdown', 'min'),
        median_excess_return=('excess_return', 'median')).reset_index()
    strategy_end = base.capital * (1 + base.total_return)
    benchmark_end = base.capital * (1 + base.benchmark_total_return)
    wins = int((annual.total_return > annual.benchmark_total_return).sum())
    smaller = int((annual.max_drawdown > annual.benchmark_max_drawdown).sum())
    gap = (base.annualized_return - base.benchmark_annualized_return) * 100
    reduction = (base.max_drawdown - base.benchmark_max_drawdown) * 100
    decision = ('The default strategy did not beat buy-and-hold on annualized return. Retain it as a research prototype for studying downside tradeoffs; these results do not support replacing the benchmark.'
                if gap <= 0 else 'The default strategy exceeded buy-and-hold in this observed period. Validate the result on new, uninspected data before treating it as a repeatable advantage.')
    text = f'''# Business performance report

## Decision question
Does this model justify its added complexity compared with buying and holding an equally allocated AAPL, MSFT, and SPY portfolio?

## Executive finding
{decision}

## Comparable results: {base.start} through {base.end}
These results use the fixed default annual walk-forward models, not the original single-split backtest or the best scenario from the grid.

| Measure | Strategy | Buy and hold |
|---|---:|---:|
| Starting capital | ${base.capital:,.0f} | ${base.capital:,.0f} |
| Ending account value | ${strategy_end:,.0f} | ${benchmark_end:,.0f} |
| Total return | {base.total_return:.1%} | {base.benchmark_total_return:.1%} |
| Annualized return | {base.annualized_return:.1%} | {base.benchmark_annualized_return:.1%} |
| Maximum drawdown | {base.max_drawdown:.1%} | {base.benchmark_max_drawdown:.1%} |
| Sharpe ratio | {base.sharpe_ratio:.2f} | {base.benchmark_sharpe_ratio:.2f} |

Annualized return difference: **{gap:+.1f} percentage points**. Drawdown reduction: **{reduction:+.1f} percentage points** (positive means a smaller peak-to-trough decline). Ending-value difference: **${strategy_end - benchmark_end:+,.0f}** on the same starting capital.

## Consistency across periods
The default strategy exceeded benchmark total return in **{wins} of {len(annual)} annual periods** and had a smaller maximum drawdown in **{smaller} of {len(annual)} periods**. Each annual comparison starts with fresh capital; 2025 is partial. These observations are descriptive, not a statistical significance test.

## Sensitivity analysis
**{len(dev):,} development scenarios** vary confidence thresholds, transaction fees, and slippage on 2021–2023 predictions. Returns are summarized within each confidence threshold across the cost assumptions. The ranges are sensitivity ranges, not confidence intervals or probabilities. No winning configuration is selected for the later-period comparison.

## Proposed next decision
Define an acceptable return sacrifice for a smaller drawdown before evaluating additional data. Compare the model against a simple lower-equity-exposure benchmark to determine whether holding cash explains the apparent risk benefit. Then assess the fixed rule on new data and record whether it meets those predeclared criteria.

## Definitions and boundaries
- Annualized return expresses growth as a yearly compound rate; total return is the actual change over the displayed period.
- Maximum drawdown is the largest decline from a previous account-value peak.
- Sharpe compares average daily returns with their variability, using a zero risk-free rate.
- Both sides include {base.fee:.2%} transaction fees and {base.slippage:.2%} slippage per order. The benchmark pays entry costs; open positions are marked to close, without forced exit fees.
- Fractional shares, no taxes, no interest on cash, and no market-impact model. Original saved price-adjustment provenance is unverified.
- Later-period data was already inspected during development; it is not a pristine final test. Scenario runs reuse historical predictions and are not independent experiments.
- Source: SQLite research.db, fixed run {base.run_id}. Saved data ends in October 2025; this is a historical report.
'''
    return text, yearly, sensitivity, base


def main():
    text, annual, sensitivity, _ = build_report(list_runs())
    folder = ROOT / 'reports'
    folder.mkdir(exist_ok=True)
    (folder / 'business_report.md').write_text(text)
    annual.to_csv(folder / 'annual_comparison.csv', index=False)
    sensitivity.to_csv(folder / 'scenario_sensitivity.csv', index=False)
    print('Generated business report and two reporting tables in reports/')


if __name__ == '__main__':
    main()
