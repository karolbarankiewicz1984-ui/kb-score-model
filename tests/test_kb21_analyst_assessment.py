import unittest
from tools.kb21_analyst_assessment import validate


def sample():
    evidence = [{"url": "https://example.org/match", "observed_at": "2026-10-17T09:00:00+02:00", "note": "Archived pre-match source"}]
    return {"fixture": "A - B", "market": "1X", "freeze_at": "2026-10-17T09:30:00+02:00",
            "kickoff": "2026-10-17T18:00:00+02:00",
            "analyst": "manual", "reasoning": "Historical rubric exercise",
            "str": 33, "qual": 31, "match": 26,
            "str_evidence": evidence, "qual_evidence": evidence, "match_evidence": evidence,
            "p_model": 0.82, "p_model_method": "Documented analyst estimate", "confidence": 8}


class AnalystAssessmentTests(unittest.TestCase):
    def test_valid_historical_shape_requires_review(self):
        result = validate(sample())
        self.assertEqual(result["sport_score"], 90)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")

    def test_rejects_out_of_range(self):
        candidate = sample()
        candidate["str"] = 36
        self.assertEqual(validate(candidate)["status"], "INVALID")

    def test_rejects_probability_without_method(self):
        candidate = sample()
        del candidate["p_model_method"]
        self.assertEqual(validate(candidate)["status"], "INVALID")

    def test_missing_evidence_rejected(self):
        candidate = sample()
        candidate["qual_evidence"] = []
        self.assertEqual(validate(candidate)["status"], "INVALID")


    def test_rejects_freeze_after_kickoff(self):
        candidate = sample()
        candidate["freeze_at"] = "2026-10-17T19:00:00+02:00"
        result = validate(candidate)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("before kickoff" in msg for msg in result["errors"]))
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")

    def test_rejects_late_evidence(self):
        candidate = sample()
        candidate["str_evidence"] = [{
            "url": "https://example.org", "observed_at": "2026-10-17T09:31:00+02:00",
            "note": "Source captured after freeze"
        }]
        result = validate(candidate)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("after pre-market freeze" in msg for msg in result["errors"]))

    def test_rejects_price_in_pre_market_stage(self):
        candidate = sample()
        candidate["odds"] = 1.75
        self.assertEqual(validate(candidate)["status"], "INVALID")

    def test_requires_probability_and_timezone(self):
        candidate = sample()
        candidate["p_model"] = None
        candidate["freeze_at"] = "2026-10-17T09:30:00"
        result = validate(candidate)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["p_model"])

    def test_distinct_analyst_probability_at_similar_score(self):
        # The original historical cases disprove a score-to-P(model) mapping.
        norway = sample()
        norway.update({"fixture": "Norway - Denmark", "str": 31, "qual": 29,
                       "match": 24, "p_model": .62})
        result = validate(norway)
        self.assertEqual(result["sport_score"], 84)
        self.assertEqual(result["p_model"], .62)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")


    def test_malformed_source_url_is_invalid_not_crash(self):
        candidate = sample()
        candidate["str_evidence"] = [{
            "url": "https://[invalid-ipv6", "observed_at": "2026-10-17T09:00:00+02:00",
            "note": "Malformed URL"
        }]
        result = validate(candidate)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("Invalid str_evidence[0] URL/note", result["errors"])


if __name__ == "__main__":
    unittest.main()
