import unittest

import pandas as pd

from src.data.fetch_data import validate_prices


def frame(**changes):
    dates = pd.bdate_range('2024-01-01', periods=10)
    rows = [{'Date': d, 'open': 10., 'high': 11., 'low': 9., 'close': 10., 'volume': 1, 'symbol': s} for s in ('A', 'B') for d in dates]
    df = pd.DataFrame(rows)
    for key, (index, value) in changes.items():
        df.loc[index, key] = value
    return df


class ValidatePricesTests(unittest.TestCase):
    def test_clean_data_passes(self):
        validate_prices(frame())

    def test_rejects_bad_data(self):
        with self.assertRaises(ValueError):
            validate_prices(frame(close=(3, 0.)))
        with self.assertRaises(ValueError):
            validate_prices(frame(close=(3, 20.)))          # +100% one-day move
        with self.assertRaises(ValueError):
            validate_prices(frame().drop(index=range(3, 7)))  # gap and mismatched calendars


if __name__ == '__main__':
    unittest.main()
