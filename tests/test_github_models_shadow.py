"""No fabricated odds, no 67-point gate, conservative independent SHADOW math."""
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from github_models.shadow_markets import _margin_p, _pmf, run
from github_models.shadow_superbet import overlay
from github_models.shadow_reports import build
from github_models.shadow_audit import settle_one, audit


FROZEN = "2026-11-20T10:00:00Z"
KICKOFF = "2026-11-21T19:00:00Z"


def fixture():
    return {"fixture_id": "m1", "league": "Bundesliga",
            "home": "Team A", "away": "Team B", "kickoff_utc": KICKOFF}


def entry(market, side, line, probability):
    return {"fixture_id": "m1", "market": market, "selection": side,
            "line": line, "probability": probability, "frozen_at_utc": FROZEN}


def sample():
    rows = [entry("btts", "yes", None, .63),
            entry("btts", "no", None, .37),
            entry("handicap", "home", 1.5, .88)]
    return {"schema": "multimodel-v2-shadow-markets-v1",
            "generated_at_utc": FROZEN, "candidates": rows,
            "unsupported_markets": {"shots": "independent_verified_history_missing",
                                    "offsides": "independent_verified_history_missing"}}


class TestShadow(unittest.TestCase):
    def test_poisson_normalization_and_complement(self):
        self.assertAlmostEqual(sum(_pmf(2.3)), 1, places=9)
        self.assertAlmostEqual(_margin_p(1.6, 1.2, 1.5) +
                               (1 - _margin_p(1.6, 1.2, 1.5)), 1.0)
        self.assertGreater(_margin_p(1.6, 1.2, 1.5),
                           _margin_p(1.6, 1.2, -1.5))
        with self.assertRaises(ValueError):
            _margin_p(1.2, 1.2, 1)

    def test_no_history_means_no_forecast_not_failure(self):
        result = run({"fixtures": [fixture()]}, [], FROZEN)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(len(result["blockers"]), 1)
        self.assertIn("shots", result["unsupported_markets"])
        self.assertTrue(result["no_67_point_quality_gate"])

    def test_strict_superbet_btts_quote_and_handicap_block(self):
        q = {"fixtures": [fixture()]}
        snap = {"provider": "oddspapi-v4", "pitch_fixture_id": "m1",
                "fixture_id": "odds1", "kickoff_utc": KICKOFF,
                "captured_at_utc": "2026-11-20T11:00:00Z",
                "quotes": [
                    {"bookmaker": "superbet.pl", "market_name": "Both Teams To Score",
                     "period": "fulltime", "player_id": "0", "player_prop": False,
                     "outcome_name": "Yes", "odds": 1.69},
                    {"bookmaker": "superbet.pl", "market_name": "Both Teams To Score",
                     "period": "fulltime", "player_id": "0", "player_prop": False,
                     "outcome_name": "No", "odds": 2.01},
                    {"bookmaker": "superbet.pl", "market_name": "Asian Handicap",
                     "period": "fulltime", "outcome_name": "1", "odds": 1.50},
                ]}
        collection = {"bookmakers": ["superbet.pl"], "as_of_utc": "2026-11-20T11:00:00Z",
                      "links": {"links": [{"status": "matched", "fixture_id": "m1",
                                           "odds_fixture_id": "odds1"}]},
                      "snapshots": [snap]}
        result = overlay(collection, sample(), q)
        self.assertEqual(result["counts"]["quoted_research"], 2)
        self.assertEqual(result["counts"]["model_only"], 1)
        self.assertIsNone(result["rows"][2]["odds"])
        self.assertEqual(result["rows"][2]["reason"],
                         "asian_handicap_quote_semantics_not_verified")
        self.assertFalse(result["quality_score_67_100_required"])
        self.assertTrue(result["no_extra_api_calls"])

        snap["quotes"][0]["odds"] = 1.19
        result = overlay(collection, sample(), q)
        self.assertEqual(result["counts"]["quoted_research"], 1)

        snap["quotes"][0]["odds"] = 1.69
        snap["quotes"][0]["period"] = "p1"
        result = overlay(collection, sample(), q)
        self.assertEqual(result["counts"]["quoted_research"], 1)

    def test_future_shadow_forecast_is_pending(self):
        rows = settle_one(sample(), {"fixtures": [fixture()]}, [],
                          "2026-11-20T11:00:00Z")
        self.assertEqual({r["status"] for r in rows}, {"pending"})

    def test_reports_publish_seven_pdfs_and_manifest(self):
        import fitz
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("queues", "shadow", "pdf"):
                (root / folder).mkdir()
            first = date(2026, 11, 20)
            days = [(first + timedelta(days=i)).isoformat() for i in range(7)]
            queue = {"dates": days, "fixtures": [fixture()],
                     "missing_dates": [], "invalid_dates": [], "partial_dates": []}
            (root/"queues"/(days[0]+".json")).write_text(json.dumps(queue))
            (root/"shadow"/(days[0]+".json")).write_text(json.dumps(sample()))
            report = build(root, days[0])
            self.assertEqual(len(report["reports"]), 7)
            self.assertEqual(sum(v["rows"] for v in report["reports"]), 3)
            self.assertTrue((root/"shadow"/("SHADOW_MANIFEST_"+days[0]+".json")).exists())
            with fitz.open(root/"pdf"/("MULTIMODEL_V2_SHADOW_"+days[1]+".pdf")) as doc:
                text = "".join(page.get_text() for page in doc)
                self.assertIn("Team A", text)
                self.assertIn("SHADOW", text)

    def test_audit_empty_archive_does_not_invent_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"shadow").mkdir()
            data = audit(tmp, [], "2026-11-20T11:00:00Z")
            self.assertEqual(data["unique_forecasts"], 0)
            self.assertEqual(data["summary"], [])
            self.assertIsNone(data["bookmaker_roi"])


if __name__ == "__main__":
    unittest.main()
