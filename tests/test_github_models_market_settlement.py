import unittest
from github_models.market_settlement import settle_markets

class EventSettlementTests(unittest.TestCase):
    def test_future_event_remains_pending(self):
        queue = {"fixtures":[{"fixture_id":"1","kickoff_utc":"2026-11-09T18:00:00Z"}]}
        markets = {"markets":[{"fixture_id":"1","market":"fouls","selection":"under",
            "line":22.5,"probability":0.7,"frozen_at_utc":"2026-11-06T10:00:00Z"}]}
        result = settle_markets(markets,queue,[],[],"2026-11-06T11:00:00Z")
        self.assertEqual(result["settlements"][0]["status"],"pending")

    def test_invalid_probability_fails(self):
        queue = {"fixtures":[{"fixture_id":"1","kickoff_utc":"2026-11-09T18:00:00Z"}]}
        markets = {"markets":[{"fixture_id":"1","market":"cards","selection":"over",
            "line":3.5,"probability":1.1,"frozen_at_utc":"2026-11-06T10:00:00Z"}]}
        with self.assertRaises(ValueError):
            settle_markets(markets,queue,[],[],"2026-11-06T11:00:00Z")
