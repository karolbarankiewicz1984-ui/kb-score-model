import unittest
from tools.kb21_legacy_calendar import check


class CalendarGateTests(unittest.TestCase):
    def test_empty_is_blocked(self):
        self.assertEqual(check({"date": "2026-10-15"})["status"], "BLOCKED")

    def test_mismatch_is_blocked(self):
        a = {"competition": "League", "home": "A", "away": "B", "kickoff": "2026-10-15T19:00:00+02:00"}
        b = dict(a, away="C")
        data = {"date": "2026-10-15", "official_source": {"url": "https://official.example", "retrieved_at": "now"},
                "independent_source": {"url": "https://independent.example", "retrieved_at": "now"},
                "coverage_reviewed": True, "fixtures": [{"official": a, "independent": b}]}
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_matching_sources_only_require_review(self):
        a = {"competition": "League", "home": "A", "away": "B", "kickoff": "2026-10-15T19:00:00+02:00"}
        data = {"date": "2026-10-15", "official_source": {"url": "https://official.example", "retrieved_at": "now"},
                "independent_source": {"url": "https://independent.example", "retrieved_at": "now"},
                "coverage_reviewed": True, "fixtures": [{"official": a, "independent": a}]}
        self.assertEqual(check(data)["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
