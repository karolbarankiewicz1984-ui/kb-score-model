import unittest
from multimodel_v2.transition_policy import classify_sources, SourcePolicy


class TransitionPolicyTests(unittest.TestCase):
    def test_pitchapi_does_not_create_picks(self):
        r = classify_sources("2026-11-03", pitchapi_context={"matches": [1]},
                             api_overlay={"schema": "api-market-snapshot-v1",
                                          "date": "2026-11-03"})
        self.assertTrue(r["pitchapi_context_available"])
        self.assertTrue(r["overlay_context_only"])
        self.assertFalse(r["ready_to_publish_bets"])
        self.assertFalse(r["composite_top_authorized"])
        self.assertIsNone(r["pitchapi_internal_request_cap"])

    def test_native_source_still_needs_independent_quote(self):
        r = classify_sources("2026-11-03", scored_api_publication={
            "schema": "api-market-scan-v3", "date": "2026-11-03"})
        self.assertTrue(r["api_only_candidates_may_be_verified"])
        self.assertFalse(r["bookmaker_quotes_verified"])
        self.assertFalse(r["ready_to_publish_bets"])

    def test_wrong_day_rejected(self):
        r = classify_sources("2026-11-04", scored_api_publication={
            "schema": "api-market-scan-v3", "date": "2026-11-03"})
        self.assertFalse(r["native_api_scored_source_present"])


if __name__ == "__main__":
    unittest.main()
