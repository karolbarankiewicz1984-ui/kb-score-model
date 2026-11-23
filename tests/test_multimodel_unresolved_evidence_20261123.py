"""Diagnose source evidence on first-quote exact records, never settle by guess."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from github_models.oddspapi_replay_audit import run

FREEZE="2026-11-20T09:00:00Z"
PRICE="2026-11-20T10:00:00Z"
KICK="2026-11-20T20:00:00Z"
NOW="2026-11-23T21:00:00Z"

def fixture():
    return {"fixture_id":"m1","home":"Alpha","away":"Beta",
            "league":"Premier League","country_code":"ENG",
            "kickoff_utc":KICK}

def sample_market(market="corners",line=8.5,selection="over"):
    return {"bookmaker":"superbet.pl","eligible_min_odds_1_20":True,
            "fixture_id":"m1","market":market,"line":line,
            "selection":selection,"kickoff_utc":KICK,
            "odds_captured_at_utc":PRICE,"forecast_frozen_at_utc":FREEZE,
            "p_model":.77,"price":1.29,
            "market_no_vig_probability":None,"settlement_verified":True}

def write(tmp,quote):
    d=Path(tmp)/"one";d.mkdir()
    (d/"pitch_queue.json").write_text(json.dumps({"fixtures":[fixture()]}))
    (d/"market_overlay.json").write_text(json.dumps({"comparisons":[quote]}))

class ReplayEvidenceTests(unittest.TestCase):
    def test_known_score_cannot_invent_missing_corner_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp,sample_market())
            with patch("github_models.oddspapi_replay_audit.settle_markets",
                       return_value={"settlements":[{
                           "status":"unmapped","reason":"no_exact_verified_outcome"}]}), \
                 patch("github_models.oddspapi_replay_audit.matching_outcomes",
                       return_value=[{"home_goals":2,"away_goals":1}]):
                report=run(Path(tmp),[],[],NOW)
            self.assertEqual(report["unresolved_by_market"],{"corners":1})
            self.assertEqual(report["unresolved_source_evidence"],
                             {"verified_final_score_exists_event_total_missing":1})
            self.assertEqual(report["status_counts"],{"unresolved":1})
            self.assertEqual(report["settled_fixture_ids"],[])
            self.assertEqual(report["unresolved_exact_selections"][0]["fixture_id"],"m1")
            self.assertTrue(report["unresolved_diagnostics_only"])

    def test_exact_score_produces_unique_fixture_id_without_changing_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp,sample_market("1X2",0,"1"))
            with patch("github_models.oddspapi_replay_audit.matching_outcomes",
                       return_value=[{"home_goals":2,"away_goals":1}]):
                report=run(Path(tmp),[],[],NOW)
            self.assertEqual(report["settled_fixture_ids"],["m1"])
            self.assertEqual(report["unique_settled_fixtures"],1)
            self.assertEqual(report["settled_selection_quotes"],1)
            self.assertEqual(report["unresolved_exact_selections"],[])
            self.assertTrue(report["no_model_retraining"])

if __name__=="__main__":
    unittest.main()
