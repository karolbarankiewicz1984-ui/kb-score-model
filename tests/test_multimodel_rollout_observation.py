"""Rollout checks are read-only and never manufacture bookmaker odds."""
import unittest
from collections import Counter
from github_models.unified_output import key,leader_shortlist,rollout_manifest,market_label

def row(fid,market,p,odds=None,selection="over",line=None):
    return dict(fixture_id=fid,market=market,probability=p,odds=odds,
                selection=selection,line=line)

class MarketRollout(unittest.TestCase):
    def test_categorical_1x2_line_zero_matches_no_line(self):
        self.assertEqual(key(row("m","1X2",.81,selection="1",line=0)),
                         key(row("m","1X2",.81,selection="1",line=None)))
        self.assertEqual(key(row("m","double_chance",.88,selection="1X",line=0)),
                         key(row("m","double_chance",.88,selection="1X",line=None)))
        with self.assertRaises(ValueError):
            key(row("m","1X2",.8,selection="1",line=2.5))
        self.assertNotEqual(key(row("m","goals",.8,line=1.5)),
                            key(row("m","goals",.8,line=2.5)))

    def test_diverse_and_one_family_for_outcome_and_dc(self):
        a=[
            row("m","double_chance",.94,selection="1X"),
            row("m","1X2",.88,odds=1.33,selection="1"),
            row("m","goals",.76,odds=1.28,line=1.5),
            row("m","goals",.83,line=2.5),
            row("m","corners",.71,line=6.5),
            row("m","btts",.85,selection="yes"),
        ]
        top=leader_shortlist({"m":a})
        self.assertEqual(len(top),3)
        self.assertEqual(set(t["market"] for t in top),{"1X2","goals","btts"})
        self.assertEqual(len(set(t["fixture_id"] for t in top)),1)
        self.assertTrue(top[0]["odds"] is not None)
        self.assertTrue(top[1]["odds"] is not None)

    def test_preview_retains_at_most_three_but_fills_when_one_category(self):
        rows=[row("m","corners",p,line=line) for p,line in [(0.9,7.5),(.85,8.5),(.8,9.5),(.78,10.5)]]
        top=leader_shortlist({"m":rows})
        self.assertEqual(len(top),3)
        self.assertEqual([r["line"] for r in top],[7.5,8.5,9.5])

    def test_market_observation_records_only_actual_rows(self):
        rows=[
            row("a","double_chance",.89,odds=1.23,selection="1X"),
            row("a","goals",.84,line=.5),
            row("b","corners",.80,line=10.5),
        ]
        leaders=leader_shortlist({"a":rows[:2],"b":rows[2:]})
        status=rollout_manifest(rows,leaders,"2026-11-24T07:00:00Z",
                               priced_as_of_utc="2026-11-24T09:00:00Z")
        self.assertEqual(status["rollout_status"],"new_markets_observed")
        self.assertEqual(status["priced_rows"],{"double_chance":1})
        self.assertEqual(status["double_chance_selections"],["1X"])
        self.assertEqual(status["observed_new_lines"],{"goals":[.5],"corners":[10.5]})
        self.assertTrue(status["no_new_bookmaker_queries"])

    def test_frozen_old_archive_not_falsely_reported_as_new(self):
        rows=[row("m","goals",.81,line=1.5),row("m","corners",.77,line=8.5)]
        z=rollout_manifest(rows,rows,"2026-11-22T07:00:00Z",
                           priced_as_of_utc="2026-11-22T09:00:00Z")
        self.assertEqual(z["rollout_status"],"awaiting_fresh_market_output_or_source_coverage")
        self.assertFalse(z["new_market_output_observed"])
        self.assertEqual(z["priced_rows"],{})

if __name__=="__main__":
    unittest.main()
