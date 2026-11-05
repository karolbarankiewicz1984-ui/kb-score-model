import unittest
from multimodel_v2.historical_result_audit import audit_historical_results

VALID = dict(fixture_id="f1", league="EPL", home="A", away="B",
             home_goals=2, away_goals=1,
             completed_at_utc="2026-10-20T20:00:00Z",
             published_at_utc="2026-10-20T20:05:00Z")

class HistoricalResultAuditTests(unittest.TestCase):
    def test_valid_record(self):
        result = audit_historical_results([VALID], as_of_utc="2026-10-21T12:00:00Z")
        self.assertEqual(result["accepted"], 1)

    def test_missing_final_score_is_not_training_data(self):
        result = audit_historical_results([dict(VALID, home_goals=None)], as_of_utc="2026-10-21T12:00:00Z")
        self.assertEqual(result["reasons"]["missing_verified_fields"], 1)

    def test_future_publication_rejected(self):
        result = audit_historical_results([dict(VALID, published_at_utc="2026-10-22T20:00:00Z")], as_of_utc="2026-10-21T12:00:00Z")
        self.assertEqual(result["reasons"]["not_known_before_cutoff"], 1)

    def test_duplicate_rejected(self):
        result = audit_historical_results([VALID, VALID], as_of_utc="2026-10-21T12:00:00Z")
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["reasons"]["duplicate_fixture"], 1)

    def test_publication_cannot_precede_completion(self):
        result = audit_historical_results([dict(VALID, published_at_utc="2026-10-19T20:00:00Z")], as_of_utc="2026-10-21T12:00:00Z")
        self.assertEqual(result["reasons"]["publication_before_completion"], 1)
