"""Offline regression tests; no credentials, live API calls, or KB writes."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
with patch.object(sys, "argv", ["tests", "2030-01-02"]):
    import api_market_scan as raw
    import api_market_v3_enrich as enrich
    import api_market_report_diversify as publication
    import api_market_settle as settle
    import api_national_today_prefetch as prefetch
    import api_market_storage as storage
    import api_market_policy as policy
    import api_market_integrity as integrity


def item(line=0.5, score=70, **kwargs):
    result = dict(fixture_id=1, team_id=10, team_side="home", market="team_goals", line=line,
        kickoff="2030-01-02T20:00:00+00:00", api_pure_pct=80, final_assessment_pct=score,
        market_data={}, final_status="WATCH", market_signal="STRONG_WARNING",
        home="Home", away="Away", competition="Premier League", selection=f"Home over {line}",
        confidence_api=7, reliability_adjusted_pct=70)
    result.update(kwargs)
    return result


def fixture():
    return {"fixture": {"id": 1, "date": "2030-01-02T20:00:00+00:00", "status": {"short": "NS"}},
        "league": {"country": "England", "name": "Premier League"},
        "teams": {"home": {"id": 10, "name": "Home"}, "away": {"id": 20, "name": "Away"}}}


def history(count=5):
    return [{"fixture_id": 100+i, "date": f"2025-09-{i+1:02d}T18:00:00+00:00",
        "home_id": 10, "away_id": 20, "goals": {"home": 4, "away": 4},
        "league": "Premier League", "country": "England", "_category": "domestic",
        "teams": [dict(team_id=t, **{k: 20 for k in raw.MARKETS if k != "team_goals"}) for t in (10,20)]}
        for i in range(count)]


class PolicyTests(unittest.TestCase):
    def test_one_threshold_no_quantity_status_market_or_fixture_filter(self):
        candidates = [item(line=i+0.5, score=67, market="shots") for i in range(180)]
        candidates += [item(score=66.9), item(score=90)]
        ranked = policy.rank_positions(candidates, 67)
        self.assertEqual(len(ranked), 181)
        self.assertEqual(ranked[0]["final_assessment_pct"], 90)
        self.assertTrue(all(x["market_signal"] == "STRONG_WARNING" for x in ranked))

    def test_sts_is_not_falsely_verified(self):
        unknown = policy.sts_availability(item())
        self.assertEqual(unknown["status"], "unknown")
        actual = policy.sts_availability(item(market_data={"quotes":[{"bookmaker":"STS"}]}))
        self.assertEqual(actual["status"], "verified_quote")

    def test_practical_lines_are_preferred_without_hiding_other_results(self):
        candidates = [item(score=90, market="shots"),
                      item(score=68, market_data={"exact_line_available":True})]
        ranked = policy.rank_positions(candidates,67)
        self.assertEqual(len(ranked),2)
        self.assertEqual(ranked[0]["final_assessment_pct"],68)
        self.assertEqual(ranked[1]["final_assessment_pct"],90)

    def test_no_raw_coverage_l10_or_seven_match_gate(self):
        rows = history(1)
        candidate = raw.build_candidate(rows, fixture(), "home", "team_goals", 5.5)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["api_pure_pct"], 0)
        self.assertEqual(candidate["samples"]["own_available"], 1)

    def test_overlay_is_immutable_and_not_compounded(self):
        candidate = item()
        before = copy.deepcopy(candidate)
        market = {"market_probability_pct":90, "paired_books":6, "bookmaker_spread_pp":2, "exact_line_available":True}
        first = raw.apply_market_overlay(candidate, market, {})
        second = raw.apply_market_overlay(first, market, {})
        self.assertEqual(candidate, before)
        self.assertEqual(first["api_pure_pct"], 80)
        self.assertEqual(second["market_adjusted_pct"], first["market_adjusted_pct"])

    def test_dates_cannot_escape_api_directory(self):
        with self.assertRaises(ValueError):
            policy.target_date("../../model/KB_SCORE.md")

    def test_kb_paths_are_rejected(self):
        for path in ("model/KB_SCORE.md", "AKTUALNY_MODEL.md", "data/KB_N.json", "config/api_market.json"):
            with self.assertRaises(RuntimeError):
                integrity.assert_api_paths([path])


class IsolatedWorkspace(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.now = datetime(2030,1,2,10,tzinfo=timezone.utc)
        self.policy = policy.load_policy()
        self.quiet = redirect_stdout(io.StringIO())
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None,None,None)
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def freeze(self, candidates, now=None):
        return storage.archive_publication({"date":"2030-01-02", "background_candidates":candidates,
            "top_positions":policy.rank_positions(candidates,67)}, "2030-01-02", self.policy, now or self.now)


class FreezeTests(IsolatedWorkspace):
    def test_immutable_versions_and_earliest_prediction_deduplication(self):
        first = self.freeze([item(),item(line=1.5,score=50)])
        path = Path("data/api_football/predictions/2030-01-02") / (first["publication"]["id"]+".json")
        original = path.read_bytes()
        self.freeze([item(score=95),item(line=1.5,score=90)], self.now+timedelta(hours=1))
        self.assertEqual(path.read_bytes(), original)
        chosen = storage.frozen_candidates("2030-01-02")
        self.assertEqual(len(chosen),2)
        self.assertEqual(chosen[0]["final_assessment_pct"],70)
        lower = next(x for x in chosen if x["line"]==1.5)
        self.assertFalse(lower["published"])
        self.assertTrue(lower["ever_published"])

    def test_post_start_and_legacy_data_do_not_train(self):
        path=Path("data/api_football/market_scan/2030-01-02.json")
        path.parent.mkdir(parents=True)
        legacy=storage.dumps({"top_positions":[item()]})
        path.write_text(legacy)
        frozen=self.freeze([item(kickoff="2030-01-02T09:00:00+00:00")])
        self.assertEqual(frozen["top_positions"],[])
        self.assertEqual(storage.frozen_candidates("2030-01-02"),[])
        archived=list(Path("data/api_football/predictions/2030-01-02").glob("legacy-*.json"))
        self.assertEqual(archived[0].read_text(),legacy)

    def test_identical_archive_cannot_be_overwritten(self):
        self.freeze([item()])
        with self.assertRaises(FileExistsError):
            self.freeze([item()])

    def test_settlement_includes_rejected_positions_and_preserves_success_on_retry(self):
        self.freeze([item(),item(line=1.5,score=50)])
        def api(endpoint,**kwargs):
            if endpoint=="fixtures":
                return {"response":[{"fixture":{"status":{"short":"FT"}}, "goals":{"home":1,"away":0}}]},{}
            return {"response":[]},{}
        with patch.object(raw,"api_get",side_effect=api):
            settle.main()
            settle.main()
        path=Path("data/api_football/calibration/2030-01-02.json")
        rows=json.loads(path.read_text())["observations"]
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(r["hit"] for r in rows),1)
        with patch.object(raw,"api_get",side_effect=RuntimeError("temporary outage")):
            settle.main()
        self.assertEqual(json.loads(path.read_text())["observations"],rows)
        summary=json.loads(Path("data/api_football/calibration/_summary.json").read_text())
        self.assertEqual(summary["observations"],2)
        self.assertEqual(summary["distinct_fixtures"],1)
        self.assertIn("published:False",summary["groups"])

    def test_prefetch_uses_nonpaged_fixtures_and_reports_errors(self):
        with patch.object(raw,"api_get",return_value=({"errors":{"page":"not supported"}},{})) as call:
            with self.assertRaises(RuntimeError):
                prefetch.main()
            self.assertNotIn("page",call.call_args.kwargs)

    def test_failed_refresh_keeps_existing_cache(self):
        path=Path("data/api_football/national_dynamic/team_10.json")
        path.parent.mkdir(parents=True)
        text=storage.dumps({"rows":history()})
        path.write_text(text)
        game=fixture();game["league"]={"name":"UEFA Nations League"}
        with patch.object(raw,"api_get",return_value=({"errors":{"quota":"limit"}},{})):
            summary=enrich.refresh_national_history([game],[])
        self.assertEqual(path.read_text(),text)
        self.assertEqual(len(summary["errors"]),2)

    def test_full_mock_pipeline_preserves_core_and_has_unlimited_output(self):
        sentinel=Path("model/KB_SCORE.md")
        sentinel.parent.mkdir()
        sentinel.write_text("protected-core")
        def api(endpoint,**kwargs):
            if endpoint=="fixtures":
                return {"response":[fixture()],"errors":[]},{}
            return {"response":[],"errors":[],"paging":{"total":1}},{}
        with patch.object(raw,"api_get",side_effect=api), patch.object(raw,"load_rows",return_value=history()):
            raw.main()
            source=json.loads(Path("data/api_football/market_work/2030-01-02.json").read_text())
            pure={policy.candidate_key(x):x["api_pure_pct"] for x in source["background_candidates"]}
            enrich.main()
            enriched=json.loads(Path("data/api_football/market_work/2030-01-02.json").read_text())
            for row in enriched["background_candidates"]:
                self.assertEqual(row["api_pure_pct"],pure[policy.candidate_key(row)])
            publication.main()
        output=json.loads(Path("data/api_football/market_scan/2030-01-02.json").read_text())
        self.assertGreater(len(output["top_positions"]),10)
        self.assertEqual(len(output["background_candidates"]),len(source["background_candidates"]))
        self.assertEqual(sentinel.read_text(),"protected-core")
        integrity.assert_api_paths([str(p) for p in Path(".").rglob("*") if p.is_file() and p!=sentinel])


if __name__ == "__main__":
    unittest.main()
