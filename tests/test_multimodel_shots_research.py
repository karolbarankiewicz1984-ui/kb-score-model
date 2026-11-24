import unittest
from github_models.shots_research import observation, research_probability, archived_quote_eligible, combined_match_history

CUTOFF="2026-11-24T12:00:00Z"
KICKOFF="2026-11-25T18:00:00Z"
def row(i, team="h", total=12, target=5):
    return {"fixture_id":str(i),"team_id":team,"scope":"team","source":"independent_historical",
            "kickoff_utc":"2026-11-10T18:00:00Z","published_at_utc":"2026-11-12T09:00:00Z",
            "stat_definition_verified":True,"shots_total":total,"shots_on_target":target}

class ShotsResearchTests(unittest.TestCase):
    def test_research_probability(self):
        r=research_probability([row(i) for i in range(5)],family="shots_total",
            selection="over",line=11.5,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertEqual(r["status"],"research_only_uncalibrated")
        self.assertTrue(0 < r["probability"] < 1)
    def test_insufficient_history(self):
        r=research_probability([row(1)],family="shots_on_target",selection="under",line=4.5,
            forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertIsNone(r["probability"])
    def test_no_future_leakage(self):
        r=row(1);r["published_at_utc"]="2026-11-24T13:00:00Z"
        with self.assertRaises(ValueError): observation(r,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_no_unverified_definition(self):
        r=row(1);r["stat_definition_verified"]=False
        with self.assertRaises(ValueError): observation(r,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_no_duplicate_history(self):
        with self.assertRaises(ValueError):
            research_probability([row(1)]*5,family="shots_total",selection="over",line=10.5,
                forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_pre_match_quote(self):
        q={"bookmaker":"superbet.pl","family":"shots_total","scope":"match",
           "period":"fulltime","selection":"over","market_identity_verified":True,
           "line":22.5,"odds":1.2,"captured_at_utc":CUTOFF}
        self.assertTrue(archived_quote_eligible(q,fixture_kickoff_utc=KICKOFF))
        q["market_identity_verified"]=False
        self.assertFalse(archived_quote_eligible(q,fixture_kickoff_utc=KICKOFF))
    def test_pairing(self):
        r=combined_match_history([row(1,"h")],[row(1,"a",9,3)],
            forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertEqual(r[0]["shots_total"],21)
        self.assertEqual(r[0]["shots_on_target"],8)

if __name__=="__main__": unittest.main()
