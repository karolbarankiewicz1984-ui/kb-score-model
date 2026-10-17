import unittest
from tools.kb21_analyst_assessment import validate


def sample():
    evidence = [{"url": "https://example.org/match", "observed_at": "2026-10-17T09:00:00+02:00", "note": "Archived pre-match source"}]
    return {"fixture": "A - B", "market": "1X", "freeze_at": "2026-10-17T09:30:00+02:00",
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


if __name__ == "__main__":
    unittest.main()
