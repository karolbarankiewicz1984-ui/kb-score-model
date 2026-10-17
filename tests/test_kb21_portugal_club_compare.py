import unittest
from tools.kb21_portugal_club_compare import compare, render


def source():
    return {
        "schema": "kb21-official-portugal-club-postponement-v1",
        "league_id": "por.1", "days": ["2026-10-17", "2026-10-18", "2026-10-19"],
        "source_comparison": "DISPLAY_TIMEZONE_NOT_STATED",
        "gil_official_article": {"gil_local_clock": "20:15",
                                 "gil_timezone": "Europe/Lisbon"},
        "braga_visible_display": {"display_clock": "19:15",
                                  "display_timezone": None},
        "source_errors": [], "by_day": {
            "2026-10-17": [], "2026-10-18": [],
            "2026-10-19": [{
                "home": "SC Braga", "away": "Gil Vicente FC",
                "kickoff_warsaw": "2026-10-19T21:15:00+02:00",
                "kickoff_utc": "2026-10-19T19:15:00+00:00",
            }],
        },
    }


def queue(time="2026-10-19T21:15:00+02:00"):
    return {
        "days": ["2026-10-17", "2026-10-18", "2026-10-19"],
        "fixtures": [{"fixture_id": "por.1:101",
                      "fixture": "Braga - Gil Vicente",
                      "date_warsaw": "2026-10-19",
                      "kickoff": time}],
    }


class PortugueseComparison(unittest.TestCase):
    def test_correct_local_utc_equivalence_never_approves_day(self):
        result = compare(queue(), source())
        self.assertEqual(result["days"]["2026-10-19"]["matched"], 1)
        self.assertEqual(result["club_clock_evidence"]["braga_visible_clock"], "19:15")
        self.assertIsNone(result["club_clock_evidence"]["braga_time_zone"])
        self.assertFalse(result["full_calendar_verified"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIn("NO PLAY", render(result))

    def test_wrong_timezone_conversion_is_reported_as_conflict(self):
        result = compare(queue("2026-10-19T20:15:00+02:00"), source())
        row = result["days"]["2026-10-19"]
        self.assertEqual(row["matched"], 0)
        self.assertEqual(row["statuses"]["KICKOFF_CONFLICT"], 1)
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_only_club_game_never_certifies_entire_league(self):
        q = queue()
        q["fixtures"] = []
        result = compare(q, source())
        self.assertEqual(result["days"]["2026-10-19"]["statuses"]["CLUB_ARTICLE_ONLY"], 1)
        self.assertIsNone(result["days"]["2026-10-17"]["confirmed_zero_matches"])

    def test_wrong_scope_and_schema_rejected(self):
        wrong = source()
        wrong["days"] = ["2026-10-19"]
        with self.assertRaises(ValueError):
            compare(queue(), wrong)
        wrong = source()
        wrong["schema"] = "untrusted"
        with self.assertRaises(ValueError):
            compare(queue(), wrong)

if __name__ == "__main__":
    unittest.main()
