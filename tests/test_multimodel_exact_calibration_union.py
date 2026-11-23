"""Fixture-level calibration readiness, no correlated-ticket inflation."""
import unittest
from github_models.multimodel_calibration_gate import report

def replay(*,ids=None):
    v={"schema":"github-models-oddspapi-frozen-audit-v1",
       "as_of_utc":"2026-11-23T10:00:00Z",
       "unique_settled_fixtures":2,
       "settled_selection_quotes":12,
       "status_counts":{"settled":12,"unresolved":3},
       "unresolved_reasons":{"no_exact_verified_outcome":3},
       "by_market":[{"variant":"model_only","market":"goals","matches":2,"n":5},
                    {"variant":"model_only","market":"corners","matches":1,"n":7},
                    {"variant":"market_50_50_shadow","market":"goals","matches":2,"n":5}]}
    if ids is not None:
        v["settled_fixture_ids"]=ids
    return v

def shadow(*,fixture="b"):
    return {"schema":"multimodel-priced-shadow-outcomes-v1",
            "as_of_utc":"2026-11-23T11:00:00Z",
            "status":{"settled":1},
            "status_reason_counts":{},
            "entries":[{"fixture_id":fixture,"status":"settled","market":"btts",
                        "bookmaker":"superbet.pl",
                        "official_bookmaker_settlement_verified":False,
                        "price":1.25,"p_model":.8,"hit":True}]}

class ReadinessUnion(unittest.TestCase):
    def test_exact_union_of_overlapping_models_is_not_max_lower_bound(self):
        got=report(replay(ids=["a","b"]),shadow(fixture="c"))
        self.assertEqual(got["combined_distinct_fixtures_exact"],3)
        self.assertEqual(got["distinct_fixtures_used_for_gate"],3)
        self.assertEqual(got["conservative_max_distinct_fixtures"],2)
        self.assertEqual(got["fixtures_remaining_to_100_review"],97)
        self.assertTrue(got["exact_cross_model_fixture_union_verified"])
        self.assertEqual(got["abc_market_readiness"]["goals"]["settled_quotes"],5)
        self.assertFalse(got["calibration_authorized"])
        self.assertFalse(got["model_weights_changed"])
        self.assertEqual(got["holdout_plan"]["status"],"not_constructed_or_scored")

    def test_shared_fixture_is_counted_once_and_old_schema_is_conservative(self):
        got=report(replay(ids=["a","b"]),shadow(fixture="b"))
        self.assertEqual(got["combined_distinct_fixtures_exact"],2)
        self.assertEqual(got["shared_abc_shadow_fixtures_exact"],1)
        old=report(replay(),shadow(fixture="c"))
        self.assertFalse(old["exact_cross_model_fixture_union_verified"])
        self.assertIsNone(old["combined_distinct_fixtures_exact"])
        self.assertEqual(old["distinct_fixtures_used_for_gate"],2)

    def test_invalid_fixture_ids_cannot_promote_calibration(self):
        for invalid in [["a","a"],["a"],["a",None]]:
            with self.subTest(ids=invalid):
                with self.assertRaisesRegex(ValueError,"invalid_independent_abc_fixture_ids"):
                    report(replay(ids=invalid),shadow())

    def test_enough_fixtures_alone_never_authorizes_weights(self):
        payload=replay(ids=[str(i) for i in range(100)])
        payload["unique_settled_fixtures"]=100
        got=report(payload,shadow())
        self.assertTrue(got["minimum_100_distinct_match_review"])
        self.assertFalse(got["holdout_evidence_available"])
        self.assertFalse(got["calibration_authorized"])
        self.assertFalse(got["model_weights_changed"])

if __name__=="__main__":
    unittest.main()
