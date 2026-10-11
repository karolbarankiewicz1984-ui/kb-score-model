import unittest
from tools.kb21_gate_audit import assess,audit

class GateAuditTests(unittest.TestCase):
    def test_missing_inputs_block(self):
        r=assess({"fixture_id":1,"event":"A - B","api_goal_rates":{}})
        self.assertFalse(r["ready_for_review"])
        self.assertIn("OFFICIAL_FIXTURE_UNVERIFIED",r["blocking_reasons"])
        self.assertIn("MISSING_HOME_EXPECTED_GOALS",r["blocking_reasons"])
        self.assertFalse(r["freeze_allowed"])
    def test_same_provider_is_not_independent(self):
        row={"sources":["API-Football fixtures","API-Football historical fixtures"],"api_goal_rates":{}}
        result=assess(row)
        self.assertIn("ONLY_ONE_SOURCE_PROVIDER",result["blocking_reasons"])
    def test_even_complete_review_is_not_play(self):
        row={"fixture_id":2,"event":"A - B","fixture_verified_official":True,
             "fixture_verified_independent":True,"sources":["official","independent"],
             "structural_0_100":70,"quality_0_100":60,"matchup_0_100":50,
             "home_expected_goals":1.3,"away_expected_goals":1.1,
             "api_goal_rates":{"home":{"sample_size":10},"away":{"sample_size":10}}}
        result=assess(row)
        self.assertTrue(result["ready_for_review"])
        self.assertFalse(result["freeze_allowed"])
        self.assertEqual(result["kb_status"],"NOT_ASSIGNED")
        self.assertEqual(audit({"date":"2030-01-01","candidates":[row]})["kb_n_effect"],0)
if __name__=="__main__":unittest.main()
