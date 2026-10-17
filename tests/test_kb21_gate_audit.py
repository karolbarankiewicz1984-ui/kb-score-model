import unittest
from tools.kb21_gate_audit import assess, audit


class GateAuditTests(unittest.TestCase):
    def test_missing_calendar_blocks_but_missing_xg_only_warns(self):
        result = assess({"fixture_id": 1, "event": "A - B", "api_goal_rates": {}})
        self.assertFalse(result["ready_for_review"])
        self.assertIn("OFFICIAL_FIXTURE_UNVERIFIED", result["blocking_reasons"])
        self.assertIn("MISSING_HOME_EXPECTED_GOALS", result["warnings"])
        self.assertNotIn("MISSING_HOME_EXPECTED_GOALS", result["blocking_reasons"])
        self.assertFalse(result["freeze_allowed"])

    def test_same_provider_is_not_independent(self):
        row = {"sources": ["API-Football fixtures", "API-Football historical fixtures"],
               "api_goal_rates": {}}
        result = assess(row)
        self.assertIn("ONLY_ONE_SOURCE_PROVIDER", result["blocking_reasons"])

    def test_even_complete_review_is_not_play(self):
        row = {"fixture_id": 2, "event": "A - B", "fixture_verified_official": True,
               "fixture_verified_independent": True,
               "sources": ["official", "independent"],
               "calendar_evidence": {"official": "official fixture reference",
                                     "independent": "independent fixture reference"},
               "structural_0_100": 70, "quality_0_100": 60, "matchup_0_100": 50,
               "home_expected_goals": 1.3, "away_expected_goals": 1.1,
               "api_goal_rates": {"home": {"sample_size": 10}, "away": {"sample_size": 10}}}
        result = assess(row)
        self.assertTrue(result["ready_for_review"])
        self.assertFalse(result["freeze_allowed"])
        self.assertFalse(result["original_scoring_recovered"])
        self.assertEqual(result["kb_status"], "NOT_ASSIGNED")
        self.assertEqual(audit({"date": "2030-01-01", "candidates": [row]})["kb_n_effect"], 0)

    def test_xg_and_goal_history_are_optional_even_when_provenance_reviewable(self):
        row = {"fixture_id": 2, "event": "A - B", "fixture_verified_official": True,
               "fixture_verified_independent": True,
               "sources": ["official competition", "independent provider"],
               "calendar_evidence": {"official": "url", "independent": "url"},
               "api_goal_rates": {}}
        result = assess(row)
        self.assertTrue(result["ready_for_review"])
        self.assertIn("MISSING_AWAY_EXPECTED_GOALS", result["warnings"])
        self.assertIn("GOAL_HISTORY_INSUFFICIENT_HOME", result["warnings"])
        self.assertEqual(result["blocking_reasons"], [])
        self.assertFalse(result["freeze_allowed"])
        audited = audit({"date": "2030-01-01", "candidates": [row]})
        self.assertEqual(audited["warning_counts"]["MISSING_HOME_EXPECTED_GOALS"], 1)
        self.assertEqual(audited["calendar_gate"], "UNVERIFIED")

    def test_invalid_optional_xg_does_not_grant_freeze(self):
        row = {"fixture_id": 3, "home_expected_goals": -3}
        result = assess(row)
        self.assertIn("OUT_OF_RANGE_HOME_EXPECTED_GOALS", result["warnings"])
        self.assertFalse(result["freeze_allowed"])


if __name__ == "__main__":
    unittest.main()
