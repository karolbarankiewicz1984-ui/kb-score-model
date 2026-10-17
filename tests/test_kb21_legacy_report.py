import unittest
from tools.kb21_legacy_report import render


class LegacyReportTests(unittest.TestCase):
    def test_no_calendar_stays_blocked(self):
        report = render({"date": "2026-10-15", "candidates": []})
        self.assertIn("BLOCKED", report)
        self.assertIn("No recommendations", report)

    def test_xg_optional_and_no_play(self):
        report = render({"date": "2026-10-15", "calendar_verified": True,
                         "official_calendar": "https://example.org/official",
                         "independent_calendar": "https://example.org/independent",
                         "candidates": [{"fixture": "A - B", "str": 30, "qual": 28, "match": 22}]})
        self.assertIn("unavailable / not mandatory", report)
        self.assertIn("DIAGNOSTIC / NO PLAY", report)
        self.assertIn("BLOCKED / REVIEW REQUIRED", report)
        self.assertNotIn("**Calendar Gate:** PASS", report)
        self.assertNotIn("**Publication status:** PLAY", report)

    def test_rejects_invalid_candidates(self):
        with self.assertRaises(ValueError):
            render({"date": "2026-10-15", "candidates": {}})


if __name__ == "__main__":
    unittest.main()
