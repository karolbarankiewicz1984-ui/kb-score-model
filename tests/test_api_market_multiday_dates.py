import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from api_market_multiday_dates import scan_dates

class MultiDayDatesTests(unittest.TestCase):
    def test_friday_through_sunday(self):
        self.assertEqual(scan_dates(date(2026, 10, 9)), ["2026-10-09", "2026-10-10", "2026-10-11"])
    def test_cross_month(self):
        self.assertEqual(scan_dates(date(2026, 10, 31), 2), ["2026-10-31", "2026-11-01"])
    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            scan_dates(date(2026, 10, 9), 8)

if __name__ == "__main__":
    unittest.main()
