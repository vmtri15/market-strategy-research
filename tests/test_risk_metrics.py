import unittest
import numpy as np
import pandas as pd
from src.models.risk_metrics import risk_metrics


class RiskMetricsTests(unittest.TestCase):
    def test_known_returns(self):
        prices = pd.Series([100.,110.,99.,99.,108.9],index=pd.date_range('2020-01-01',periods=5))
        result=risk_metrics(prices,prices)
        self.assertAlmostEqual(result['positive_day_rate'],.5)
        self.assertAlmostEqual(result['annualized_volatility'],np.std([.1,-.1,0,.1],ddof=1)*np.sqrt(252))
        self.assertAlmostEqual(result['sortino_ratio'],.025/.05*np.sqrt(252))
        self.assertAlmostEqual(result['expected_shortfall_return'],-.1)
        self.assertEqual(result['longest_underwater_sessions'],3)
        self.assertAlmostEqual(result['beta'],1.)
        self.assertAlmostEqual(result['benchmark_correlation'],1.)
        self.assertIsNone(result['information_ratio'])

    def test_flat_and_short_series(self):
        flat=pd.Series([100.]*4,index=pd.date_range('2020-01-01',periods=4))
        result=risk_metrics(flat,flat)
        self.assertEqual(result['annualized_volatility'],0)
        self.assertIsNone(result['sortino_ratio'])
        self.assertIsNone(result['calmar_ratio'])
        self.assertIsNone(result['beta'])
        self.assertEqual(result['positive_day_rate'],0)
        self.assertEqual(result['longest_underwater_sessions'],0)
        self.assertEqual(risk_metrics(flat.iloc[:1]),{})
