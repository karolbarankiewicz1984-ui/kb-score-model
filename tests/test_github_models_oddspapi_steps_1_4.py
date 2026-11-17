"""Steps 1–4: bookmaker gap explanation, future audit, matched-cohort filters.

Entire suite uses frozen synthetic source quotes; ZERO provider calls.
"""
import unittest
from datetime import datetime, timezone

from github_models.oddspapi_agreement_test import compare_agreement
from github_models.oddspapi_health import report_health
from github_models.oddspapi_market_gaps import coverage
from github_models.oddspapi_replay_audit import audit_one


def example_collection():
    kickoff="2026-11-21T19:00:00Z"
    quote=lambda m, line, price, outcome, player="0": {
        "bookmaker":"superbet.pl", "market_name":m,"market_type":"totals",
        "period":"fulltime","handicap":line,"player_prop":player!="0",
        "player_id":player,"outcome_name":outcome,"odds":price}
    return {
        "bookmakers":["superbet.pl"],
        "links":{"links":[{"fixture_id":"f1","status":"matched","odds_fixture_id":"odds1"}]},
        "snapshots":[{"provider":"oddspapi-v4","fixture_id":"odds1",
                      "pitch_fixture_id":"f1","home":"Home","away":"Away",
                      "kickoff_utc":kickoff,"captured_at_utc":"2026-11-17T07:00:00Z",
                      "quotes":[quote("Over Under Full Time",2.5,1.34,"Over"),
                                quote("Corners - Over Under Full Time",8.5,1.12,"Over"),
                                quote("Bookings - Over Under Full Time",3.5,1.42,"Over"),
                                quote("Over Under Player Fouls Committed",1.5,1.71,"Over","12")]}]
    }


def models():
    markets=[]
    for market,line,p in (("goals",2.5,.76),("corners",8.5,.74),
                          ("fouls",19.5,.81),("cards",3.5,.73)):
        markets.append({"fixture_id":"f1","market":market,"line":line,
                        "selection":"over","probability":p,
                        "frozen_at_utc":"2026-11-16T17:01:50Z"})
    return {"markets":markets}


def settled(fid, market, line, side, p, fair, hit):
    return {"fixture_id":fid,"market":market,"line":line,"selection":side,
            "p_model":p,"p_market":fair,"price":1.45,
            "status":"settled","hit":hit}


class StepOneAndTwo(unittest.TestCase):
    def test_true_market_coverage_missing_or_uncomparable(self):
        result=coverage(example_collection(),models(),as_of_utc="2026-11-17T08:00:00Z")
        self.assertEqual(result["candidate_count"],4)
        status={r["market"]:r["status"] for r in result["model_only_candidates"]}
        self.assertNotIn("goals",status)
        self.assertEqual(status["corners"],"only_offer_below_minimum_odds")
        self.assertEqual(status["cards"],"booking_rules_unverified")
        self.assertEqual(status["fouls"],"player_props_not_match_total")
        self.assertEqual(result["by_market"]["fouls"]["priced_and_settlement_compatible"],0)
        self.assertEqual(result["by_market"]["cards"]["priced_and_settlement_compatible"],0)

    def test_source_and_quote_quality_warning_not_fake_prediction(self):
        coll=example_collection(); coll["snapshots"]=[]
        health=report_health(coll,{"comparisons":[]},{"by_market":{}},
                             {"dates":["2026-11-17"],"fixtures":[{}]})
        self.assertIn("zero_superbet_quotes",health["warnings"])
        self.assertIn("zero_exact_model_market_comparisons",health["warnings"])
        self.assertEqual(health["status"],"attention")

    def test_bookmaker_scope_rejected(self):
        c=example_collection();c["bookmakers"]=["efortuna.pl"]
        with self.assertRaisesRegex(ValueError,"bookmaker_scope"):
            coverage(c,models(),as_of_utc="2026-11-17T08:00:00Z")

    def test_future_matches_are_not_looked_up_as_failed(self):
        fixture={"fixture_id":"f1","home":"Home","away":"Away","league":"LaLiga2"}
        market={"fixture_id":"f1","market":"goals","line":2.5,"selection":"over",
                "p_model":0.75,"price":1.30,"bookmaker":"superbet.pl",
                "eligible_min_odds_1_20":True,"settlement_verified":True,
                "kickoff_utc":"2026-11-21T19:00:00Z",
                "forecast_frozen_at_utc":"2026-11-16T17:00:00Z",
                "odds_captured_at_utc":"2026-11-17T07:00:00Z"}
        rows,reasons=audit_one({"comparisons":[market]},
                               {"fixtures":[fixture]},[],[],
                               datetime(2026,11,17,8,tzinfo=timezone.utc))
        self.assertEqual(rows[0]["status"],"pending_future")
        self.assertEqual(rows[0]["reason"],"kickoff_not_yet_passed")
        self.assertEqual(reasons,{})


class StepFour(unittest.TestCase):
    def test_no_settled_matches_no_lift_claim(self):
        report=compare_agreement([{"status":"pending_future"}])
        self.assertEqual(report["decision"],"NOT_ENOUGH_INDEPENDENT_SETTLED_MATCHES")
        self.assertIsNone(report["agree_minus_disagree_hit_rate_pp"])

    def test_same_population_and_correlated_sides_suppressed(self):
        rows=[]
        for n in range(120):
            fid="f%03d"%n
            agree=n<60
            hit = n%6 != 0 if agree else n%2 == 0
            fair=.70 if agree else .54
            rows.append(settled(fid,"goals",2.5,"over",.75,fair,hit))
        rows.append(settled("f000","goals",2.5,"under",.24,.22,False))
        report=compare_agreement(rows)
        c=report["same_population_comparison"]
        self.assertEqual(c["all"]["positions"],120)
        self.assertEqual(c["agree"]["positions"],60)
        self.assertEqual(c["disagree"]["positions"],60)
        self.assertEqual(c["all"]["distinct_matches"],120)
        self.assertTrue(report["minimum_evidence_reached"])
        self.assertTrue(report["confidence_interval"])
        self.assertGreater(report["agree_minus_disagree_hit_rate_pp"],0)
        self.assertFalse(report["production_weights_unchanged"] is False)
        self.assertEqual(report["decision"],"DESCRIPTIVE_TEST_ONLY_REQUIRES_HOLDOUT")

    def test_do_not_pick_more_than_three_markets_per_game(self):
        rows=[settled("one","goals",i+.5,"over",.85-i*.02,.82,True)
              for i in range(5)]
        report=compare_agreement(rows)
        self.assertEqual(report["same_population_comparison"]["all"]["positions"],3)
        self.assertEqual(report["suppressed_over_three_per_game"],2)


if __name__=="__main__":
    unittest.main()
