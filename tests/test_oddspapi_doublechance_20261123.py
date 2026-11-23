"""Exact OddsPapi DC archive match; no guessed price or retroactive settlement."""
from datetime import datetime, timezone
from unittest.mock import patch
import copy
import unittest

from github_models.oddspapi_integration import (
    classify_market, market_overlay,
)
from github_models.oddspapi_replay_audit import audit_one

FREEZE="2026-11-22T10:00:00Z"
CAPTURE="2026-11-22T16:38:00Z"
CHANGED="2026-11-22T16:10:00Z"
KICK="2026-11-23T20:00:00Z"
AS_OF="2026-11-22T17:00:00Z"

def sample():
    model={"predictions":[dict(fixture_id="m1",model_id=k,
          frozen_at_utc=FREEZE,p_home=ph,p_draw=pd,p_away=pa)
          for k,ph,pd,pa in [
              ("github-elo",.5,.25,.25),
              ("callumfm-dixon-coles",.48,.27,.25)]]}
    quotes=[]
    for side,odd in (("1X",1.33),("2X",1.55),("12",1.39)):
        quotes.append(dict(bookmaker="superbet.pl",
          market_id="204",outcome_id=side,market_name="Double Chance Full Time",
          market_type="doublechance",period="fulltime",handicap=0.,
          outcome_name=side,player_prop=False,player_id="0",odds=odd,
          eligible_min_odd=True,no_vig_probability=None,
          changed_at_utc=CHANGED))
    links={"links":[dict(status="matched",fixture_id="m1",odds_fixture_id="od1",
             kickoff_utc=KICK,league="Premier League",home="Team 1",away="Team 2")]}
    snapshot={"fixture_id":"od1","provider":"oddspapi-v4",
              "captured_at_utc":CAPTURE,"kickoff_utc":KICK,
              "quotes":quotes}
    return links,[snapshot],model

class DoubleChanceOdds(unittest.TestCase):
    def test_exact_fulltime_market_is_three_way_and_second_side_maps_2x_to_x2(self):
        links,odds,models=sample()
        one=classify_market(odds[0]["quotes"][0])
        self.assertEqual(one["family"],"double_chance")
        self.assertEqual(one["model_market"],"double_chance")
        overlay=market_overlay(links,odds,as_of_utc=AS_OF,frozen_predictions=models)
        rows=overlay["comparisons"]
        self.assertEqual({r["selection"] for r in rows},{"1X","X2","12"})
        self.assertTrue(all(r["market"]=="double_chance" and r["line"] is None
                            and r["price"] >= 1.20 and r["settlement_verified"]
                            and r["forecast_frozen_at_utc"]==FREEZE and
                            r["bookmaker"]=="superbet.pl" for r in rows))
        self.assertAlmostEqual(next(r["p_model"] for r in rows if r["selection"]=="1X"),.75)

    def test_no_incomplete_half_time_player_or_unknown_period_quotes(self):
        links,odds,models=sample()
        odds[0]["quotes"].pop()
        self.assertEqual(
            market_overlay(links,odds,as_of_utc=AS_OF,
                           frozen_predictions=models)["comparisons"],[])
        for key,value in [
            ("market_name","Double Chance First Half"),
            ("period","p1"),("player_prop",True),
            ("market_type","doublechance-wrong"),("handicap",1.5)]:
            links,odds,models=sample()
            for q in odds[0]["quotes"]:
                q[key]=value
            with self.subTest(key=key):
                self.assertEqual(
                    market_overlay(links,odds,as_of_utc=AS_OF,
                                   frozen_predictions=models)["comparisons"],[])

    def test_timestamp_required_no_forecast_after_kickoff(self):
        links,odds,models=sample()
        odds[0]["quotes"][0]["changed_at_utc"]=None
        rows=market_overlay(links,odds,as_of_utc=AS_OF,frozen_predictions=models)["comparisons"]
        self.assertEqual(len(rows),2)
        links,odds,models=sample()
        for row in models["predictions"]:
            row["frozen_at_utc"]="2026-11-24T10:00:00Z"
        self.assertEqual(
            market_overlay(links,odds,as_of_utc=AS_OF,
                           frozen_predictions=models)["comparisons"],[])

    def test_replay_draw_settles_1x_x2_but_loses_12(self):
        links,odds,models=sample()
        overlay=market_overlay(links,odds,as_of_utc=AS_OF,frozen_predictions=models)
        queue={"fixtures":[{"fixture_id":"m1","kickoff_utc":KICK}]}
        now=datetime(2026,11,25,tzinfo=timezone.utc)
        with patch("github_models.oddspapi_replay_audit.matching_outcomes",
                   return_value=[{"home_goals":1,"away_goals":1}]):
            rows,_=audit_one(overlay,queue,[],[],now)
        actual={r["selection"]:r["hit"] for r in rows}
        self.assertEqual(actual,{"1X":True,"X2":True,"12":False})
        self.assertTrue(all(r["status"]=="settled" for r in rows))

if __name__ == "__main__":
    unittest.main()
