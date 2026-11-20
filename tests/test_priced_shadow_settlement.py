"""No speculation about fouls/cards, European handicap, or model calibration."""
import copy
import sys
import types
import unittest
from unittest.mock import patch

from github_models.priced_shadow_settlement import (
    quote_identity, quote_pairs, settle_quotes, summarize, review_archive,
)

FROZEN = "2026-11-20T08:42:09+00:00"
CAPTURE = "2026-11-20T09:14:03+00:00"
START = "2026-11-20T20:00:00Z"
CHANGED = "2026-11-20T09:00:46Z"


def fixture():
    return {"fixture_id": "m_1", "home": "A", "away": "B", "league": "L",
            "kickoff_utc": START}


def model(market, selection, line, p=.78):
    return {"fixture_id": "m_1", "market": market,
            "selection": selection, "line": line,
            "probability": p, "frozen_at_utc": FROZEN,
            "resolved_identity": {"league": "L", "home": "A", "away": "B"}}


def quote(market, kind, side, line, price, market_id):
    return {"bookmaker": "superbet.pl", "market_name": market,
            "market_type": kind, "period": "fulltime", "outcome_name": side,
            "handicap": line, "odds": price, "player_prop": False,
            "player_id": "0", "market_id": market_id,
            "outcome_id": market_id+side, "changed_at_utc": CHANGED}


def sample():
    quotes = [
        quote("Both Teams To Score", "bothteamsscore", "Yes", 0., 1.63, "104"),
        quote("Both Teams To Score", "bothteamsscore", "No", 0., 2.25, "104"),
        quote("Asian Handicap", "spreads", "1", -1.5, 3.5, "1060"),
        quote("Asian Handicap", "spreads", "2", -1.5, 1.27, "1060"),
        quote("Asian Handicap", "spreads", "1", 1.5, 1.1, "1084"),
        quote("Asian Handicap", "spreads", "2", 1.5, 6.5, "1084"),
        quote("European Handicap", "spreads-european", "1", -1.5, 2., "eu1"),
        quote("Bookings - Over Under Full Time", "totals-bookings", "Over",
              4.5, 2., "book"),
        quote("Fouls - Player 1", "playertotals-fouls", "Over", 1.5, 2., "player"),
    ]
    queue = {"schema": "github-models-fixture-queue-v1",
             "generated_at_utc": FROZEN, "fixtures": [fixture()]}
    frozen = {"schema": "multimodel-v2-shadow-markets-v1",
              "generated_at_utc": FROZEN,
              "candidates": [model("btts", "yes", None),
                             model("btts", "no", None),
                             model("handicap", "home", -1.5),
                             model("handicap", "away", 1.5),
                             model("handicap", "home", 1.5),
                             model("handicap", "away", -1.5)]}
    collection = {"provider": "oddspapi-v4", "bookmakers": ["superbet.pl"],
                  "links": {"links": [{"status": "matched", "fixture_id": "m_1",
                                      "odds_fixture_id": "of1"}]},
                  "snapshots": [{"provider": "oddspapi-v4", "pitch_fixture_id": "m_1",
                                 "fixture_id": "of1", "kickoff_utc": START,
                                 "captured_at_utc": CAPTURE, "quotes": quotes}]}
    return collection, queue, frozen


