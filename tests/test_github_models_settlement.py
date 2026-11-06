import unittest
from github_models.settlement import settle

class SettlementTests(unittest.TestCase):
    def test_future_match_stays_pending(self):
        queue = {"fixtures": [{"fixture_id": "x", "kickoff_utc": "2026-11-08T18:00:00Z", "league": "Ligue 1", "home": "A", "away": "B"}]}
        pred = {"predictions": [{"fixture_id": "x", "model_id": "elo", "frozen_at_utc": "2026-11-06T08:00:00Z", "p_home": .4, "p_draw": .3, "p_away": .3}]}
        result = settle(pred, queue, [], "2026-11-06T10:00:00Z")
        self.assertEqual(result["settlements"][0]["status"], "pending")

    def test_rejects_post_kickoff_freeze(self):
        queue = {"fixtures": [{"fixture_id": "x", "kickoff_utc": "2026-11-06T09:00:00Z"}]}
        pred = {"predictions": [{"fixture_id": "x", "model_id": "elo", "frozen_at_utc": "2026-11-06T10:00:00Z"}]}
        with self.assertRaises(ValueError):
            settle(pred, queue, [], "2026-11-07T10:00:00Z")
