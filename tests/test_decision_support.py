import unittest
import numpy as np
import pandas as pd
from src.models.decision_support import stock_cash_benchmark,criteria_table,vol_target_benchmark


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


class VolTargetTests(unittest.TestCase):
    def setUp(self):
        self.index=pd.bdate_range('2020-01-01',periods=120)

    def test_calm_market_is_fully_invested_and_starts_in_cash(self):
        calm=pd.Series(100*1.0002**np.arange(120),index=self.index)  # zero volatility
        curve=vol_target_benchmark(calm,1000,.15)
        self.assertEqual(curve.iloc[0],1000)
        self.assertEqual(curve.iloc[:20].nunique(),1)             # cash until the window fills
        self.assertGreater(curve.iloc[-1],1000)

    def test_turbulent_market_reduces_exposure(self):
        rng=pd.Series(np.where(np.arange(120)%2,1.05,.95)).cumprod()*100
        wild=pd.Series(rng.values,index=self.index)
        stock=wild/wild.iloc[0]*1000
        curve=vol_target_benchmark(stock,1000,.10)
        self.assertLess(curve.pct_change().abs().max(),stock.pct_change().abs().max())

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            vol_target_benchmark(pd.Series([1.,2.]),100,0)
