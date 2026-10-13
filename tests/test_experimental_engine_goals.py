import unittest
from tools.experimental_engine_goals import estimate, run

class ExperimentalEngineTests(unittest.TestCase):
    def test_probabilities(self):
        p=estimate(1.4,1.1)
        self.assertTrue(0 < p["over_3_5"] < p["over_2_5"] < p["over_1_5"] < 1)
        self.assertTrue(0 < p["btts_yes"] < 1)

    def test_freeze_before_kickoff(self):
        item={"fixture_id":123,"kickoff_utc":"2026-10-15T20:00:00Z",
              "snapshot_utc":"2026-10-15T19:00:00Z",
              "home_goals_per_match":1.4,"away_goals_per_match":1.1}
        result=run({"date":"2026-10-15","matches":[item]})
        self.assertEqual(result["matches"][0]["decision"],"EXPERIMENT_ONLY_NOT_PLAY")
        self.assertEqual(result["kb_n_effect"],0)
        item["snapshot_utc"]="2026-10-15T21:00:00Z"
        with self.assertRaises(ValueError):
            run({"date":"2026-10-15","matches":[item]})

    def test_missing_rates(self):
        with self.assertRaises(ValueError):
            run({"date":"2026-10-15","matches":[{"fixture_id":1,
                "kickoff_utc":"2026-10-15T20:00:00Z",
                "snapshot_utc":"2026-10-15T19:00:00Z"}]})

if __name__=="__main__": unittest.main()
