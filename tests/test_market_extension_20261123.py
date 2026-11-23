"""Double chance and extra half-lines must remain frozen research forecasts."""
import unittest
from unittest.mock import patch

from github_models.abc_filter import evaluate
from github_models.event_markets import THRESHOLDS, poisson_over
from github_models.abc_settlement import audit

def forecasts(*, elo=(.55,.25,.20), dc=(.53,.27,.20)):
    def row(model, p):
        return dict(fixture_id="match1",model_id=model,
                    p_home=p[0],p_draw=p[1],p_away=p[2],
                    frozen_at_utc="2026-11-23T10:00:00Z")
    return {"predictions":[row("github-elo",elo),
                           row("callumfm-dixon-coles",dc)]}

class DoubleChance(unittest.TestCase):
    def test_1x_x2_12_are_exact_sums_not_independent(self):
        cases=[
            ((.55,.25,.20),(.53,.27,.20),"1X",.8),
            ((.20,.25,.55),(.20,.27,.53),"X2",.8),
            ((.45,.10,.45),(.44,.10,.46),"12",.9)
        ]
        for a,b,side,p in cases:
            with self.subTest(side=side):
                items=evaluate(forecasts(elo=a,dc=b),{"markets":[]})["candidates"]
                dc_rows=[x for x in items if x["market"]=="double_chance"
                         and x["selection"]==side]
                self.assertEqual({x["variant"] for x in dc_rows},{"A","B","C"} if p>=.8 else {"A","B"})
                self.assertAlmostEqual(dc_rows[0]["probability_min"],p)
                self.assertTrue(dc_rows[0]["correlated_with_1x2"])
                self.assertNotIn("odds",dc_rows[0])

    def test_requires_both_frozen_models_and_10pp_agreement(self):
        one=forecasts()
        one["predictions"]=one["predictions"][:1]
        self.assertFalse(any(x["market"]=="double_chance"
                             for x in evaluate(one,{"markets":[]})["candidates"]))
        disagree=forecasts(elo=(.75,.20,.05),dc=(.30,.20,.50))
        items=evaluate(disagree,{"markets":[]})["candidates"]
        self.assertFalse(any(x["market"]=="double_chance"
                             for x in items))

    def test_reject_invalid_input_vector(self):
        bad=forecasts(elo=(.7,.4,-.1))
        with self.assertRaisesRegex(ValueError,"invalid_1x2"):
            evaluate(bad,{"markets":[]})

    def test_double_chance_settlement_uses_actual_1x2_not_independent_market(self):
        predictions=forecasts()
        outcomes=[
            dict(fixture_id="match1",model_id=mod,status="settled",actual="X")
            for mod in ("github-elo","callumfm-dixon-coles")
        ]
        with patch("github_models.abc_settlement.settle",
                   return_value={"settlements":outcomes}), \
             patch("github_models.abc_settlement.settle_markets",
                   return_value={"settlements":[]}):
            rows=audit(predictions,{"markets":[]},{},[],[],"2026-11-24T20:00:00Z")
        outcomes={(r["market"],r["selection"]):r["hit"]
                  for r in rows if r["market"]=="double_chance"}
        self.assertTrue(outcomes[("double_chance","1X")])
        self.assertNotIn(("double_chance","12"),outcomes)  # fails consensus threshold
        self.assertTrue(all(r["status"]=="settled" for r in rows))

    def test_missing_final_remains_unresolved(self):
        predictions=forecasts()
        outcomes=[dict(fixture_id="match1",model_id=mod,
                       status="unresolved",reason="no_exact_final")
                  for mod in ("github-elo","callumfm-dixon-coles")]
        with patch("github_models.abc_settlement.settle",
                   return_value={"settlements":outcomes}), \
             patch("github_models.abc_settlement.settle_markets",
                   return_value={"settlements":[]}):
            rows=audit(predictions,{"markets":[]},{},[],[],"2026-11-24T20:00:00Z")
        dc=[r for r in rows if r["market"]=="double_chance"]
        self.assertTrue(dc)
        self.assertTrue(all(r["status"]=="unresolved" and r["hit"] is None for r in dc))

class ExtraTotals(unittest.TestCase):
    def test_exact_enabled_extra_lines(self):
        self.assertEqual(THRESHOLDS["goals"],(.5,1.5,2.5,3.5,4.5))
        self.assertEqual(THRESHOLDS["corners"],(6.5,7.5,8.5,9.5,10.5,11.5))
        self.assertEqual(THRESHOLDS["fouls"],(19.5,22.5,25.5))
        self.assertEqual(THRESHOLDS["cards"],(2.5,3.5,4.5))

    def test_over_under_complement_and_monotonicity(self):
        for mean in (0,.4,1.25,2.8,8.7,14):
            for market in ("goals","corners"):
                ps=[poisson_over(mean,line) for line in THRESHOLDS[market]]
                self.assertTrue(all(0<=p<=1 for p in ps))
                self.assertEqual(ps,sorted(ps,reverse=True))
                for p in ps:
                    self.assertAlmostEqual(p+(1-p),1,places=10)

    def test_integer_totals_rejected_no_push_in_complement(self):
        with self.assertRaises(ValueError):
            poisson_over(2.4,2)
        with self.assertRaises(ValueError):
            poisson_over(7.9,-.5)

if __name__=="__main__":
    unittest.main()
