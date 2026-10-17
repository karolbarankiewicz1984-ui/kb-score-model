import unittest
from tools.kb21_knvb_compare import compare, render


def official():
    return {
        "schema": "kb21-official-knvb-eredivisie-v1", "league_id": "ned.1",
        "days": ["2026-10-17", "2026-10-18"],
        "official_url": "https://www.knvb.nl/competities/eredivisie/programma",
        "errors": [], "unconfirmed_zero_dates": ["2026-10-18"],
        "by_day": {
            "2026-10-17": [{
                "home": "ADO Den Haag", "away": "PSV",
                "kickoff_utc": "2026-10-17T14:30:00+00:00",
                "kickoff_warsaw": "2026-10-17T16:30:00+02:00",
            }],
            "2026-10-18": [],
        },
    }


def queue(kickoff="2026-10-17T16:30:00+02:00"):
    return {
        "days": ["2026-10-17", "2026-10-18"],
        "fixtures": [{
            "fixture_id": "ned.1:10", "fixture": "ADO Den Haag - PSV",
            "kickoff": kickoff, "date_warsaw": "2026-10-17",
        }],
    }


class CompareKNVBTests(unittest.TestCase):
    def test_match_remains_unapproved(self):
        report = compare(queue(), official())
        self.assertEqual(report["days"]["2026-10-17"]["matched"], 1)
        self.assertFalse(report["reviewer_signed"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertIn("NO PLAY", render(report))

    def test_time_discrepancy_reported(self):
        report = compare(queue("2026-10-17T17:30:00+02:00"), official())
        row = report["days"]["2026-10-17"]
        self.assertEqual(row["matched"], 0)
        self.assertEqual(row["statuses"]["START_TIME_CONFLICT"], 1)

    def test_blank_day_is_not_approved_no_games(self):
        report = compare(queue(), official())
        self.assertFalse(report["days"]["2026-10-18"]["day_found_in_knvb_page"])
        self.assertIn("NIE potwierdzono zera spotkań", render(report))

    def test_scope_mismatch_fails(self):
        wrong = official()
        wrong["days"] = ["2026-10-18"]
        with self.assertRaises(ValueError):
            compare(queue(), wrong)


if __name__ == "__main__":
    unittest.main()
