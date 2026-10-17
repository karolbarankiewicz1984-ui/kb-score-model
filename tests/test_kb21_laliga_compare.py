import unittest
from tools.kb21_laliga_compare import compare


def official():
    return {"schema": "kb21-official-laliga-matchday-html-v1", "league_id": "esp.1",
            "days": ["2026-10-17"], "captured_at_utc": "2026-10-17T10:00:00+00:00",
            "by_day": {"2026-10-17": [{"home": "Real Betis", "away": "FC Barcelona",
              "kickoff_utc": "2026-10-17T16:30:00+00:00", "kickoff_warsaw": "2026-10-17T18:30:00+02:00"}]},
            "errors": [], "calendar_gate": "BLOCKED"}


def queue(kick="2026-10-17T18:30:00+02:00"):
    return {"days": ["2026-10-17"], "fixtures": [{
        "fixture_id": "esp.1:123", "fixture": "Real Betis - Barcelona",
        "date_warsaw": "2026-10-17", "kickoff": kick}]}


class LaLigaCompareTests(unittest.TestCase):
    def test_same_clubs_and_kickoff_remain_review_only(self):
        report = compare(queue(), official())
        self.assertEqual(report["days"]["2026-10-17"]["matched"], 1)
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertFalse(report["full_calendar_verified"])

    def test_kickoff_conflict_not_accepted(self):
        report = compare(queue("2026-10-17T18:00:00+02:00"), official())
        row = report["days"]["2026-10-17"]
        self.assertEqual(row["matched"], 0)
        self.assertEqual(row["statuses"]["KICKOFF_CONFLICT"], 1)

    def test_missing_espn_fixture_is_visible(self):
        report = compare({"days": ["2026-10-17"], "fixtures": []}, official())
        self.assertEqual(report["days"]["2026-10-17"]["statuses"]["OFFICIAL_ONLY"], 1)
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_invalid_schema_and_scope_rejected(self):
        source = official()
        source["schema"] = "not official"
        with self.assertRaises(ValueError):
            compare(queue(), source)
