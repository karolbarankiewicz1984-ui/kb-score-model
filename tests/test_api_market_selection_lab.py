"""Tests for read-only API Market selection lab (no network, no API key)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from api_market_selection_lab import load,published,playable,capped,metrics,audit,band,odds_band,markdown

def row(oid,score=70,odd=1.25,fixture=1,market="corners",hit=1,bookmaker="Betano",is_published=True):
    return {
        "observation_id":oid,"date":"2026-10-13","fixture_id":fixture,
        "final_assessment_pct":score,"published":is_published,"hit":hit,
        "market":market,"market_data":{"quotes":[
            {"bookmaker":bookmaker,"selected_odd":odd}]},
    }

class SelectionLabTests(unittest.TestCase):
    def test_settlement_dedup_and_publication(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"day.json"
            path.write_text(json.dumps({"schema":"api-market-settlement-v2",
                "observations":[row("A"),row("A"),row("B",is_published=False)],
                "errors":[]}),encoding="utf-8")
            rows,errors=load([path,path])
            self.assertEqual((len(rows),errors),(2,0))
            self.assertEqual(len(published(rows)),1)

    def test_minimum_odd_and_polish_bookies(self):
        rows=[row("A",odd=1.19),row("B",odd=1.20),
              row("C",odd=1.23,bookmaker="STS"),
              row("D",odd=float("nan"))]
        self.assertEqual(len(playable(rows)),2)
        self.assertEqual(len(playable(rows,bookmakers={"sts","superbet"})),1)

    def test_three_pick_cap_and_diversification(self):
        rows=playable([row("A",score=90),row("B",score=80),
                       row("C",score=75,market="fouls"),
                       row("D",score=70,fixture=2)])
        self.assertEqual(len(capped(rows,2)),3)
        self.assertEqual({r["observation_id"] for r in capped(rows,2,True)},{"A","C","D"})

    def test_metrics_and_bands(self):
        rows=playable([row("A",odd=1.50),row("B",odd=1.40,hit=0)])
        self.assertAlmostEqual(metrics(rows,True)["roi_pct"],-25.0)
        self.assertEqual(band(69.9),"67-69.9")
        self.assertEqual(band(100.0),"90-100")

    def test_fixture_equal_metrics_do_not_overweight_a_match(self):
        # Two wins from fixture A and one loss from fixture B:
        # 66.67% per pick but only 50% when each fixture gets equal weight.
        rows=playable([row("A",fixture=1,odd=1.20),
                       row("B",fixture=1,odd=1.20),
                       row("C",fixture=2,odd=2.00,hit=0)])
        outcome=metrics(rows,True)
        self.assertEqual(outcome["n"],3)
        self.assertEqual(outcome["fixtures"],2)
        self.assertAlmostEqual(outcome["accuracy_pct"],66.67)
        self.assertAlmostEqual(outcome["fixture_equal_accuracy_pct"],50.0)
        self.assertAlmostEqual(outcome["roi_pct"],-20.0)
        self.assertAlmostEqual(outcome["fixture_equal_roi_pct"],-40.0)
        self.assertAlmostEqual(outcome["max_fixture_pick_share_pct"],66.67)

    def test_competition_and_odds_groups_and_flags(self):
        a=row("A",odd=1.21,fixture=1,market="corners")
        a.update(competition="Serie A",model_version="v3.2",direction="over",market_scope="team")
        b=row("B",odd=1.71,fixture=2,market="fouls")
        b.update(competition="UEFA Champions League",model_version="v3.3",direction="under",market_scope="match")
        outcome=audit([a,b],errors=22)
        self.assertEqual(outcome["by_competition"]["Serie A"]["n"],1)
        self.assertEqual(outcome["by_competition"]["UEFA Champions League"]["n"],1)
        self.assertEqual(outcome["by_market_direction"]["fouls:under"]["hits"],1)
        self.assertEqual(outcome["by_market_scope"]["match"]["n"],1)
        self.assertEqual(outcome["by_odds_band"]["1.20-1.39"]["n"],1)
        self.assertEqual(outcome["by_odds_band"]["1.60-1.99"]["n"],1)
        self.assertEqual(outcome["model_versions"],{"v3.2":1,"v3.3":1})
        self.assertEqual(set(outcome["quality_flags"]),
                         {"low_independent_fixture_count",
                          "settlement_missing_statistics",
                          "no_verified_sts_superbet_quotes",
                          "multiple_model_versions_not_directly_comparable"})
        md=markdown(outcome)
        self.assertIn("Fixture-equal ROI %",md)
        self.assertIn("## by_competition",md)
        self.assertIn("multiple_model_versions_not_directly_comparable",md)

    def test_odds_band_edges(self):
        self.assertEqual([odds_band(x) for x in (1.20,1.39,1.40,1.59,1.60,1.99,2.0)],
                         ["1.20-1.39","1.20-1.39","1.40-1.59","1.40-1.59",
                          "1.60-1.99","1.60-1.99","2.00+"])

    def test_shadow_never_rewrites_input(self):
        rows=[row("A"),row("B",market="fouls",fixture=2)]
        before=json.dumps(rows,sort_keys=True)
        result=audit(rows)
        self.assertEqual(json.dumps(rows,sort_keys=True),before)
        self.assertEqual(result["all_published"]["n"],2)
        self.assertEqual(result["scenarios"]["sts_superbet_only"]["n"],0)

if __name__=="__main__":
    unittest.main()
