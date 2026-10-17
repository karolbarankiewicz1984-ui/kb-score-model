import unittest
from tools.kb21_portugal_postponed_compare import compare, render


def source():
    return {
        "schema": "kb21-official-portugal-club-postponement-v1",
        "league_id": "por.1", "days": ["2026-10-18", "2026-10-19"],
        "source_comparison": "DISPLAY_TIMEZONE_NOT_STATED",
        "by_day": {"2026-10-18": [],
                   "2026-10-19": [{
                       "home": "SC Braga", "away": "Gil Vicente FC",
                       "kickoff_utc": "2026-10-19T19:15:00+00:00",
                       "kickoff_warsaw": "2026-10-19T21:15:00+02:00"}]},
        "errors": [],
    }


def queue(kickoff="2026-10-19T21:15:00+02:00"):
    return {"days": ["2026-10-18", "2026-10-19"], "fixtures": [{
        "fixture_id": "por.1:10", "fixture": "Braga - Gil Vicente",
        "date_warsaw": "2026-10-19", "kickoff": kickoff,
    }]}


class PortugalComparisonTests(unittest.TestCase):
    def test_gil_official_time_matches_espn_but_not_calendar_approval(self):
        report = compare(queue(), source())
        self.assertEqual(report["days"]["2026-10-19"]["matched"], 1)
        self.assertEqual(report["club_time_display"], "DISPLAY_TIMEZONE_NOT_STATED")
        self.assertFalse(report["human_approved"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_esnp_kickoff_conflict_with_gil_article(self):
        report = compare(queue("2026-10-19T20:15:00+02:00"), source())
        self.assertEqual(report["days"]["2026-10-19"]["matched"], 0)
        self.assertEqual(report["days"]["2026-10-19"]["statuses"]
                         ["START_TIME_CONFLICT_WITH_GIL_ARTICLE"], 1)

    def test_single_club_article_not_zero_certificate(self):
        report = compare(queue(), source())
        self.assertTrue(report["days"]["2026-10-18"]["unconfirmed_zero_day"])
        self.assertIn("niepotwierdzony brak meczów", render(report))

    def test_date_scope_mismatch_rejected(self):
        s = source()
        s["days"] = ["2026-10-19"]
        with self.assertRaises(ValueError):
            compare(queue(), s)

    def test_unmatched_source_fixture_visible(self):
        q = queue()
        q["fixtures"] = []
        report = compare(q, source())
        self.assertEqual(report["days"]["2026-10-19"]["statuses"]
                         ["GIL_ARTICLE_ONLY"], 1)
        self.assertEqual(report["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
