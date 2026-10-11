import unittest
from tools.kb21_api_diagnostic import diagnose
from tools.kb21_api_prematch import in_scope

class TestApiDiagnostic(unittest.TestCase):
    def test_diagnostic_probabilities(self):
        row={"api_goal_rates":{"home":{"sample_size":10,"goals_for_per_match":1.6,"goals_against_per_match":1.0},
                               "away":{"sample_size":10,"goals_for_per_match":1.2,"goals_against_per_match":1.3}}}
        result=diagnose(row)
        self.assertEqual(result["status"],"EXPLORATORY_API_ONLY")
        self.assertIsNone(result["p_model"])
        self.assertAlmostEqual(sum(result["diagnostic_probabilities"][k] for k in ("home","draw","away")),1,places=3)
    def test_missing_history(self):
        self.assertEqual(diagnose({"api_goal_rates":{}})["status"],"INSUFFICIENT_HISTORY")
    def test_league_filter(self):
        self.assertTrue(in_scope({"league":{"country":"England","name":"Premier League"}}))
        self.assertFalse(in_scope({"league":{"country":"Argentina","name":"Primera Nacional"}}))
if __name__=="__main__": unittest.main()
