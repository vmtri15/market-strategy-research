import tempfile
import unittest
from pathlib import Path
import pandas as pd
from src.models.research import annual_splits, evaluate, save_run, list_runs


class ResearchTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame({'Date': pd.date_range('2021-01-01', periods=4), 'symbol': ['A'] * 4,
                             'open': [10., 11., 12., 13.], 'close': [10., 11., 12., 13.],
                             'predicted_signal': [1, 0, -1, 0], 'confidence': [.6] * 4})

    def test_each_fold_purges_labels_and_test_dates_do_not_overlap(self):
        dates = pd.date_range('2019-01-01', '2023-12-31')
        df = pd.DataFrame({'Date': dates, 'target_date': dates + pd.Timedelta(days=5), 'future_return': .1})
        seen = set()
        for year, train, test in annual_splits(df):
            self.assertLess(train.target_date.max(), pd.Timestamp(f'{year}-01-01'))
            self.assertFalse(seen.intersection(test.Date))
            seen.update(test.Date)
        self.assertEqual(len(seen), 1095)

    def test_confidence_filters_trades(self):
        curve, stats = evaluate(self.sample(), confidence=.7)
        self.assertEqual(stats['trade_count'], 0)
        self.assertTrue((curve.equity == 10000).all())

    def test_cost_increase_reduces_equity(self):
        low, _ = evaluate(self.sample(), fee=0, slippage=0)
        high, _ = evaluate(self.sample(), fee=.01, slippage=.01)
        self.assertLess(high.equity.iloc[-1], low.equity.iloc[-1])

    def test_saved_runs_are_reproducible_and_unique(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'research.db'
            first, _, _ = save_run(self.sample(), db=db)
            second, _, _ = save_run(self.sample(), db=db)
            self.assertEqual(first, second)
            self.assertEqual(len(list_runs(db)), 1)
            save_run(self.sample(), confidence=.7, db=db)
            self.assertEqual(len(list_runs(db)), 2)

    def test_reject_empty_period(self):
        with self.assertRaises(ValueError):
            evaluate(self.sample().iloc[:0])
