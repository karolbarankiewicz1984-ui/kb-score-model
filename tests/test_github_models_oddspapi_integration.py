"""Offline exact-identity, data-leakage and odds overlay tests. Zero billable calls."""
import unittest
from copy import deepcopy

from github_models.oddspapi_integration import (
    classify_market, compare_variants, join_fixtures, market_overlay,
)
from github_models.oddspapi_market import normalize_snapshot


def fixture_queue():
    return {"fixtures": [
        {"fixture_id":"m_3NvoM5","league":"LaLiga2","home":"Albacete",
         "away":"Celta Fortuna","country_code":"ESP",
         "kickoff_utc":"2026-11-16T19:30:00Z",
         "snapshot_utc":"2026-11-15T20:22:05Z","identity_blockers":[]}
    ]}


def odds_fixtures():
    return [{"fixtureId":"idODDS1","sportId":10,"tournamentId":123,
             "tournamentName":"LaLiga 2","categorySlug":"spain",
             "participant1Name":"Albacete Balompie",
             "participant2Name":"RC Celta Fortuna","statusId":0,
             "startTime":"2026-11-16T19:30:00Z"}]


class MarketIdentityTests(unittest.TestCase):
    def test_exclusive_market_classification(self):
        fields={"period":"fulltime","handicap":2.5,"player_prop":False,"player_id":"0"}
        expected={
            "Over Under Full Time":"goals",
            "Corners - Over Under Full Time":"corners",
            "Bookings - Over Under Full Time":"cards_bookings",
            "Total Fouls - Over Under Full Time":"fouls_match",
            "Over Under Player Fouls Committed (incl. overtime)":"player_prop",
            "Over Under Player Shots On Goal (incl. overtime)":"player_prop",
            "Corners - Handicap":"corners_other",
        }
        for market_name,family in expected.items():
            with self.subTest(market_name=market_name):
                got=classify_market({**fields,"market_name":market_name})
                self.assertEqual(got["family"],family)
        self.assertFalse(classify_market({**fields,"market_name":"Bookings - Over Under Full Time"})["settlement_compatible"])

    def test_prevent_wrong_period_and_wrong_line(self):
        fields={"market_name":"Over Under Full Time","period":"firsthalf",
                "handicap":2.5,"player_prop":False}
        self.assertIsNone(classify_market(fields)["model_market"])
        self.assertIsNone(classify_market({**fields,"period":"fulltime","handicap":None})["model_market"])

    def test_positive_match(self):
        r=join_fixtures(fixture_queue(),odds_fixtures(),as_of_utc="2026-11-15T22:00:00Z")
        self.assertEqual(r["match_count"],1)
        self.assertEqual(r["links"][0]["odds_fixture_id"],"idODDS1")

    def test_reject_ambiguity_wrong_league_country_and_reverse(self):
        for changed in (
            {**odds_fixtures()[0],"tournamentName":"LaLiga"},
            {**odds_fixtures()[0],"categorySlug":"france"},
            {**odds_fixtures()[0],"participant1Name":"RC Celta Fortuna","participant2Name":"Albacete Balompie"},
        ):
            out=join_fixtures(fixture_queue(),[changed],as_of_utc="2026-11-15T22:00:00Z")
            self.assertEqual(out["match_count"],0)
        double=join_fixtures(fixture_queue(), odds_fixtures()*2, as_of_utc="2026-11-15T22:00:00Z")
        self.assertEqual(double["links"][0]["status"],"ambiguous")

    def test_reject_future_or_blocked_pitch(self):
        p=fixture_queue()
        p["fixtures"][0]["snapshot_utc"]="2026-11-17T00:00:00Z"
        self.assertEqual(join_fixtures(p,odds_fixtures(),as_of_utc="2026-11-15T22:00:00Z")["match_count"],0)
        p=fixture_queue()
        p["fixtures"][0]["identity_blockers"]=["missing_country"]
        self.assertEqual(join_fixtures(p,odds_fixtures(),as_of_utc="2026-11-15T22:00:00Z")["match_count"],0)

    def test_exact_market_overlay_and_no_books(self):
        links=join_fixtures(fixture_queue(),odds_fixtures(),as_of_utc="2026-11-15T22:00:00Z")
        catalog=[{"marketId":106,"marketName":"Over Under Full Time",
                  "marketType":"totals","period":"fulltime","handicap":2.5,
                  "marketLength":2,"playerProp":False,
                  "outcomes":[{"outcomeId":106,"outcomeName":"Over"},
                              {"outcomeId":107,"outcomeName":"Under"}]}]
        def odd(price):
            return {"players":{"0":{"active":True,"price":price,"mainLine":True,
                                    "changedAt":"2026-11-15T21:30:00Z"}}}
        payload={"fixtureId":"idODDS1","startTime":"2026-11-16T19:30:00Z",
                 "statusId":0,"bookmakerOdds":{
                     "superbet.pl":{"bookmakerIsActive":True,"suspended":False,
                                    "markets":{"106":{"marketActive":True,
                                                       "outcomes":{"106":odd(1.5),
                                                                   "107":odd(2.8)}}}}}}
        snapshot=normalize_snapshot(payload,catalog,captured_at_utc="2026-11-15T22:00:00Z")
        markets={"markets":[
            {"fixture_id":"m_3NvoM5","market":"goals","line":2.5,"selection":"over",
             "probability":0.8,"frozen_at_utc":"2026-11-15T20:25:13Z",
             "probability_status":"uncalibrated_research"},
            {"fixture_id":"m_3NvoM5","market":"fouls","line":19.5,"selection":"over",
             "probability":0.9,"frozen_at_utc":"2026-11-15T20:25:13Z"},
        ]}
        report=market_overlay(links,[snapshot],markets,as_of_utc="2026-11-15T22:10:00Z")
        self.assertEqual(len(report["comparisons"]),1)
        row=report["comparisons"][0]
        self.assertEqual(row["bookmaker"],"superbet.pl")
        self.assertEqual(row["market"],"goals")
        self.assertAlmostEqual(row["market_no_vig_probability"],
                               (1/1.5)/(1/1.5+1/2.8),places=6)
        self.assertEqual(report["counters"]["no_exact_market_offer"],1)
        payload["bookmakerOdds"]["not-allowed-pl"] = deepcopy(payload["bookmakerOdds"]["superbet.pl"])
        extra=normalize_snapshot(payload,catalog,captured_at_utc="2026-11-15T22:00:00Z")
        with self.assertRaisesRegex(ValueError,"non_polish"):
            market_overlay(links,[extra],markets,as_of_utc="2026-11-15T22:10:00Z")
        with self.assertRaisesRegex(ValueError,"odds_from_future"):
            market_overlay(links,[snapshot],markets,as_of_utc="2026-11-15T21:59:00Z")

    def test_variant_audit_is_no_data_no_claim(self):
        report=compare_variants({"comparisons":[]},{"settlements":[]})
        self.assertEqual(report["metrics"],[])
        self.assertEqual(report["conclusion"],"insufficient_evidence")
        row={"fixture_id":"f1","market":"goals","line":2.5,"selection":"over",
             "eligible_min_odds_1_20":True,"settlement_verified":True,
             "p_model":0.75,"market_no_vig_probability":0.70,"price":1.8}
        out=compare_variants({"comparisons":[row]}, {"settlements":[
            {"fixture_id":"f1","market":"goals","line":2.5,"selection":"over",
             "status":"settled","hit":True}]})
        self.assertEqual({m["variant"] for m in out["metrics"]},
                         {"frozen_model","market_filter_only","shadow_50_50_blend"})
        self.assertEqual(out["conclusion"],"retrospective_descriptive_only")


if __name__=="__main__":
    unittest.main()
