import unittest
import numpy as np
import pandas as pd
from src.features.build_features import add_indicators
from src.models.train_model import split_data
from src.models.backtest import simulate_symbol, metrics


class PipelineTests(unittest.TestCase):
    def test_indicators_do_not_cross_symbols(self):
        dates = pd.date_range('2020-01-01', periods=80)
        a = pd.DataFrame({'Date': dates, 'symbol': 'A', 'close': np.arange(80) + 100.})
        b = pd.DataFrame({'Date': dates, 'symbol': 'B', 'close': np.arange(80) + 1000.})
        combined = add_indicators(pd.concat([a, b]))
        expected = add_indicators(b)
        np.testing.assert_allclose(combined[combined.symbol == 'B'].ema_50, expected.ema_50, equal_nan=True)

    def test_split_purges_future_labels(self):
        dates = pd.date_range('2020-01-01', periods=100)
        df = pd.DataFrame({'Date': dates, 'target_date': dates + pd.Timedelta(days=5), 'future_return': 0.1})
        train, test, cutoff = split_data(df)
        self.assertTrue((train.target_date < cutoff).all())
        self.assertTrue((test.Date >= cutoff).all())
        self.assertEqual(len(train), 75)

    def test_next_open_and_both_side_costs(self):
        df = pd.DataFrame({'Date': pd.date_range('2020-01-01', periods=3),
                           'open': [10., 20., 30.], 'close': [10., 20., 30.],
                           'predicted_signal': [1, -1, 0]})
        result = simulate_symbol(df, 1000, 0.01, 0.01)
        self.assertEqual(result.equity.iloc[0], 1000)
        shares = 1000 / (20 * 1.01 * 1.01)
        self.assertAlmostEqual(result.equity.iloc[-1], shares * 30 * .99 * .99)
        self.assertEqual(result.trade_count.iloc[-1], 2)
        other = simulate_symbol(df.assign(predicted_signal=0), 1000, .01, .01)
        self.assertTrue((other.equity == 1000).all())

    def test_metrics_drawdown(self):
        equity = pd.Series([100., 120., 90., 110.], index=pd.date_range('2020-01-01', periods=4))
        result = metrics(equity, 100)
        self.assertAlmostEqual(result['max_drawdown'], -.25)
        self.assertAlmostEqual(result['total_return'], .10)


if __name__ == '__main__':
    unittest.main()
