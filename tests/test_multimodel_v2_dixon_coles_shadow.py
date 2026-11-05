import unittest
from multimodel_v2.dixon_coles_shadow import forecast_dixon_coles

FIXTURE = dict(fixture_id="future-1", league="EPL", home="A", away="B",
               kickoff_utc="2026-11-08T16:00:00Z")
HISTORY = [dict(league="EPL", home="A", away="B", home_goals=1, away_goals=0,
                completed_at_utc="2026-11-01T16:00:00Z",
                published_at_utc="2026-11-01T18:00:00Z")]

class DixonColesShadowTests(unittest.TestCase):
    def test_insufficient_history_blocks_before_optional_import(self):
        with self.assertRaisesRegex(ValueError, "insufficient_verified_training_matches"):
            forecast_dixon_coles(HISTORY, FIXTURE, frozen_at_utc="2026-11-07T10:00:00Z",
                                 model_version="pinned-sha", min_matches=30)

    def test_future_publication_is_not_training(self):
        history = [dict(HISTORY[0], published_at_utc="2026-11-08T17:00:00Z")]
        with self.assertRaisesRegex(ValueError, "insufficient_verified_training_matches"):
            forecast_dixon_coles(history, FIXTURE, frozen_at_utc="2026-11-07T10:00:00Z",
                                 model_version="pinned-sha", min_matches=1)

    def test_xg_provenance_is_required(self):
        with self.assertRaisesRegex(ValueError, "xg_provenance_missing"):
            forecast_dixon_coles(HISTORY, FIXTURE, frozen_at_utc="2026-11-07T10:00:00Z",
                                 model_version="pinned-sha", min_matches=1, xg_weight=.5)

    def test_no_post_kickoff_freeze(self):
        with self.assertRaisesRegex(ValueError, "freeze_must_precede_kickoff"):
            forecast_dixon_coles(HISTORY, FIXTURE, frozen_at_utc="2026-11-08T18:00:00Z",
                                 model_version="pinned-sha", min_matches=1)
