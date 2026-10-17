import unittest
from datetime import datetime, timezone
from tools.kb21_review_shortlist import choose, render


NOW = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


def candidate(id, kickoff, match=True, history=True):
    return {
        "fixture_id": id, "fixture": "Team A - Team B", "competition": "Premier League",
        "kickoff": kickoff, "date_warsaw": "2026-10-17",
        "independent_crosscheck": {"status": "MATCHED_FOR_REVIEW" if match else "NO_NAME_TIME_MATCH"},
        "pre_match_research": {
            "status": "PRIOR_GOAL_CONTEXT" if history else "NO_API_SNAPSHOT",
            "context": {"home": {"previous_completed_matches": 5}, "away": {"previous_completed_matches": 5}}
                       if history else None
        },
        "assessment": {"p_model": None, "str": None, "qual": None, "match": None}
    }


class ReviewShortlistTests(unittest.TestCase):
    def test_forward_only_and_no_inferred_sporting_probability(self):
        q = {"fixtures": [
            candidate("old", "2026-10-17T09:00:00Z"),
            candidate("strong", "2026-10-17T13:00:00Z"),
            candidate("weak", "2026-10-17T12:30:00Z", match=False, history=False)
        ]}
        result = choose(q, now=NOW)
        self.assertEqual([r["fixture_id"] for r in result["fixtures"]], ["strong", "weak"])
        self.assertEqual(result["excluded"]["started_or_past"], 1)
        self.assertEqual(result["fixtures"][0]["evidence_priority_only"], 4)
        self.assertIsNone(result["fixtures"][0]["assessment"]["p_model"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIn("NO PLAY", render(result))

    def test_limit_only_manual_validation(self):
        q = {"fixtures": [candidate(str(i), f"2026-10-18T{12+i:02d}:00:00Z")
                          for i in range(4)]}
        result = choose(q, now=NOW, limit=2)
        self.assertEqual(len(result["fixtures"]), 2)
        self.assertEqual(result["available_future_candidates"], 4)
        self.assertEqual(result["selection_limit_for_validation_only"], 2)

    def test_started_at_now_not_retrospectively_scored(self):
        result = choose({"fixtures": [candidate("one", "2026-10-17T10:00:00Z")]},
                        now=NOW)
        self.assertEqual(result["fixtures"], [])
        self.assertEqual(result["excluded"]["started_or_past"], 1)

    def test_duplicate_fixture_id_not_overcounted(self):
        row = candidate("a", "2026-10-17T15:00:00Z")
        result = choose({"fixtures": [row, dict(row)]}, now=NOW)
        self.assertEqual(result["available_future_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
