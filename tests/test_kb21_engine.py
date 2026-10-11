import datetime as dt
import unittest
from tools.kb21_engine import calculate

class EngineTests(unittest.TestCase):
    def base(self):
        return {"event":"TEST A - TEST B","kickoff_utc":"2030-01-02T12:00:00Z",
                "snapshot_utc":"2030-01-01T12:00:00Z",
                "fixture_verified_official":True,"fixture_verified_independent":True,
                "sources":["official fixture","independent xG dataset"],
                "structural_0_100":70,"quality_0_100":60,"matchup_0_100":50,
                "home_expected_goals":1.8,"away_expected_goals":1.0,"selection":"home"}
    def test_probabilities_and_score(self):
        r=calculate(self.base(),dt.datetime(2030,1,1,13,tzinfo=dt.timezone.utc))
        self.assertEqual(r["sport_score"],60.5)
        self.assertGreater(r["p_model"],0.5)
        self.assertEqual(r["status"],"CANDIDATE_ONLY")
        self.assertIsNone(r["market_signal"])
    def test_no_post_start(self):
        with self.assertRaises(ValueError):
            calculate(self.base(),dt.datetime(2030,1,3,tzinfo=dt.timezone.utc))
    def test_no_unverified_fixture(self):
        a=self.base();a["fixture_verified_official"]=False
        with self.assertRaises(ValueError):
            calculate(a,dt.datetime(2030,1,1,13,tzinfo=dt.timezone.utc))
    def test_no_missing_xg(self):
        a=self.base();del a["home_expected_goals"]
        with self.assertRaises(ValueError):
            calculate(a,dt.datetime(2030,1,1,13,tzinfo=dt.timezone.utc))
if __name__=="__main__": unittest.main()
