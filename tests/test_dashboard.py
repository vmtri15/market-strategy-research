import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.models.research import PREDICTIONS

PAGES = ['Overview', 'Stock explorer', 'Scenario lab', 'Saved comparisons', 'Paper trading']


@unittest.skipUnless(PREDICTIONS.exists(), 'run make all to generate research data first')
class DashboardSmokeTest(unittest.TestCase):
    def test_every_page_renders_without_exceptions(self):
        at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app/dashboard.py'), default_timeout=90).run()
        # Without a local model (hosted copy), the paper account is hidden.
        expected = PAGES if (Path(__file__).resolve().parents[1] / 'models/model.pkl').exists() else PAGES[:-1]
        self.assertEqual([option.split('  ')[-1] for option in at.sidebar.radio[0].options], expected)
        for page in expected:
            at.sidebar.radio[0].set_value(page).run()
            self.assertEqual([e.value for e in at.exception], [], page)


if __name__ == '__main__':
    unittest.main()
