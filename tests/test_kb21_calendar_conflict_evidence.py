import copy
import unittest

from tools.kb21_calendar_conflict_evidence import annotate


def data():
    compare = {"calendar_gate": "BLOCKED", "days": {"2026-10-17": [{
        "league_id": "esp.1", "competition": "La Liga",
        "fixtures": [{
            "status": "START_TIME_CONFLICT",
            "official_fixture": {
                "home": "Real Betis", "away": "FC Barcelona",
                "kickoff": "2026-10-17T18:30:00+02:00"
            },
            "espn_fixture_id": None,
        }]
    }]}}
    snap = {"date": "2026-10-17", "source": "API-Football",
            "snapshot_utc": "2026-10-17T09:02:24Z",
            "candidates": [{
                "fixture_id": 1570413, "league": "La Liga",
                "league_country": "Spain", "home_team": "Real Betis",
                "away_team": "Barcelona",
                "kickoff_utc": "2026-10-17T18:30:00+02:00"
            }]}
    return compare, snap


class ThirdSourceConflictEvidenceTests(unittest.TestCase):
    def test_third_source_corrob_official_but_no_auto_calendar_approval(self):
        c, snap = data()
        original = copy.deepcopy(c)
        result = annotate(c, {"2026-10-17": snap})
        proof = result["days"]["2026-10-17"][0]["fixtures"][0]["third_source_review"]
        self.assertEqual(proof["status"], "OFFICIAL_AND_API_TIME_AGREE_ESPN_DIFFERS")
        self.assertEqual(proof["api_fixture_id"], 1570413)
        self.assertEqual(result["third_source_summary"]["corroborated_with_pre_match_api"], 1)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertTrue(proof["requires_manual_resolution"])
        self.assertEqual(c, original)
        self.assertFalse(result["publication"] == "PLAY")

    def test_api_kickoff_disagrees_with_official(self):
        c, snap = data()
        snap["candidates"][0]["kickoff_utc"] = "2026-10-17T18:00:00+02:00"
        result = annotate(c, {"2026-10-17": snap})
        self.assertEqual(result["third_source_summary"]["corroborated_with_pre_match_api"], 0)
        self.assertEqual(result["days"]["2026-10-17"][0]["fixtures"][0]
                         ["third_source_review"]["status"], "NO_API_MATCH_FOR_OFFICIAL_KICKOFF")

    def test_late_snapshot_cannot_reconstruct_pre_match(self):
        c, snap = data()
        snap["snapshot_utc"] = "2026-10-17T19:00:00+02:00"
        result = annotate(c, {"2026-10-17": snap})
        self.assertEqual(result["days"]["2026-10-17"][0]["fixtures"][0]
                         ["third_source_review"]["status"], "API_SNAPSHOT_NOT_PREMATCH")

    def test_wrong_api_league_not_confused_for_same_named_teams(self):
        c, snap = data()
        snap["candidates"][0]["league_country"] = "England"
        result = annotate(c, {"2026-10-17": snap})
        self.assertEqual(result["third_source_summary"]["corroborated_with_pre_match_api"], 0)

    def test_no_snapshot_never_invents_confirmation(self):
        c, snap = data()
        result = annotate(c, {})
        self.assertEqual(result["days"]["2026-10-17"][0]["fixtures"][0]
                         ["third_source_review"]["status"], "NO_CAPTURED_API_FOOTBALL_SNAPSHOT")

    def test_previously_cleared_calendar_not_accepted(self):
        c, snap = data()
        c["calendar_gate"] = "PASS"
        with self.assertRaises(ValueError):
            annotate(c, {"2026-10-17": snap})


if __name__ == "__main__":
    unittest.main()
