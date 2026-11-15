"""Offline regression tests; these do not call OddsPapi or consume API quota."""
import unittest

from github_models.oddspapi_market import (
    normalize_snapshot, normalize_history, subscription_budget,
)

CATALOG = [
    {"marketId": 101, "marketName": "Full Time Result", "marketLength": 3,
     "marketType": "1x2", "period": "fulltime", "handicap": 0, "playerProp": False,
     "outcomes": [{"outcomeId": 101, "outcomeName": "1"},
                  {"outcomeId": 102, "outcomeName": "X"},
                  {"outcomeId": 103, "outcomeName": "2"}]},
    {"marketId": 106, "marketName": "Over Under Full Time", "marketLength": 2,
     "marketType": "totals", "period": "fulltime", "handicap": 2.5,
     "outcomes": [{"outcomeId": 106, "outcomeName": "Over"},
                  {"outcomeId": 107, "outcomeName": "Under"}]},
]


def selection(price, changed="2026-11-15T11:59:00Z", active=True):
    return {"players": {"0": {"active": active, "price": price,
                               "changedAt": changed, "mainLine": True}}}


def payload():
    return {"fixtureId": "id123", "startTime": "2026-11-15T18:00:00Z",
            "statusId": 0, "participant1Name": "Alpha",
            "participant2Name": "Beta", "tournamentId": 17,
            "bookmakerOdds": {
                "book-a": {"bookmakerIsActive": True, "suspended": False,
                           "markets": {
                               "101": {"marketActive": True,
                                       "outcomes": {"101": selection(2.0),
                                                    "102": selection(3.0),
                                                    "103": selection(4.0)}},
                               "106": {"marketActive": True,
                                       "outcomes": {"106": selection(1.10),
                                                    "107": selection(7.2)}}}},
                "book-b": {"bookmakerIsActive": True, "suspended": False,
                           "markets": {"101": {"marketActive": True,
                                                "outcomes": {"101": selection(1.9),
                                                             "102": selection(3.1)}}}},
                "book-c": {"bookmakerIsActive": True, "suspended": True,
                           "markets": {"101": {"marketActive": True,
                                                "outcomes": {"101": selection(1.3)}}}}
            }}


class OddsPapiMarketTest(unittest.TestCase):
    def test_all_offered_markets_and_only_complete_no_vig(self):
        r = normalize_snapshot(payload(), CATALOG, captured_at_utc="2026-11-15T12:00:00Z")
        self.assertEqual(len(r["quotes"]), 7)
        a1 = next(x for x in r["quotes"] if x["bookmaker"] == "book-a" and x["outcome_id"] == "101")
        self.assertAlmostEqual(a1["no_vig_probability"], 0.46153846, places=7)
        b1 = next(x for x in r["quotes"] if x["bookmaker"] == "book-b" and x["outcome_id"] == "101")
        self.assertIsNone(b1["no_vig_probability"])
        self.assertIsNone(next(x for x in r["market_summary"] if x["market_id"] == "101")["consensus_no_vig_probability"])
        low = next(x for x in r["quotes"] if x["market_id"] == "106" and x["outcome_id"] == "106")
        self.assertFalse(low["eligible_min_odd"])
        self.assertIsNotNone(low["no_vig_probability"])

    def test_cutoff_or_started_fixture_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly_prematch"):
            normalize_snapshot(payload(), CATALOG, captured_at_utc="2026-11-15T18:00:00Z")
        p = payload()
        p["statusId"] = 1
        with self.assertRaisesRegex(ValueError, "strictly_prematch"):
            normalize_snapshot(p, CATALOG, captured_at_utc="2026-11-15T12:00:00Z")

    def test_future_quote_is_excluded(self):
        p = payload()
        p["bookmakerOdds"]["book-a"]["markets"]["101"]["outcomes"]["101"] = selection(
            2.0, "2026-11-15T13:00:00Z")
        r = normalize_snapshot(p, CATALOG, captured_at_utc="2026-11-15T12:00:00Z")
        self.assertFalse(any(x["bookmaker"] == "book-a" and x["outcome_id"] == "101"
                             for x in r["quotes"]))
        self.assertTrue(all(x["no_vig_probability"] is None for x in r["quotes"]
                            if x["market_id"] == "101"))

    def test_quota_reserve_guard(self):
        a = {"current_subscription_id": "a", "subscriptions": [
            {"subscription_id": "a", "is_active": True, "request_limit": 250,
             "request_count": 240, "bookmakers": {"pinnacle": {}}}]}
        with self.assertRaisesRegex(RuntimeError, "reserve_guard"):
            subscription_budget(a, requested=1)
        self.assertEqual(subscription_budget(a, requested=0)["remaining_before_reserve"], 0)

    def test_history_enforces_strict_prekickoff(self):
        history = {"fixtureId": "id123", "bookmakers": {
            "pinnacle": {"markets": {"106": {"outcomes": {
                "106": {"players": {"0": [
                    {"createdAt": "2026-11-15T17:59:00Z", "price": 1.4, "active": True},
                    {"createdAt": "2026-11-15T18:00:00Z", "price": 1.3, "active": True},
                    {"createdAt": "2026-11-15T18:10:00Z", "price": 1.2, "active": True}
                ]}}}}}}}}
        r = normalize_history(history, kickoff_utc="2026-11-15T18:00:00Z")
        self.assertEqual(len(r["history"]), 1)
        self.assertEqual(r["history"][0]["odds"], 1.4)


if __name__ == "__main__":
    unittest.main()
