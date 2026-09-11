import unittest
import pandas as pd
from src.models.portfolio_details import portfolio_details
from src.models.research import evaluate


class PortfolioDetailsTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame({'Date':pd.date_range('2021-01-01',periods=3),'symbol':['A']*3,'open':[10.,20.,30.],'close':[10.,21.,29.],'predicted_signal':[1,-1,0],'confidence':[.7,.8,.9]})

    def test_cash_fees_and_previous_signal(self):
        history,ledger,composition,summary=portfolio_details(self.sample(),fee=.01,slippage=.01,capital=1000)
        self.assertEqual(len(ledger),2)
        self.assertEqual(ledger.iloc[0].signal_date,pd.Timestamp('2021-01-01'))
        self.assertEqual(ledger.iloc[0].execution_confidence,.7)
        buy=ledger.iloc[0]
        self.assertAlmostEqual(buy.quantity*buy.execution_price+buy.fee,1000)
        sell=ledger.iloc[1]
        self.assertAlmostEqual(sell.quantity*sell.execution_price-sell.fee,sell.cash)
        self.assertAlmostEqual(summary.net_gain.sum(),composition.iloc[-1].sum()-1000)
        curve,_=evaluate(self.sample(),fee=.01,slippage=.01,capital=1000)
        pd.testing.assert_series_equal(composition.sum(axis=1),curve.equity,check_names=False)

    def test_no_trades(self):
        _,ledger,composition,summary=portfolio_details(self.sample(),confidence=.95,capital=1000)
        self.assertTrue(ledger.empty)
        self.assertTrue((composition.Cash==1000).all())
        self.assertEqual(summary.fees.sum(),0)
