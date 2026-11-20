"""Regression tests: market/period/side/line identity must not be guessed."""
import unittest
from github_models.market_rule_gate import (
    classify_quote, audit, settle_half_goal_handicap,
)

TIME = "2026-11-20T10:00:00Z"
KICK = "2026-11-20T20:00:00Z"


def quote(name, kind, period="fulltime", outcome="Over", line=1.5, **kw):
    return {"bookmaker": "superbet.pl", "market_name": name,
            "market_type": kind, "period": period, "handicap": line,
            "outcome_name": outcome, "player_id": "0", "player_prop": False,
            "odds": 1.6, "market_id": "test123", **kw}


class MarketRuleGateTests(unittest.TestCase):
    def test_player_fouls_cannot_price_match_fouls(self):
        q = quote("Over Under Player Fouls Committed (incl. overtime)",
                  "playertotals-foulscommitted", period="result")
        q.update(player_prop=True, player_id="1859482")
        got = classify_quote(q)
        self.assertEqual(got["reason"], "player_scope_not_match_total")
        self.assertEqual(got["family"], "player_fouls")
        self.assertFalse(got["comparison_allowed"])

    def test_match_fouls_remain_blocked_without_stat_source(self):
        q = quote("Total Fouls Over Under Full Time", "totals-fouls", line=19.5)
        got = classify_quote(q)
        self.assertEqual(got["reason"], "independent_foul_stat_source_unverified")
        self.assertFalse(got["settlement_allowed"])
        self.assertFalse(got["comparison_allowed"])

    def test_bookings_not_silent_yellow_card_equivalence(self):
        q = quote("Bookings - Over Under Full Time", "totals-bookings",
                  line=4.5, outcome="Under")
        got = classify_quote(q)
        self.assertEqual(got["family"], "bookings_or_cards")
        self.assertEqual(got["reason"], "booking_vs_yellow_card_units_unverified")
        self.assertFalse(got["comparison_allowed"])

    def test_half_and_team_bookings_are_not_fulltime_cards(self):
        for name, period in [
            ("Bookings - Over Under Team 2 First Half", "p1"),
            ("Bookings - Over Under Team 1", "fulltime")
        ]:
            got = classify_quote(quote(name, "teamtotals-bookings-team2", period))
            self.assertFalse(got["comparison_allowed"])

    def test_asian_line_sign_and_side_need_source_evidence(self):
        for outcome, line in [("1", -1.5), ("2", 1.5), ("1", 0.5), ("2", -0.5)]:
            q = quote("Asian Handicap", "spreads", outcome=outcome, line=line)
            got = classify_quote(q)
            self.assertEqual(got["family"], "asian_handicap")
            self.assertEqual(got["reason"], "provider_line_sign_and_side_unverified")
            self.assertFalse(got["comparison_allowed"])

    def test_european_handicap_not_equivalent(self):
        q = quote("European Handicap", "spreads-european", outcome="X", line=2)
        got = classify_quote(q)
        self.assertEqual(got["reason"], "three_way_not_asian_handicap")
        self.assertFalse(got["comparison_allowed"])

    def test_allowed_existing_markets_still_only_comparisons(self):
        for name, kind, selection, line in [
            ("Over Under Full Time", "totals", "Over", 2.5),
            ("Corners - Over Under Full Time", "totals-corners", "Under", 8.5),
            ("Both Teams To Score", "binary", "Yes", 0),
        ]:
            got = classify_quote(quote(name, kind, outcome=selection, line=line))
            self.assertTrue(got["comparison_allowed"])
            self.assertFalse(got["settlement_allowed"])

    def test_low_odds_and_wrong_period_blocked(self):
        q = quote("Over Under Full Time", "totals", "p1", line=2.5)
        self.assertFalse(classify_quote(q)["comparison_allowed"])
        q = quote("Over Under Full Time", "totals", line=2.5)
        q["odds"] = 1.19
        self.assertFalse(classify_quote(q)["comparison_allowed"])

    def test_half_goal_math_home_away(self):
        self.assertTrue(settle_half_goal_handicap(2, 1, team="away", line=1.5))
        self.assertFalse(settle_half_goal_handicap(2, 0, team="away", line=1.5))
        self.assertTrue(settle_half_goal_handicap(0, 1, team="away", line=1.5))
        self.assertTrue(settle_half_goal_handicap(1, 0, team="home", line=-0.5))
        self.assertFalse(settle_half_goal_handicap(1, 0, team="home", line=-1.5))
        for bad in (0, -1, 0.25, 0.75, "1.5", 4.5):
            with self.assertRaises(ValueError):
                settle_half_goal_handicap(1, 1, team="away", line=bad)

    def test_audit_only_superbet_exact_snapshots(self):
        s = {"provider": "oddspapi-v4", "kickoff_utc": KICK,
             "captured_at_utc": TIME, "quotes": [
                 quote("Asian Handicap", "spreads"),
                 quote("Bookings - Over Under Full Time", "totals-bookings"),
                 quote("Over Under Full Time", "totals", line=2.5),
             ]}
        c = {"bookmakers": ["superbet.pl"], "as_of_utc": TIME, "snapshots": [s]}
        data = audit(c)
        self.assertEqual(data["quotes_checked"], 3)
        self.assertEqual(data["family_counts"]["asian_handicap"], 1)
        self.assertEqual(data["family_counts"]["bookings_or_cards"], 1)
        self.assertEqual(data["automatically_promoted_markets"], [])
        self.assertEqual(data["new_paid_api_calls"], 0)
        self.assertFalse(data["quality_score_67_100_mandatory"])
        with self.assertRaises(ValueError):
            audit({**c, "bookmakers": ["sts.pl"]})

    def test_late_quote_not_counted(self):
        q = quote("Over Under Full Time", "totals", line=2.5)
        q["changed_at_utc"] = "2026-11-20T20:01:00Z"
        c = {"bookmakers": ["superbet.pl"], "snapshots": [
            {"provider": "oddspapi-v4", "kickoff_utc": KICK,
             "captured_at_utc": TIME, "quotes": [q]}]}
        z = audit(c)
        self.assertEqual(z["quotes_checked"], 0)
        self.assertEqual(z["reason_counts"]["provider_quote_after_kickoff"], 1)


if __name__ == "__main__":
    unittest.main()
