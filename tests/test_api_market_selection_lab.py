"""Tests for read-only API Market selection lab (no network, no API key)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from api_market_selection_lab import load,published,playable,capped,metrics,audit,band

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

    def test_shadow_never_rewrites_input(self):
        rows=[row("A"),row("B",market="fouls",fixture=2)]
        before=json.dumps(rows,sort_keys=True)
        result=audit(rows)
        self.assertEqual(json.dumps(rows,sort_keys=True),before)
        self.assertEqual(result["all_published"]["n"],2)
        self.assertEqual(result["scenarios"]["sts_superbet_only"]["n"],0)

if __name__=="__main__":
    unittest.main()
