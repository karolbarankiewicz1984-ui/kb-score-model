"""Independent display-only practical API Market PDF tests."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from api_market_practical_pdf import pick_research_positions,render_pdf

NOW=datetime(2026,10,18,11,14,tzinfo=timezone.utc)


def make(fid,score,market="team_goals",selection="gole drużyny: powyżej 0.5",
         odd=1.32,kickoff="2026-10-18T16:00:00+02:00"):
    return {
        "fixture_id":fid,"team_id":fid,"market":market,
        "market_scope":"team","direction":"over","line":0.5,
        "kickoff":kickoff,
        "home":f"Klub {fid}","away":f"Drużyna {fid}",
        "selection":selection,"final_assessment_pct":score,
        "market_data":{"quotes":[{"bookmaker":"TestAPI","over_odd":odd}]},
    }


def input_data(rows=None):
    return {
        "schema":"api-market-scan-v3",
        "date":"2026-10-18",
        "generated_at_utc":"2026-10-18T08:57:59+00:00",
        "top_positions":rows if rows is not None else [
            make(1,81),make(2,78,"yellow_cards","kartki: powyżej 0.5",1.27),
        ],
    }


class PracticalPDFTests(unittest.TestCase):
    def test_unmodified_snapshot_one_market_per_game(self):
        source=input_data([make(1,84),make(1,82,selection="gole drużyny: powyżej 1.5"),
                           make(2,78,"corners","rożne drużyny: powyżej 3.5")])
        before=deepcopy(source)
        out=pick_research_positions(source,now=NOW)
        self.assertEqual(out["total"],2)
        self.assertEqual(len(out["goal_markets"]),1)
        self.assertEqual(len(out["other_markets"]),1)
        self.assertEqual(out["goal_markets"][0]["score"],84.0)
        self.assertEqual(source,before)
        self.assertFalse(out["polish_bookmaker_verified"])
        self.assertFalse(out["original_market_model_modified"])

    def test_threshold_and_already_started_game_removed(self):
        rows=[make(1,90,odd=1.19),
              make(2,66,odd=1.8),
              make(3,80,kickoff="2026-10-18T12:10:00+02:00"),
              make(4,79,kickoff="2026-10-18T17:00:00+02:00",odd=1.20)]
        out=pick_research_positions(input_data(rows),now=NOW)
        self.assertEqual(out["total"],1)
        self.assertEqual(out["goal_markets"][0]["fixture_id"],4)
        self.assertEqual(out["goal_markets"][0]["api_best_odd"],1.20)

    def test_source_timestamp_and_faked_odds_rejected(self):
        src=input_data()
        src["generated_at_utc"]="2026-10-19T08:57:59Z"
        with self.assertRaisesRegex(ValueError,"genuine existing"):
            pick_research_positions(src,now=NOW)
        src=input_data([make(2,90,odd=1.11)])
        self.assertEqual(pick_research_positions(src,now=NOW)["total"],0)
        src=input_data([make(3,90,odd=1.3,kickoff="2026-10-19T16:00:00+02:00")])
        self.assertEqual(pick_research_positions(src,now=NOW)["total"],0)

    def test_compact_pdf_with_real_quotes_and_unicode(self):
        report=pick_research_positions(input_data(),now=NOW)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"praktyczne.pdf"
            render_pdf(report,dest)
            self.assertEqual(dest.read_bytes()[:5],b"%PDF-")
            self.assertGreater(dest.stat().st_size,2500)
            bad=deepcopy(report)
            bad["polish_bookmaker_verified"]=True
            with self.assertRaisesRegex(ValueError,"unverified"):
                render_pdf(bad,dest)

    def test_empty_list_is_not_fake_prediction(self):
        report=pick_research_positions(input_data([]),now=NOW)
        self.assertEqual(report["total"],0)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"empty.pdf"
            render_pdf(report,dest)
            self.assertTrue(dest.read_bytes().startswith(b"%PDF-"))


if __name__=="__main__":
    unittest.main()
