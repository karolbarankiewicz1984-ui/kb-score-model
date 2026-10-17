import unittest

from tools.kb21_market_review import review


def assessment():
    evidence = [{"url": "https://example.org/source", "observed_at": "2026-10-17T09:00:00+02:00",
                 "note": "Pre-market measurements"}]
    return {"fixture_id": "eng.1:123", "fixture": "A - B", "market": "1X",
            "freeze_at": "2026-10-17T09:30:00+02:00",
            "kickoff": "2026-10-17T18:00:00+02:00",
            "analyst": "reviewer", "reasoning": "Evidence-led historical rubric exercise",
            "str": 33, "qual": 31, "match": 26,
            "str_evidence": evidence, "qual_evidence": evidence,
            "match_evidence": evidence, "p_model": .82,
            "p_model_method": "Documented analyst estimate before viewing odds",
            "confidence": 8}


def quote():
    return {"fixture_id": "eng.1:123", "market": "1X", "odds": 1.40,
            "bookmaker": "test quotation", "quoted_at": "2026-10-17T09:31:00+02:00"}


class MarketReviewTests(unittest.TestCase):
    def test_original_ev_guideline_without_auto_play(self):
        result = review(assessment(), quote())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["sport_score"], 90)
        self.assertAlmostEqual(result["ev"], .148)
        self.assertEqual(result["min_ev_guideline"], .02)
        self.assertTrue(result["meets_ev_guideline"])
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")

    def test_quote_before_freeze_blocked(self):
        p = quote()
        p["quoted_at"] = "2026-10-17T09:00:00+02:00"
        result = review(assessment(), p)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["ev"])

    def test_wrong_market_or_fixture_blocked(self):
        for field in ("market", "fixture_id"):
            with self.subTest(field=field):
                p = quote()
                p[field] = "wrong"
                self.assertEqual(review(assessment(), p)["status"], "BLOCKED")

    def test_missing_probability_or_confidence_below_five(self):
        a = assessment()
        a["p_model"] = None
        self.assertEqual(review(a, quote())["status"], "BLOCKED")
        a["p_model"] = .82
        a["confidence"] = 4
        result = review(a, quote())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["meets_ev_guideline"])
        self.assertIsNone(result["min_ev_guideline"])

    def test_price_after_kickoff_blocked(self):
        p = quote()
        p["quoted_at"] = "2026-10-17T20:00:00+02:00"
        self.assertEqual(review(assessment(), p)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
