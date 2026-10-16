import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from api_market_playable_shadow import eligible_quotes, evaluate, report

class PlayableShadowTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"min_quoted_odds": 1.20, "preserve_min_final_score": 67}
        self.base = {"fixture_id": 1, "kickoff": "2026-10-08T18:00:00Z", "home":"A", "away":"B",
                     "selection":"under 2.5", "direction":"under", "final_assessment_pct": 75,
                     "api_pure_pct": 80}
    def item(self, quotes):
        return dict(self.base, market_data={"quotes": quotes})
    def test_boundary(self):
        item = self.item([{"bookmaker":"X","under_odd":1.19},{"bookmaker":"Y","under_odd":1.20}])
        self.assertEqual([q["odd"] for q in eligible_quotes(item)], [1.20])
    def test_other_bookmaker_qualifies_without_sts(self):
        positions, _ = evaluate({"background_candidates":[self.item([{"bookmaker":"Bet365","under_odd":1.31}])]}, self.cfg)
        self.assertEqual(len(positions), 1)
        self.assertIsNone(positions[0]["sts_quote"])
        self.assertIsNone(positions[0]["superbet_quote"])
    def test_superbet_and_sts(self):
        positions, _ = evaluate({"background_candidates":[self.item([{"bookmaker":"STS","under_odd":1.22},{"bookmaker":"Superbet","under_odd":1.25}])]}, self.cfg)
        self.assertEqual(positions[0]["sts_quote"], 1.22)
        self.assertEqual(positions[0]["superbet_quote"], 1.25)
    def test_rejection_and_direction(self):
        low = dict(self.item([{"bookmaker":"X","over_odd":1.80,"under_odd":1.19}]))
        weak = dict(self.item([{"bookmaker":"X","under_odd":1.30}]), final_assessment_pct=66)
        positions, reasons = evaluate({"background_candidates":[low,weak]}, self.cfg)
        self.assertEqual(positions, [])
        self.assertEqual(reasons, {"no_eligible_quote":1,"below_score_threshold":1})
    def test_invalid_prices(self):
        item = self.item([{"under_odd":float("nan")},{"under_odd":True},{"under_odd":1.3}])
        self.assertEqual(len(eligible_quotes(item)), 1)
    def test_export_has_exact_market_and_quote_timestamp(self):
        from api_market_playable_shadow import export_position
        item=self.item([{"bookmaker":"Betano","under_odd":1.35,
                         "selected_odd":1.35,
                         "provider_updated_at":"2026-10-16T08:15:00+00:00",
                         "bookmaker_id":32}])
        item.update(best_quote={"bookmaker":"Betano","odd":1.35},
                    market="corners",market_scope="team",team_side="home",
                    bet_id=57,line=6.5,kickoff="2026-10-17T18:00:00+02:00")
        exported=export_position(item,"2026-10-17")
        self.assertEqual(exported["line"],6.5)
        self.assertEqual(exported["market"],"corners")
        self.assertEqual(exported["direction"],"under")
        self.assertEqual(exported["best_quote"]["provider_updated_at"],"2026-10-16T08:15:00+00:00")
        self.assertFalse(exported["verified_live_in_polish_bookmaker"])

    def test_report_json_includes_full_positions_not_only_counts(self):
        one=self.item([{"bookmaker":"Betano","under_odd":1.23,
                        "selected_odd":1.23,
                        "provider_updated_at":"2026-10-16T08:10:00+00:00"}])
        one.update(market="fouls",market_scope="match",line=23.5,direction="under")
        _, exported=report({"date":"2026-10-17","background_candidates":[one]},self.cfg)
        self.assertEqual(exported["published_count"],1)
        self.assertEqual(len(exported["positions"]),1)
        self.assertEqual(exported["positions"][0]["selection"],"under 2.5")
        self.assertEqual(exported["positions"][0]["best_quote"]["odd"],1.23)
        self.assertEqual(exported["schema"],"api-market-playable-export-v2")
        self.assertFalse(exported["model_score_is_probability"])

    def test_report(self):
        markdown, audit = report({"date":"2026-10-08","background_candidates":[self.item([{"bookmaker":"X","under_odd":1.21}])]},self.cfg)
        self.assertIn("niepotwierdzone", markdown)
        self.assertEqual(audit["published_count"],1)

if __name__ == "__main__":
    unittest.main()
