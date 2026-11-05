import unittest
from multimodel_v2.comparison_only import compare_frozen_forecasts

BASE = dict(fixture_id="f1", league="EPL", kickoff_utc="2026-11-08T16:00:00Z",
            frozen_at_utc="2026-11-07T10:00:00Z", model_id="multimodel",
            model_version="frozen", p_home=.4, p_draw=.3, p_away=.3)

class ComparisonOnlyTests(unittest.TestCase):
    def test_comparison_never_promotes(self):
        other = dict(BASE, model_id="dixon-coles", p_home=.5, p_draw=.2)
        rows = compare_frozen_forecasts(BASE, [other], as_of="2026-11-07T11:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ranking_weight"], 0)
        self.assertFalse(rows[0]["production_eligible"])
        self.assertTrue(rows[0]["comparison_only"])

    def test_different_fixture_cannot_be_compared(self):
        with self.assertRaisesRegex(ValueError, "fixture_mismatch"):
            compare_frozen_forecasts(BASE, [dict(BASE, fixture_id="f2", model_id="dc")],
                                     as_of="2026-11-07T11:00:00Z")

    def test_same_model_cannot_self_validate(self):
        with self.assertRaisesRegex(ValueError, "baseline_model_not_independent"):
            compare_frozen_forecasts(BASE, [BASE], as_of="2026-11-07T11:00:00Z")
