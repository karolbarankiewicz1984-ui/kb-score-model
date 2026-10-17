import unittest
from tools.kb21_readiness_summary import render

class ReadinessSummaryTests(unittest.TestCase):
    def test_blocked_and_no_calendar(self):
        report = render({"date": "2030-01-01", "total": 2, "blocked": 2, "ready_for_review": 0,
                         "blocker_counts": {"OFFICIAL_FIXTURE_UNVERIFIED": 2},
                         "warning_counts": {"MISSING_HOME_EXPECTED_GOALS": 2}})
        self.assertIn("Blocked: 2", report)
        self.assertIn("OFFICIAL_FIXTURE_UNVERIFIED: 2", report)
        self.assertIn("MISSING_HOME_EXPECTED_GOALS: 2", report)
        self.assertIn("xG is OPTIONAL", report)
        self.assertIn("Historical N changes: 0", report)
        self.assertIn("No independent calendar", report)

    def test_calendar_is_review_only(self):
        report = render({"date": "2030-01-01"}, {"rows": [{"independent_match": True}, {"independent_match": False}]})
        self.assertIn("1 / 2", report)
        self.assertIn("not PLAY", report)

if __name__ == "__main__":
    unittest.main()
