"""Quoted-side, UNDER, match-total and archive/settlement regression tests."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from test_api_market import raw, enrich, policy, settle, storage, fixture, history, item, IsolatedWorkspace


def odds(bet_id=16, values=None):
    return [{"update":"2030-01-02T10:00:00Z", "bookmakers":[{"id":8, "name":"TestBook", "bets":[
        {"id":bet_id, "values":values or [{"value":"Over 2.5", "odd":"2"}, {"value":"Under 2.5", "odd":"4"}]}]}]}]


class OutcomeTests(unittest.TestCase):
    def test_candidates_use_offered_side_and_line_instead_of_fixed_grid(self):
        offered = raw.offered_outcomes(odds(173,[{"value":"Under 24.5", "odd":"1.9"}]))
        self.assertEqual(offered, [{"team_side":"home", "market":"fouls", "line":24.5,
                                   "direction":"under", "market_scope":"match"}])

    def test_generic_cards_first_half_and_refund_lines_are_not_mislabelled(self):
        for bet_id in (80, 82, 83, 6):
            self.assertEqual(raw.offered_outcomes(odds(bet_id)), [])
        values = [{"value":f"Over {line}", "odd":"1.9"} for line in (2, 2.25, 2.75)]
        self.assertEqual(raw.offered_outcomes(odds(5,values)), [])

    def test_opposite_side_quote_does_not_prove_selected_side_availability(self):
        offered = odds(16,[{"value":"Under 2.5", "odd":"1.9"}])
        over = item(line=2.5)
        under = item(line=2.5, direction="under")
        over["market_data"] = raw.extract_market_quotes(offered,over)
        under["market_data"] = raw.extract_market_quotes(offered,under)
        self.assertFalse(over["market_data"]["exact_line_available"])
        self.assertTrue(under["market_data"]["exact_line_available"])
        self.assertEqual(policy.rank_positions([over,under],67), [dict(under, sts_availability=policy.sts_availability(under))])
        self.assertEqual(under["market_data"]["paired_books"],0)
        self.assertIn("1.90",policy.quote_text(under))

    def test_consensus_follows_selected_direction(self):
        over = raw.extract_market_quotes(odds(),item(line=2.5))
        under = raw.extract_market_quotes(odds(),item(line=2.5,direction="under"))
        self.assertAlmostEqual(over["market_probability_pct"] + under["market_probability_pct"],100,places=1)
        self.assertEqual(under["quotes"][0]["selected_odd"],4)
        self.assertLess(under["market_probability_pct"],over["market_probability_pct"])

    def test_under_is_recomputed_from_observations(self):
        values=[0,1,2,3,4]
        self.assertEqual(raw.coverage(values,2.5,5,"under")["hits"],3)
        self.assertEqual(raw.coverage(values,2.5,5,"over")["hits"],2)
        weighted=enrich.weighted_cov([(0,1),(3,0.5)],2.5,5,"under")
        self.assertAlmostEqual(weighted["pct"],200/3)
        under=raw.build_candidate(history(),fixture(),"home","team_goals",4.5,"under")
        over=raw.build_candidate(history(),fixture(),"home","team_goals",4.5,"over")
        self.assertEqual(under["api_pure_pct"],100)
        self.assertEqual(over["api_pure_pct"],0)
        self.assertLess(enrich.reliability_existing(under),100)

    def test_match_total_requires_both_teams_and_uses_sum(self):
        rows=history()
        total=raw.build_candidate(rows,fixture(),"home","team_goals",4.5,"under","match")
        single=raw.build_candidate(rows,fixture(),"home","team_goals",4.5,"under","team")
        self.assertEqual(total["api_pure_pct"],0)  # 4 + 4 goals, not the home team's 4.
        self.assertEqual(single["api_pure_pct"],100)
        incomplete=copy.deepcopy(rows[0]); incomplete["teams"][1]["corners"]=None
        self.assertIsNone(raw.observed_value(incomplete,10,"corners","match"))

    def test_national_and_europe_layers_keep_direction_and_scope(self):
        national=history()
        for row in national:
            row["league"]="UEFA Nations League"; row["_category"]="national_team"
        g=fixture(); g["league"]={"name":"UEFA Nations League"}
        selected=raw.build_candidate(national,g,"home","team_goals",7.5,"under","match")
        result=enrich.recompute_national(selected,g,national)
        self.assertEqual(result["competition_adjusted_pct"],0)
        g["league"]={"name":"UEFA Champions League"}
        for scope, expected in (("team",100),("match",0)):
            selected=raw.build_candidate(history(),g,"home","team_goals",7.5,"under",scope)
            result=enrich.recompute_europe(selected,g,history())
            self.assertEqual(result["competition_adjusted_pct"],expected)

    def test_outcome_keys_preserve_legacy_and_separate_new_variants(self):
        items=[item(direction=d,market_scope=s) for s in ("team","match") for d in ("over","under")]
        self.assertEqual(policy.candidate_key(item()),"1|10|team_goals|0.5")
        self.assertEqual(len({raw.market_key(x) for x in items}),4)
        under=items[1]
        market={"market_probability_pct":70,"paired_books":2,"bookmaker_spread_pp":0,"exact_line_available":True}
        result=raw.apply_market_overlay(under,market,{raw.market_key(item()):{"probability":10}})
        self.assertIsNone(result["market_movement_pp"])

    def test_false_availability_flag_cannot_publish_without_selected_price(self):
        selected=item(market_data={"exact_line_available":True,"quotes":[{"bookmaker":"STS","under_odd":1.8}]})
        self.assertEqual(policy.rank_positions([selected],67),[])
        self.assertEqual(policy.sts_availability(selected)["status"],"unknown")

    def test_goal_history_and_settlement_use_regulation_time(self):
        row=history()[0]
        row["score"]={"fulltime":{"home":1,"away":1},"extratime":{"home":1,"away":0}}
        self.assertEqual(raw.observed_value(row,10,"team_goals","match"),2)
        self.assertIsNone(raw.observed_value(row,10,"corners","match"))
        g=fixture(); g["fixture"]["status"]["short"]="AET"; g["goals"]={"home":2,"away":1};g["score"]=row["score"]
        self.assertEqual(settle.actual_metric(g,[],item(market_scope="match")),2)

    def test_settlement_match_stats_requires_both_actual_values(self):
        g=fixture();g["fixture"]["status"]["short"]="FT"
        blocks=[{"team":{"id":20},"statistics":[{"type":"Fouls","value":8}]},
                {"team":{"id":10},"statistics":[{"type":"Fouls","value":11}]}]
        selected=item(market="fouls",market_scope="match",direction="under",line=19.5)
        actual=settle.actual_metric(g,blocks,selected)
        self.assertEqual(actual,19)
        self.assertTrue(raw.outcome_hit(actual,19.5,"under"))
        self.assertIsNone(settle.actual_metric(g,blocks[:1],selected))


class OutcomeStorageTests(IsolatedWorkspace):
    def test_total_odds_outage_cannot_replace_report_with_empty_success(self):
        def api(endpoint,**kwargs):
            return ({"response":[fixture()],"errors":[]} if endpoint=="fixtures" else {"errors":{"provider":"outage"}}),{}
        with patch.object(raw,"api_get",side_effect=api),patch.object(raw,"load_rows",return_value=history()):
            with self.assertRaisesRegex(RuntimeError,"previous published report"):
                raw.main()
        self.assertFalse(Path("data/api_football/market_work/2030-01-02.json").exists())

    def test_archive_and_settlement_do_not_merge_directions_or_scopes(self):
        selected=[item(line=2.5,direction=d,market_scope=s) for s in ("team","match") for d in ("over","under")]
        self.freeze(selected)
        self.assertEqual(len(storage.frozen_candidates("2030-01-02")),4)
        g=fixture();g["fixture"]["status"]["short"]="FT";g["goals"]={"home":2,"away":1}
        with patch.object(raw,"api_get",side_effect=lambda endpoint,**kw: ({"response":[g] if endpoint=="fixtures" else []},{})):
            settle.main()
        rows=json.loads(Path("data/api_football/calibration/2030-01-02.json").read_text())["observations"]
        actual={(r["market_scope"],r["direction"]):r["hit"] for r in rows}
        self.assertEqual(actual,{("team","over"):0,("team","under"):1,("match","over"):1,("match","under"):0})

    def test_successful_current_prefetch_is_reused_without_duplicate_calls(self):
        for tid in (10,20):
            path=Path(f"data/api_football/national_dynamic/team_{tid}.json")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({"target":"2030-01-02","complete":True,"rows":history()}))
        g=fixture();g["league"]={"name":"UEFA Nations League"}
        with patch.object(raw,"api_get") as api:
            summary=enrich.refresh_national_history([g],[],reuse_current=True)
        api.assert_not_called()
        self.assertEqual(summary["cached_teams"],2)


if __name__ == "__main__":
    unittest.main()
