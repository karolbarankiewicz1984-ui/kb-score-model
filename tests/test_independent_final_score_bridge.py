"""Verified final score bridge is frozen-identity, time, provenance gated."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from github_models.independent_final_score_bridge import reconcile
from github_models.multimodel_calibration_gate import report

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"data/github_models/independent_final_evidence_2026-11-20.json"
AS_OF="2026-11-23T09:00:00Z"

class IndependentScores(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name)
        (self.d/"queues"/"2026-11-20").mkdir(parents=True)
        self.e=json.loads(EVIDENCE.read_text(encoding="utf-8"))
        fixtures=[{k:row[k] for k in
                   ("fixture_id","league","league_id","country_code","home",
                    "away","kickoff_utc","home_team_id","away_team_id")}
                  for row in self.e["rows"]]
        (self.d/"queues"/"2026-11-20"/"queue.json").write_text(
            json.dumps({"fixtures":fixtures}),encoding="utf-8")

    def reconcile(self, history=None, cutoff=AS_OF):
        return reconcile(history if history is not None else [],self.e,
                         self.d,observed_at_utc=cutoff)

    def test_four_exact_scores_and_as_of_provenance(self):
        rows,info=self.reconcile()
        self.assertEqual(len(rows),4)
        self.assertEqual(info["new_finished_rows"],4)
        self.assertTrue(info["not_backdated"])
        self.assertEqual({r["frozen_pitch_fixture_id"] for r in rows},
                         {e["fixture_id"] for e in self.e["rows"]})
        self.assertTrue(all(r["published_at_utc"]=="2026-11-23T09:00:00+00:00"
                            and r["actual_bookmaker_payout_verified"] is False for r in rows))
        self.assertEqual({(r["home_goals"],r["away_goals"]) for r in rows},
                         {(2,1),(1,3),(0,2),(1,2)})

    def test_idempotent_and_source_conflict_is_fatal(self):
        rows,_=self.reconcile()
        second,info=self.reconcile(rows)
        self.assertEqual(rows,second)
        self.assertEqual(info["new_finished_rows"],0)
        bad=copy.deepcopy(rows)
        bad[0]["home_goals"]=9
        with self.assertRaisesRegex(ValueError,"independent_sources_disagree_final"):
            self.reconcile(bad)

    def test_no_premature_or_backdated_completion(self):
        with self.assertRaises(ValueError):
            self.reconcile(cutoff="2026-11-21T08:00:00Z")
        with self.assertRaises(ValueError):
            self.reconcile(cutoff="2026-11-23T09:00:00")

    def test_mutated_frozen_team_id_is_blocked(self):
        self.e["rows"][0]["home_team_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"frozen_identity_mismatch"):
            self.reconcile()

    def test_duplicate_or_incomplete_documentation_is_blocked(self):
        self.e["rows"][0]["sources"]=["https://redstar.fr/a","https://redstar.fr/b"]
        with self.assertRaisesRegex(ValueError,"not_two_distinct"):
            self.reconcile()

    def test_duplicate_frozen_fixture_conflict_is_blocked(self):
        f=copy.deepcopy(self.e["rows"][0])
        f["home"]="Not the frozen team"
        (self.d/"queues"/"2026-11-20"/"other.json").write_text(
            json.dumps({"fixtures":[f]}),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"conflicting_frozen_fixture"):
            self.reconcile()

class ModelCalibration(unittest.TestCase):
    def test_never_promote_on_four_matches_even_if_bets_many(self):
        rows=[]
        for i in range(500):
            rows.append(dict(fixture_id="same_game",market="btts",bookmaker="superbet.pl",
                             status="settled",official_bookmaker_settlement_verified=False,
                             p_model=.8,hit=True,price=1.25))
        replay={"schema":"github-models-oddspapi-frozen-audit-v1",
                "as_of_utc":AS_OF,"unique_settled_fixtures":4,
                "settled_selection_quotes":32,
                "status_counts":{"unresolved":100},
                "unresolved_reasons":{"no_exact_verified_outcome":50,
                                      "market_settlement_not_verified":50}}
        shadow={"schema":"multimodel-priced-shadow-outcomes-v1",
                "as_of_utc":AS_OF,"entries":rows,"status":{"settled":500}}
        result=report(replay,shadow)
        self.assertEqual(result["conservative_max_distinct_fixtures"],4)
        self.assertFalse(result["diagnostic_threshold_met"])
        self.assertFalse(result["calibration_authorized"])
        self.assertFalse(result["model_weights_changed"])
        self.assertEqual(result["market_summaries"]["btts"]["distinct_settled_fixtures"],1)
        self.assertEqual(result["abc_unsettled_market_rules_not_yet_verified"],50)

    def test_even_one_hundred_qualifies_only_for_review_not_weight_promotion(self):
        r={"schema":"github-models-oddspapi-frozen-audit-v1",
           "as_of_utc":AS_OF,"unique_settled_fixtures":100}
        s={"schema":"multimodel-priced-shadow-outcomes-v1",
           "as_of_utc":AS_OF,"entries":[]}
        v=report(r,s)
        self.assertTrue(v["minimum_100_distinct_match_review"])
        self.assertFalse(v["calibration_authorized"])
        self.assertFalse(v["holdout_evidence_available"])

if __name__=="__main__":
    unittest.main()
