import copy
import unittest
from tools.kb21_context_enrich import enrich


def queue():
    return {
        "days": ["2026-10-17", "2026-10-18"],
        "calendar_gate": "BLOCKED",
        "fixtures": [{
            "fixture_id": "eng.1:777",
            "fixture": "Everton - Chelsea",
            "date_warsaw": "2026-10-17",
            "kickoff": "2026-10-17T13:30:00+02:00",
            "assessment": {"str": None, "qual": None, "match": None,
                           "p_model": None, "confidence": None},
            "publication": "DIAGNOSTIC / NO PLAY",
        }]
    }


def api_snapshot():
    history = {"sample_size": 5, "goals_for_per_match": 1.4,
               "goals_against_per_match": 1.0, "fixture_ids": [1, 2, 3, 4, 5]}
    return {"date": "2026-10-17", "source": "API-Football",
            "snapshot_utc": "2026-10-17T09:00:00+00:00",
            "candidates": [{
                "fixture_id": 123, "home_team": "Everton FC",
                "away_team": "Chelsea FC", "league_country": "England",
                "league": "Premier League",
                "kickoff_utc": "2026-10-17T11:30:00Z",
                "api_goal_rates": {"home": history, "away": history},
            }]}


class ContextEnrichTests(unittest.TestCase):
    def test_matched_prior_goals_are_labelled_and_do_not_change_model(self):
        q = queue()
        untouched = copy.deepcopy(q["fixtures"][0]["assessment"])
        result = enrich(q, {"2026-10-17": api_snapshot()})
        research = result["fixtures"][0]["pre_match_research"]
        self.assertEqual(research["status"], "PRIOR_GOAL_CONTEXT")
        self.assertIn("NOT xG", research["context"]["home"]["metric"])
        self.assertIsNone(research["context"]["xg"])
        self.assertEqual(result["fixtures"][0]["assessment"], untouched)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")

    def test_wrong_league_or_kickoff_is_not_attached(self):
        snap = api_snapshot()
        snap["candidates"][0]["league"] = "Championship"
        result = enrich(queue(), {"2026-10-17": snap})
        self.assertEqual(result["fixtures"][0]["pre_match_research"]["status"],
                         "NO_UNAMBIGUOUS_NAME_LEAGUE_TIME_MATCH")
        self.assertIsNone(result["fixtures"][0]["pre_match_research"]["context"])

    def test_post_start_snapshot_is_rejected(self):
        snap = api_snapshot()
        snap["snapshot_utc"] = "2026-10-17T12:00:00Z"
        self.assertEqual(enrich(queue(), {"2026-10-17": snap})
                         ["fixtures"][0]["pre_match_research"]["status"], "SNAPSHOT_NOT_PREMATCH")

    def test_duplicate_fixtures_are_ambiguous(self):
        snap = api_snapshot()
        snap["candidates"].append(copy.deepcopy(snap["candidates"][0]))
        self.assertEqual(enrich(queue(), {"2026-10-17": snap})
                         ["fixtures"][0]["pre_match_research"]["status"], "AMBIGUOUS_MATCH")

    def test_no_history_means_no_fabricated_metrics(self):
        snap = api_snapshot()
        snap["candidates"][0]["api_goal_rates"] = {}
        r = enrich(queue(), {"2026-10-17": snap})["fixtures"][0]["pre_match_research"]
        self.assertEqual(r["status"], "MATCH_WITHOUT_RELIABLE_HISTORY")
        self.assertIsNone(r["context"]["home"])
        self.assertIsNone(r["context"]["away"])

    def test_no_snapshot_stays_unscored(self):
        row = enrich(queue(), {})["fixtures"][0]
        self.assertEqual(row["pre_match_research"]["status"], "NO_API_SNAPSHOT")
        self.assertIsNone(row["assessment"]["p_model"])


if __name__ == "__main__":
    unittest.main()
