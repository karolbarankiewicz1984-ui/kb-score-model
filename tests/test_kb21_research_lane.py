"""Research-first produces useful prospective briefs WITHOUT betting predictions."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_calendar_review_packet import data
from tools.kb21_calendar_review_packet import build as review_packet
from tools.kb21_research_lane import build, render_md, write_reports, render_pdf

UTC = timezone.utc
NOW = datetime(2026, 10, 17, 9, tzinfo=UTC)
THIRD = "2026-10-19"


def examples():
    q, gate, dashboard = data()
    # Date-three can legitimately have NO candidates and still yield one PDF.
    q["days"].append(THIRD)
    gate["days"][THIRD] = copy.deepcopy(gate["days"]["2026-10-18"])
    dashboard["days"].append(THIRD)
    for row in dashboard["rows"][:14]:
        extra = copy.deepcopy(row)
        extra["day"] = THIRD
        extra["espn_candidates"] = 0
        dashboard["rows"].append(extra)
    packet = review_packet(q, gate, dashboard, now=NOW)
    return q, packet


class ResearchFirstTests(unittest.TestCase):
    def test_three_days_research_does_not_need_global_calendar_pass(self):
        q, packet = examples()
        result = build(q, packet, now=NOW)
        self.assertEqual([r["day"] for r in result["reports"]], q["days"])
        self.assertEqual([r["selected_for_source_review"]
                          for r in result["reports"]], [1, 1, 0])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertFalse(result["safe_to_publish_play"])
        self.assertEqual(result["actual_betting_recommendations"], 0)
        self.assertEqual(result["analyst_scores_generated"], 0)
        self.assertFalse(result["old_historical_n_written"])
        self.assertTrue(result["api_market_remains_separate"])
        for day in result["reports"]:
            for item in day["fixtures"]:
                for key in ("sport_score", "str_35", "qual_35",
                            "match_30", "pre_price_p_model", "odds", "ev"):
                    self.assertIsNone(item[key], key)
                self.assertEqual(item["publication"], "DIAGNOSTIC / NO PLAY")
                self.assertTrue(item["requires_independent_human_analysis"])

    def test_started_games_never_get_pseudo_premarket_assessment(self):
        q, packet = examples()
        result = build(q, packet, now=datetime(2026, 10, 18, 20, tzinfo=UTC))
        self.assertEqual([r["selected_for_source_review"] for r
                          in result["reports"]], [0, 0, 0])
        self.assertEqual(result["reports"][0]["excluded"]["already_started"], 1)

    def test_matching_early_official_snapshot_prioritizes_source_readiness_only(self):
        q, packet = examples()
        row = next(r for r in packet["rows"]
                   if r["day"] == q["days"][1] and r["league_id"] == "bel.1")
        row["fixtures"][0]["early_official_archive"] = {
            "status": "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"}
        result = build(q, packet, now=NOW)
        game = result["reports"][1]["fixtures"][0]
        self.assertEqual(game["source_evidence_priority_only"], 3)
        self.assertIsNone(game["pre_price_p_model"])
        self.assertIn("NO PLAY", render_md(result["reports"][1]))

    def test_kickoff_conflict_never_becomes_high_confidence(self):
        q, packet = examples()
        row = next(r for r in packet["rows"]
                   if r["day"] == q["days"][0] and r["league_id"] == "eng.1")
        row["fixtures"][0]["organizer_crosscheck"] = {
            "organizer_comparator_status": "OFFICIAL_KICKOFF_CONFLICT"}
        result = build(q, packet, now=NOW)
        self.assertEqual(result["reports"][0]["fixtures"][0][
            "source_evidence_priority_only"], 0)
        self.assertEqual(result["reports"][0]["excluded"]["unresolved_source"], 1)

    def test_actual_goals_are_not_xg(self):
        q, packet = examples()
        q["fixtures"][0]["pre_match_research"] = {
            "context": {
                "home": {"previous_completed_matches": 6,
                         "goals_for_per_match": 1.5,
                         "goals_against_per_match": 0.8},
                "away": {"previous_completed_matches": 4,
                         "goals_for_per_match": 1.7,
                         "goals_against_per_match": 0.9}}}
        result = build(q, packet, now=NOW)
        record = result["reports"][0]["fixtures"][0]
        self.assertEqual(record["previous_completed_match_goals"]["home"]["sample_size"], 6)
        self.assertNotIn("away", record["previous_completed_match_goals"])
        self.assertIn("NIE xG", render_md(result["reports"][0]))

    def test_refuse_false_gate_approval_or_malformed_date_scope(self):
        q, packet = examples()
        packet["calendar_gate"] = "PASS_MANUAL"
        with self.assertRaises(ValueError):
            build(q, packet, now=NOW)
        _, packet = examples()
        q["days"] = q["days"][:2]
        with self.assertRaises(ValueError):
            build(q, packet, now=NOW)

    def test_refuse_fixture_id_or_kickoff_divergence(self):
        q, packet = examples()
        q["fixtures"][0]["kickoff"] = "2026-10-17T20:00:00+02:00"
        with self.assertRaisesRegex(ValueError, "kickoff mismatch"):
            build(q, packet, now=NOW)
        q, packet = examples()
        packet["rows"][0]["fixtures"].append(copy.deepcopy(packet["rows"][0]["fixtures"][0]))
        with self.assertRaisesRegex(ValueError, "missing/duplicate"):
            build(q, packet, now=NOW)

    def test_pdf_generation_one_per_day_including_no_candidates(self):
        try:
            import reportlab
        except ImportError:
            self.skipTest("ReportLab intentionally installed in the PDF job")
        q, packet = examples()
        report = build(q, packet, now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_reports(report, directory)
            self.assertEqual(len(paths), 3)
            for path in paths:
                blob = Path(path).read_bytes()
                self.assertGreater(len(blob), 1200)
                self.assertTrue(blob.startswith(b"%PDF-"))
            files = json.loads(Path(directory, "KB21_RESEARCH_MANIFEST.json").read_text())
            self.assertEqual(len(files["pdf_files"]), 3)
            self.assertFalse(files["safe_to_publish_play"])


if __name__ == "__main__":
    unittest.main()
