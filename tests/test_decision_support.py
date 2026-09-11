import unittest
import pandas as pd
from src.models.decision_support import stock_cash_benchmark,criteria_table


class DecisionSupportTests(unittest.TestCase):
    def test_cash_and_full_stock_endpoints(self):
        stock=pd.Series([100.,80.,120.],index=pd.to_datetime(['2020-01-01','2020-06-01','2021-01-01']))
        pd.testing.assert_series_equal(stock_cash_benchmark(stock,100,1),stock)
        self.assertTrue((stock_cash_benchmark(stock,100,0)==100).all())
        mixed=stock_cash_benchmark(stock,100,.6)
        self.assertEqual(mixed.tolist(),[100.,88.,112.])

    def test_thresholds_and_drawdown_sign(self):
        curves=pd.DataFrame({'Strategy':[100.,80.,120.],'Cash':[100.,100.,100.]},index=pd.to_datetime(['2020-01-01','2020-06-01','2021-01-01']))
        result=criteria_table(curves,100,.1,.15)
        self.assertEqual(result.iloc[0]['Return target'],'Met')
        self.assertEqual(result.iloc[0]['Drawdown limit'],'Missed')
        self.assertEqual(result.iloc[1]['Return target'],'Missed')
        self.assertEqual(result.iloc[1]['Drawdown limit'],'Met')
        self.assertTrue((result.Overall=='Not met').all())
        result=criteria_table(curves,100,0,0)
        self.assertEqual(result.iloc[1].Overall,'Both met')

    def test_short_period_and_invalid_allocation(self):
        curves=pd.DataFrame({'Cash':[100.]},index=pd.to_datetime(['2020-01-01']))
        self.assertEqual(criteria_table(curves,100,0,.15).iloc[0].Overall,'Unavailable')
        with self.assertRaises(ValueError):
            stock_cash_benchmark(curves.Cash,100,1.1)
