"""End-to-end recovery smoke test: discovery -> human scoring -> market review."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.kb21_assessment_queue import build
from tools.kb21_analyst_assessment import validate
from tools.kb21_market_review import review
from tools.kb21_queue_report import render_day, write_reports


class PipelineIntegrationTests(unittest.TestCase):
    def test_realistic_forward_path_stays_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fixtures.json"
            source.write_text(json.dumps({
                "date": "2026-10-17", "errors": [],
                "fixtures": [{"league": "eng.1", "event_id": "123",
                              "home": "Home", "away": "Away",
                              "kickoff": "2026-10-17T16:00:00Z",
                              "competition": "Premier League",
                              "source": "ESPN third-party"}]
            }), encoding="utf-8")
            queue = build([source])
            self.assertEqual(queue["calendar_gate"], "BLOCKED")
            fixture = queue["fixtures"][0]
            self.assertEqual(fixture["kickoff"], "2026-10-17T18:00:00+02:00")
            form = fixture["assessment"]
            self.assertEqual(validate(form)["status"], "INVALID")
            evidence = [{"url": "https://example.org/source",
                         "observed_at": "2026-10-17T09:00:00+02:00",
                         "note": "Source checked before freeze"}]
            form.update({
                "market": "1X", "freeze_at": "2026-10-17T09:30:00+02:00",
                "analyst": "test analyst", "reasoning": "Evidence-led review",
                "str": 33, "qual": 31, "match": 26, "str_evidence": evidence,
                "qual_evidence": evidence, "match_evidence": evidence,
                "p_model": .82, "p_model_method": "Analyst judgement before odds",
                "confidence": 8
            })
            self.assertEqual(validate(form)["status"], "REVIEW_REQUIRED")
            quote = {"market": "1X", "fixture_id": "eng.1:123",
                     "odds": 1.40, "bookmaker": "test price",
                     "quoted_at": "2026-10-17T09:31:00+02:00"}
            reviewed = review(form, quote)
            self.assertEqual(reviewed["status"], "REVIEW_REQUIRED")
            self.assertAlmostEqual(reviewed["ev"], .148)
            self.assertEqual(reviewed["publication"], "DIAGNOSTIC / NO PLAY")
            day_report = render_day(queue, "2026-10-17")
            self.assertIn("90", day_report)
            self.assertIn("82.0%", day_report)
            self.assertIn("Calendar Gate: BLOCKED", day_report)
            self.assertNotIn("Decyzja: PLAY", day_report)
            days = write_reports(queue, Path(tmp) / "out")
            self.assertEqual(days, ["2026-10-17"])
            self.assertTrue((Path(tmp) / "out" /
                             "KB21_ANALYST_QUEUE_2026-10-17.md").exists())


if __name__ == "__main__":
    unittest.main()
