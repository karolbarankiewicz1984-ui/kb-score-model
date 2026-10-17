"""Tests for Belgian organizer selected-round evidence without usable dates."""
from io import BytesIO
import unittest

from tools.kb21_official_belgium import SOURCE, parse, collect
from tools.kb21_belgium_round_compare import compare

HTML = """<html><main><h1>Jupiler Pro League Kalender</h1>
<p>Speeldag 9</p>
<p>Jupiler Pro League·S9</p><p>KV Kortrijk</p><p>KV Mechelen</p>
<p>Jupiler Pro League·S9</p><p>Royal Antwerp FC</p><p>Sporting Charleroi</p>
<p>Jupiler Pro League·S9</p><p>RSC Anderlecht</p><p>KAA Gent</p>
</main></html>"""
DAYS = ["2026-10-17", "2026-10-18", "2026-10-19"]


def queue():
    return {
        "days": DAYS,
        "fixtures": [{
            "date_warsaw": DAYS[1],
            "fixture_id": "bel.1:100",
            "fixture": "KV Kortrijk - KV Mechelen",
            "kickoff": "2026-10-18T19:00:00+02:00",
        }],
    }


class BelgiumRoundTests(unittest.TestCase):
    def test_read_visible_round_but_never_assign_date_or_time(self):
        rows, errors = parse(HTML)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 3)
        self.assertEqual({x["selected_round"] for x in rows}, {9})
        self.assertIsNone(rows[0]["date_warsaw"])
        self.assertIsNone(rows[0]["kickoff_warsaw"])
        self.assertFalse(rows[0]["kickoff_timezone_verified"])

    def test_empty_or_changed_site_does_not_prove_zero(self):
        rows, errors = parse("<html><h1>Jupiler Pro League</h1></html>")
        self.assertEqual(rows, [])
        self.assertIn("NO_VISIBLE_FIXTURES_IN_SELECTED_ROUND", errors)

    def test_collect_captures_undated_round_and_keeps_each_day_empty(self):
        snapshot = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        self.assertEqual(snapshot["status"], "OFFICIAL_SELECTED_ROUND_UNDATED_FOR_REVIEW")
        self.assertEqual(snapshot["selected_rounds"], [9])
        self.assertEqual(len(snapshot["undated_fixtures"]), 3)
        self.assertTrue(all(v == [] for v in snapshot["by_day"].values()))
        self.assertFalse(snapshot["date_verified"])
        self.assertEqual(snapshot["calendar_gate"], "BLOCKED")
        self.assertFalse(snapshot["full_calendar_verified"])

    def test_team_only_hint_is_never_a_date_pair(self):
        snapshot = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        matched = compare(queue(), snapshot)
        row = matched["days"][DAYS[1]]
        self.assertEqual(row["team_pair_only_hints"], ["bel.1:100"])
        self.assertEqual(row["time_approved_matches"], 0)
        self.assertEqual(row["organizer_count"], 0)
        self.assertFalse(row["no_games_certified"])
        self.assertEqual(matched["calendar_gate"], "BLOCKED")

    def test_reject_spoofed_belgium_dated_organizer_fixtures(self):
        snapshot = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        snapshot["by_day"][DAYS[1]] = [{"home": "KV Kortrijk"}]
        with self.assertRaisesRegex(ValueError, "Undated JPL"):
            compare(queue(), snapshot)
        snapshot = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        snapshot["undated_fixtures"][0]["date_warsaw"] = DAYS[1]
        with self.assertRaisesRegex(ValueError, "must not claim verified"):
            compare(queue(), snapshot)
        snapshot = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        snapshot["date_verified"] = True
        with self.assertRaisesRegex(ValueError, "Invalid unsigned"):
            compare(queue(), snapshot)


if __name__ == "__main__":
    unittest.main()
