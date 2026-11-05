import unittest
from multimodel_v2.external_model_shadow import validate_shadow_prediction

class ExternalShadowContractTests(unittest.TestCase):
    def test_valid_and_invalid_sum(self):
        row = dict(fixture_id='f1', league='EPL', kickoff_utc='2026-11-08T16:00:00Z', frozen_at_utc='2026-11-07T10:00:00Z', model_id='dc', model_version='v1', p_home=.4, p_draw=.3, p_away=.3)
        self.assertEqual(validate_shadow_prediction(row, as_of='2026-11-07T11:00:00Z')['fixture_id'], 'f1')
        with self.assertRaises(ValueError):
            validate_shadow_prediction(dict(row, p_away=.2), as_of='2026-11-07T11:00:00Z')
    def test_future_freeze_rejected(self):
        row = dict(fixture_id='f1', league='EPL', kickoff_utc='2026-11-08T16:00:00Z', frozen_at_utc='2026-11-07T10:00:00Z', model_id='dc', model_version='v1', p_home=.4, p_draw=.3, p_away=.3)
        with self.assertRaises(ValueError):
            validate_shadow_prediction(row, as_of='2026-11-06T11:00:00Z')
