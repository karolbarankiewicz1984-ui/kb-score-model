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


    def test_result_page_after_kickoff_explains_schedule_disappearance_but_not_time(self):
        from copy import deepcopy
        from datetime import datetime, timezone
        o = official()
        o["by_day"]["2026-10-17"] = []
        r = {
            "schema": "kb21-knvb-results-date-pair-v1",
            "league_id": "ned.1",
            "official_url": "https://www.knvb.nl/competities/eredivisie/uitslagen",
            "days": ["2026-10-17", "2026-10-18"],
            "captured_at_utc": "2026-10-17T15:00:00+00:00",
            "errors": [], "status": "KNVB_RESULTS_DATE_PAIRS_PARTIAL",
            "calendar_gate": "BLOCKED", "prematch_calendar_verified": False,
            "official_kickoff_verified": False, "full_day_verified": False,
            "reviewer_signed": False, "confirmed_zero_matches": False,
            "by_day": {"2026-10-17": [{
                "league_id": "ned.1", "date_printed": "2026-10-17",
                "home": "ADO Den Haag", "away": "PSV",
                "kickoff_utc": None, "kickoff_time_verified": False,
                "match_result_verified": False
            }], "2026-10-18": []},
        }
        result = compare(queue(), o, results=r)
        day = result["days"]["2026-10-17"]
        self.assertEqual(day["post_start_result_date_pairs"], 1)
        self.assertEqual(day["matched"], 0)
        self.assertEqual(day["statuses"]["KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF"], 1)
        self.assertIsNone(day["comparisons"][0]["knvb_kickoff"])
        self.assertFalse(day["comparisons"][0]["kickoff_verified_from_results"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        r["captured_at_utc"] = "2026-10-17T11:30:00+00:00"
        before = compare(queue(), o, results=r)
        self.assertEqual(before["days"]["2026-10-17"]["post_start_result_date_pairs"], 0)
        self.assertEqual(before["days"]["2026-10-17"]["comparisons"][0]["status"],
                         "NOT_ON_KNVB_VISIBLE_PROGRAM")
        r["captured_at_utc"] = "2026-10-17T15:00:00+00:00"
        r["by_day"]["2026-10-17"][0]["kickoff_time_verified"] = True
        with self.assertRaisesRegex(ValueError, "Unsafe KNVB results-row"):
            compare(queue(), o, results=r)

if __name__ == "__main__":
    unittest.main()
