import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGES = ['Overview', 'Stock explorer', 'Scenario lab', 'Saved comparisons', 'Paper trading']


class DashboardSmokeTest(unittest.TestCase):
    def test_every_page_renders_without_exceptions(self):
        at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app/dashboard.py'), default_timeout=90).run()
        for page in PAGES:
            at.sidebar.radio[0].set_value(page).run()
            self.assertEqual([e.value for e in at.exception], [], page)


if __name__ == '__main__':
    unittest.main()
