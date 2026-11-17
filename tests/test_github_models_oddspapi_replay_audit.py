"""Historical odds audit: no post-kickoff leakage and no price hindsight bias."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_models.oddspapi_replay_audit import run,audit_one


def queue():
    return {"fixtures":[{"fixture_id":"m1","home":"A","away":"B",
              "league":"LaLiga2","kickoff_utc":"2026-11-16T19:30:00Z"}]}


def record(price=1.8, observed="2026-11-15T12:00:00Z"):
    return {"fixture_id":"m1","bookmaker":"superbet.pl",
            "eligible_min_odds_1_20":True,"market":"goals","line":2.5,"selection":"over",
            "p_model":0.80,"market_no_vig_probability":0.70,"price":price,
            "kickoff_utc":"2026-11-16T19:30:00Z",
            "odds_captured_at_utc":observed,
            "forecast_frozen_at_utc":"2026-11-15T11:00:00Z",
            "settlement_verified":True}


class ReplayTest(unittest.TestCase):
    def test_empty_does_not_claim_calibration(self):
        with tempfile.TemporaryDirectory() as td:
            r=run(td,[],[],"2026-11-17T18:00:00Z")
            self.assertEqual(r["archives_processed"],0)
            self.assertEqual(r["settled_selection_quotes"],0)
            self.assertEqual(r["decision"],"INSUFFICIENT_PROSPECTIVE_EVIDENCE")

    def test_future_market_quote_is_not_eligible(self):
        too_late=record(observed="2026-11-16T19:31:00Z")
        rows,excluded=audit_one({"comparisons":[too_late]},queue(),[],[],
                                __import__("datetime").datetime(2026,11,17,tzinfo=__import__("datetime").timezone.utc))
        self.assertEqual(rows,[])
        self.assertEqual(excluded["not_verified_prekickoff"],1)

    def test_first_price_is_frozen_not_best_in_hindsight(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name,price,stamp in (("earlier",1.8,"2026-11-15T12:00:00Z"),
                                     ("later",2.7,"2026-11-15T19:00:00Z")):
                folder=root/name
                folder.mkdir()
                (folder/"pitch_queue.json").write_text(json.dumps(queue()))
                (folder/"market_overlay.json").write_text(json.dumps(
                    {"comparisons":[record(price=price,observed=stamp)]}))
            with patch("github_models.oddspapi_replay_audit.settle_markets",
                       return_value={"settlements":[{"status":"settled","hit":True}]}):
                r=run(root,[],[],"2026-11-18T12:00:00Z")
            self.assertEqual(r["archives_processed"],2)
            self.assertEqual(r["duplicates_suppressed"],1)
            self.assertEqual(r["settled_selection_quotes"],1)
            self.assertEqual(len(r["price_changes"]),1)
            self.assertAlmostEqual(r["price_changes"][0]["first_price"],1.8)
            results={x["variant"]:x for x in r["summary"]}
            self.assertAlmostEqual(results["model_only"]["unit_stake_roi_before_fees_and_tax"],0.8)
            self.assertFalse(r["promotion_gate"]["production_weight_change_permitted"])


if __name__=="__main__":
    unittest.main()
