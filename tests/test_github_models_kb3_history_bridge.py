import unittest
from github_models.kb3_history_bridge import import_verified_results

ROW = dict(fixture_id="m1", league="Serie A", home="A", away="B",
           home_goals=1, away_goals=0, status="FINISHED",
           completed_at_utc="2026-11-01T20:00:00Z",
           published_at_utc="2026-11-01T20:10:00Z",
           source_provider="PitchAPI", source_record_id="m1")

class KB3BridgeTests(unittest.TestCase):
    def test_verified_final_result_only(self):
        out = import_verified_results([ROW], as_of_utc="2026-11-05T12:00:00Z")
        self.assertEqual(out["accepted_count"], 1)
        self.assertNotIn("source_provider", out["accepted"][0])

    def test_no_unproven_publication(self):
        out = import_verified_results([dict(ROW, published_at_utc=None)],
                                      as_of_utc="2026-11-05T12:00:00Z")
        self.assertEqual(out["accepted_count"], 0)

    def test_no_forecast_data_import(self):
        out = import_verified_results([dict(ROW, kb3_probability=.95)],
                                      as_of_utc="2026-11-05T12:00:00Z")
        self.assertNotIn("kb3_probability", out["accepted"][0])

    def test_future_publication_rejected(self):
        out = import_verified_results([dict(ROW, published_at_utc="2026-11-06T12:00:00Z")],
                                      as_of_utc="2026-11-05T12:00:00Z")
        self.assertEqual(out["accepted_count"], 0)
