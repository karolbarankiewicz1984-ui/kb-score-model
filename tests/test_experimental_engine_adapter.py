import unittest
from tools.experimental_engine_adapter import transform
from tools.experimental_engine_goals import run

class AdapterTests(unittest.TestCase):
    def test_api_snapshot_to_experimental_market(self):
        source={"date":"2026-10-15","snapshot_utc":"2026-10-15T08:00:00Z",
                "candidates":[{"fixture_id":42,"kickoff_utc":"2026-10-15T20:00:00Z",
                "api_goal_rates":{"home":{"sample_size":10,"goals_for_per_match":1.8,"goals_against_per_match":0.8},
                                  "away":{"sample_size":10,"goals_for_per_match":1.2,"goals_against_per_match":1.4}}}]}
        converted,excluded=transform(source)
        self.assertEqual(excluded,[])
        self.assertAlmostEqual(converted["matches"][0]["home_goals_per_match"],1.6)
        self.assertAlmostEqual(converted["matches"][0]["away_goals_per_match"],1.0)
        result=run(converted)
        self.assertEqual(result["matches"][0]["rate_type"],"historical_goals_proxy_NOT_xG")
        self.assertFalse(result["register_writes"])
    def test_incomplete_history_is_excluded(self):
        source={"date":"2026-10-15","candidates":[{"fixture_id":42,"api_goal_rates":{"home":{"sample_size":3},"away":{"sample_size":10}}}]}
        converted,excluded=transform(source)
        self.assertEqual(converted["matches"],[])
        self.assertEqual(excluded[0]["reason"],"INSUFFICIENT_HISTORY")

if __name__=="__main__": unittest.main()
