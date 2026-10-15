import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as O
from tools.pitchapi_prematch_context import (
    eligible_past_match, find_recent, build_team_sample, lookup_context, render, collect
)

def match(i, kickoff, status="finished", home="A", away="B", team_home="t1", team_away="t2"):
    return O(id=i, time_utc=kickoff, status=status,
             home_team=O(id=team_home, name=home),
             away_team=O(id=team_away, name=away),
             league=O(id="lg1", name="Premier League"))

class TestPrematch(unittest.TestCase):
    def setUp(self):
        self.cutoff = datetime(2026,10,15,20,0,tzinfo=timezone.utc)

    def test_no_future_or_live_info(self):
        self.assertFalse(eligible_past_match(match("a","2026-10-16T12:00:00Z"),"t1",self.cutoff))
        self.assertFalse(eligible_past_match(match("b","2026-10-14T12:00:00Z","not_started"),"t1",self.cutoff))
        self.assertTrue(eligible_past_match(match("c","2026-10-14T12:00:00Z"),"t1",self.cutoff))

    def test_only_target_team(self):
        x=match("x","2026-10-14T12:00:00Z")
        self.assertFalse(eligible_past_match(x,"another",self.cutoff))

    def test_last_five_only(self):
        matches=[match(str(i),f"2026-10-{i:02d}T10:00:00Z") for i in range(1,14)]
        p=find_recent(matches,"t1",self.cutoff)
        self.assertEqual(len(p),5)
        self.assertEqual(p[0].id,"13")

    def test_complete_samples_roll_up(self):
        games=[match(str(i),f"2026-10-{i:02d}T10:00:00Z") for i in (10,11,12)]
        def collector(m):
            return {"home_team_id":"t1","away_team_id":"t2",
                    "xg_home":{"xg_complete":True,"xg":1.5},
                    "xg_away":{"xg_complete":True,"xg":0.5}}
        s=build_team_sample(games,"t1",{},collector)
        self.assertEqual(s["mean_xg_for"],1.5)
        self.assertEqual(s["mean_xg_against"],0.5)

    def test_two_matches_does_not_invent_average(self):
        games=[match(str(i),f"2026-10-{i:02d}T10:00:00Z") for i in (10,11)]
        s=build_team_sample(games,"t1",{},lambda m:{
            "home_team_id":"t1","away_team_id":"t2",
            "xg_home":{"xg_complete":True,"xg":2.0},
            "xg_away":{"xg_complete":True,"xg":1.0}})
        self.assertIsNone(s["mean_xg_for"])
        self.assertEqual(s["data_quality"],"insufficient")

    def test_ambiguous_name_matches_are_rejected(self):
        p={"fixtures":[{"home":"AS Roma","away":"Real Madrid",
                         "league":"Champions League","kickoff_utc":"2026-10-16T19:00:00Z"}]*2}
        self.assertIsNone(lookup_context(p,"Roma","Real Madrid","UEFA Champions League"))

    def test_cross_source_competition_and_names(self):
        item={"home":"AS Roma","away":"Real Madrid","league":"Champions League",
              "kickoff_utc":"2026-10-16T19:00:00Z"}
        self.assertIs(lookup_context({"fixtures":[item]},"Roma","Real Madrid","UEFA Champions League"),item)
        self.assertIsNone(lookup_context({"fixtures":[item]},"Roma","Real Madrid","Premier League"))

    def test_render_marks_no_scores_recalculated(self):
        report={"target_date":"2026-10-16","snapshot_utc":"2026-10-15T18:00:00Z",
                "fixtures_collected":0,"available_upcoming":0,
                "fixtures_with_both_sides_sufficient":0,"fixtures":[]}
        self.assertIn("BEZ ZMIANY PUNKTACJI",render(report))

if __name__=="__main__":
    unittest.main()
