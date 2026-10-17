import json
import tempfile
import unittest
from pathlib import Path
from tools.kb21_assessment_queue import build


class AssessmentQueueTests(unittest.TestCase):
    def test_real_candidate_becomes_unscored_review_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixtures.json"
            path.write_text(json.dumps({"fixtures": [{
                "league": "eng.1", "event_id": "123", "home": "Home",
                "away": "Away", "kickoff": "2026-10-17T22:30:00Z",
                "competition": "Premier League", "source": "ESPN third-party"}]}))
            result = build([path, path])
        self.assertEqual(len(result["fixtures"]), 1)
        item = result["fixtures"][0]
        self.assertEqual(item["date_warsaw"], "2026-10-18")
        self.assertEqual(item["fixture_id"], "eng.1:123")
        self.assertIsNone(item["assessment"]["p_model"])
        self.assertIsNone(item["assessment"]["sport_score"])
        self.assertEqual(item["calendar_gate"], "BLOCKED")
        self.assertEqual(item["publication"], "DIAGNOSTIC / NO PLAY")

    def test_invalid_kickoff_is_not_assessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixtures.json"
            path.write_text(json.dumps({"fixtures": [{
                "league": "eng.1", "event_id": "123", "home": "Home",
                "away": "Away", "kickoff": "not-a-date"}]}))
            result = build([path])
        self.assertEqual(result["fixtures"], [])
        self.assertEqual(result["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