class Pricings(unittest.TestCase):
    def test_away_plus_1_5_from_home_minus_1_5(self):
        c, q, f = sample()
        rows, excluded = quote_pairs(c, q, f)
        found = {(r["market"], r["selection"], r["line"]): r for r in rows}
        self.assertEqual(len(rows), 5)
        self.assertIn(("handicap", "away", 1.5), found)
        self.assertEqual(found[("handicap", "away", 1.5)]["price"], 1.27)
        self.assertEqual(found[("handicap", "away", 1.5)]["source_market_id"], "1060")
        self.assertIn(("handicap", "away", -1.5), found)
        self.assertEqual(found[("handicap", "away", -1.5)]["price"], 6.5)
        self.assertNotIn(("handicap", "home", 1.5), found)
        self.assertEqual(excluded["odds_below_1_20_or_invalid"], 1)

    def test_correct_btts_not_booking_or_fouls(self):
        c,q,f=sample()
        rows,_=quote_pairs(c,q,f)
        self.assertEqual({r["market"] for r in rows},{"btts","handicap"})
        self.assertFalse(any(r["official_bookmaker_settlement_verified"] for r in rows))

    def test_only_exact_markets_can_be_priced(self):
        c,q,f=sample()
        for qq in c["snapshots"][0]["quotes"]:
            if "European" in qq["market_name"] or "Bookings" in qq["market_name"] \
                    or "Foul" in qq["market_name"]:
                self.assertIsNone(quote_identity(qq))

    def test_reject_wrong_time_and_untrusted_fixture_link(self):
        c,q,f=sample()
        c["snapshots"][0]["captured_at_utc"]="2026-11-20T21:00:00Z"
        with self.assertRaises(ValueError):
            quote_pairs(c,q,f)
        c,q,f=sample()
        c["links"]["links"][0]["odds_fixture_id"]="wrong"
        with self.assertRaises(ValueError):
            quote_pairs(c,q,f)

    def test_not_scoped_to_player_first_half_or_unknown_book(self):
        c,q,f=sample()
        c["snapshots"][0]["quotes"][2]["period"]="p1"
        c["snapshots"][0]["quotes"][2]["player_prop"]=True
        rows,_=quote_pairs(c,q,f)
        self.assertFalse(any(r["market"]=="handicap" and r["selection"]=="home"
                             and r["line"]==-1.5 for r in rows))
        c,q,f=sample()
        c["snapshots"][0]["quotes"][2]["bookmaker"]="sts.pl"
        with self.assertRaises(ValueError):
            # A foreign quote inside a Superbet-only archive is a fatal error,
            # not a silently ignored market that might be repriced.
            quote_pairs(c,q,f)  # tightened gate in implementation

    def test_disallow_missing_provider_timestamp_and_unpaired_market(self):
        c,q,f=sample()
        c["snapshots"][0]["quotes"][3]["changed_at_utc"]=None
        rows,_=quote_pairs(c,q,f)
        self.assertFalse(any(r["market"]=="handicap" and r["selection"]=="away"
                             and r["line"]==1.5 for r in rows))
        c,q,f=sample()
        c["snapshots"][0]["quotes"]=[
            z for z in c["snapshots"][0]["quotes"] if not (
                z["market_id"]=="104" and z["outcome_name"]=="No")]
        rows,_=quote_pairs(c,q,f)
        self.assertFalse(any(r["market"]=="btts" for r in rows))

    def test_fail_closed_when_model_or_queue_changes(self):
        c,q,f=sample()
        f["generated_at_utc"]="2026-11-20T08:42:08Z"
        with self.assertRaises(ValueError):
            quote_pairs(c,q,f)
        c,q,f=sample()
        f["candidates"][0]["probability"]=1.8
        with self.assertRaises(ValueError):
            quote_pairs(c,q,f)

    def test_settlement_uses_resolved_final_and_retains_pending(self):
        c,q,f=sample()
        priced,_=quote_pairs(c,q,f)
        def settle_one(_,queue,pool,at):
            return [{**{"fixture_id":r["fixture_id"], "market":r["market"],
                       "selection":r["selection"], "line":r["line"]},
                     **({"status":"settled","hit":True,
                         "actual_goals":[2,1], "source_fixture_id":"verified-1"}
                        if r["market"]=="handicap"
                        else {"status":"pending"})} for r in priced]
        package_shadow = types.ModuleType("github_models.shadow_audit")
        package_shadow.settle_one = settle_one
        package_settlement = types.ModuleType("github_models.settlement")
        package_settlement.CachedHistoricalPool = lambda items: items
        with patch.dict(sys.modules,{"github_models.shadow_audit":package_shadow,
                                     "github_models.settlement":package_settlement}):
            settled=settle_quotes(priced,q,f,[],as_of_utc=CAPTURE)
        self.assertEqual(sum(r["status"]=="settled" for r in settled),3)
        self.assertEqual(sum(r["status"]=="pending" for r in settled),2)
        self.assertTrue(all("simulated_unit_return_before_fees" in r for r in settled))
        z=summarize(settled)
        self.assertFalse(z["official_bookmaker_payout_confirmed"])
        self.assertFalse(z["production_promotion"])
        self.assertEqual(z["market_summary"]["btts"]["brier"],None)


if __name__ == "__main__":
    unittest.main()
