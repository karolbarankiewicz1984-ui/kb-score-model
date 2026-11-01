"""Audit fixtures are synthetic TEST INPUTS, never production observations."""
from copy import deepcopy
import json
import unittest

from tests.test_multimodel_v2_provenance import DAY, SHA, change_market, evidence
from multimodel_v2.audit import build_audits, freeze_reference

AUDIT_TIME = "2026-11-01T23:00:00Z"


def frozen_evidence():
    runs, snapshots = evidence()
    snapshot = snapshots[0]
    snapshot["publication"] = {"id": "original-test-freeze", "provenance": "live_pre_match",
                               "captured_at_utc": "2026-11-01T09:05:00Z"}
    row = snapshot["background_candidates"][0]
    row["frozen_quote"] = deepcopy(row["market_data"]["quotes"][0])
    snapshot["top_positions"] = [deepcopy(row)]
    return runs, snapshots


def make_row(snapshot, fid=123, line=13.5, score=67, odd=1.75, market="fouls"):
    row = deepcopy(snapshot["background_candidates"][0])
    change_market(row, fixture_id=fid, team_id=fid, line=line, market=market)
    row.update(home=f"Test Gospodarze {fid}", away=f"Test Goście {fid}", final_assessment_pct=score)
    row["market_data"]["quotes"][0]["selected_odd"] = odd
    row["frozen_quote"] = deepcopy(row["market_data"]["quotes"][0])
    return row


def settlement(snapshot, row, outcome="win"):
    return {"date": snapshot["date"], "freeze": freeze_reference(snapshot),
            "market_identity": deepcopy(row["market_data"]["quotes"][0]["market_identity"]),
            "fixture_status": "FT", "finished_at": "2026-11-01T22:00:00Z",
            "settled_at": "2026-11-01T22:01:00Z", "outcome": outcome,
            "result_source": "test-only final statistics fixture"}


class IndependentAuditTests(unittest.TestCase):
    def setUp(self):
        self.runs, self.snapshots = frozen_evidence()
        self.snapshot = self.snapshots[0]
        self.row = self.snapshot["background_candidates"][0]
        self.results = [settlement(self.snapshot, self.row)]

    def audit(self, cutoff=AUDIT_TIME):
        return build_audits(DAY, self.runs, self.snapshots, self.results, as_of=cutoff)

    def test_three_cohorts_are_independent_with_no_shared_denominator(self):
        rows = [make_row(self.snapshot, fid=1, score=55),
                make_row(self.snapshot, fid=2, score=75, market="corners"),
                make_row(self.snapshot, fid=3, score=80)]
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = [deepcopy(rows[0])]
        self.results = [settlement(self.snapshot, r) for r in rows]
        cohorts = self.audit()["cohorts"]
        self.assertEqual([cohorts[n]["metrics"]["positions"] for n in
                          ("original_top", "qualifying_api", "fouls_under")], [1, 2, 2])
        self.assertEqual(cohorts["original_top"]["rows"][0]["original_position"]["final_assessment_pct"], 55)

    def test_original_top_membership_and_order_are_never_reranked(self):
        rows = [make_row(self.snapshot, fid=1, score=70), make_row(self.snapshot, fid=2, score=99)]
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = deepcopy(rows)
        self.results = [settlement(self.snapshot, r, outcome="loss") for r in rows]
        top = self.audit()["cohorts"]["original_top"]["rows"]
        self.assertEqual([r["market_identity"]["fixture_id"] for r in top], ["1", "2"])
        self.assertEqual([r["original_position"] for r in top], rows)

    def test_missing_top_does_not_become_reconstructed_top(self):
        del self.snapshot["top_positions"]
        out = self.audit()["cohorts"]
        self.assertEqual(out["original_top"]["status"], "source_missing")
        self.assertIsNone(out["original_top"]["metrics"]["positions"])
        self.assertEqual(out["qualifying_api"]["metrics"]["positions"], 1)

    def test_explicitly_empty_original_top_is_different_from_missing_source(self):
        self.snapshot["top_positions"] = []
        top = self.audit()["cohorts"]["original_top"]
        self.assertEqual(top["status"], "complete")
        self.assertEqual(top["metrics"]["positions"], 0)
        self.assertIsNone(top["metrics"]["roi_pct"])

    def test_without_original_publication_no_historical_settlement(self):
        del self.snapshot["publication"]
        for cohort in self.audit()["cohorts"].values():
            self.assertEqual(cohort["status"], "source_missing")
            self.assertIsNone(cohort["metrics"]["roi_pct"])

    def test_freeze_at_kickoff_is_not_prematch(self):
        self.row["kickoff"] = "2026-11-01T09:05:00Z"
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        for cohort in self.audit()["cohorts"].values():
            self.assertIsNone(cohort["metrics"]["roi_pct"])
        self.assertEqual(self.audit()["cohorts"]["original_top"]["metrics"]["settled"], 0)

    def test_publication_cannot_follow_run_or_observation_cutoff(self):
        self.snapshot["publication"]["captured_at_utc"] = "2026-11-01T10:00:00Z"
        self.assertIsNone(self.audit()["freeze"])

    def test_earliest_original_freeze_is_not_replaced_by_profitable_rerun(self):
        later = deepcopy(self.snapshot)
        later["publication"].update(id="later-test-freeze", captured_at_utc="2026-11-01T09:10:00Z")
        later["background_candidates"][0]["final_assessment_pct"] = 99
        self.snapshots.insert(0, later)
        self.assertEqual(self.audit()["freeze"]["id"], "original-test-freeze")

    def test_conflicting_copies_of_original_freeze_block_audit(self):
        other = deepcopy(self.snapshot)
        other["top_positions"] = []
        self.snapshots.append(other)
        self.assertIsNone(self.audit()["freeze"])

    def test_missing_price_keeps_original_top_row_but_suppresses_financial_metrics(self):
        self.row["market_data"]["quotes"] = []
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        top = self.audit()["cohorts"]["original_top"]
        self.assertEqual(len(top["rows"]), 1)
        self.assertEqual(top["status"], "incomplete")
        self.assertIsNone(top["metrics"]["roi_pct"])

    def test_no_retrospective_best_price_substitution(self):
        del self.row["frozen_quote"]
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        for cohort in self.audit()["cohorts"].values():
            self.assertEqual(cohort["metrics"]["settled"], 1)
            self.assertIsNone(cohort["metrics"]["roi_pct"])

    def test_frozen_price_must_match_exact_bookmaker_timestamp_and_market(self):
        for field, value in (("bookmaker", "NotTheRecordedBook"), ("selected_odd", 9.0),
                             ("provider_updated_at", "2026-11-01T08:58:00Z")):
            with self.subTest(field=field):
                runs, snapshots = frozen_evidence()
                row = snapshots[0]["background_candidates"][0]
                row["frozen_quote"][field] = value
                snapshots[0]["top_positions"] = [deepcopy(row)]
                result = build_audits(DAY, runs, snapshots, [settlement(snapshots[0], row)], as_of=AUDIT_TIME)
                self.assertIsNone(result["cohorts"]["qualifying_api"]["metrics"]["roi_pct"])

    def test_all_results_required_roi_not_computed_on_survivor_subset(self):
        other = make_row(self.snapshot, fid=124)
        self.snapshot["background_candidates"].append(other)
        self.snapshot["top_positions"].append(deepcopy(other))
        metrics = self.audit()["cohorts"]["original_top"]["metrics"]
        self.assertEqual((metrics["settled"], metrics["unresolved"], metrics["losses"]), (1, 1, 0))
        self.assertIsNone(metrics["roi_pct"])
        self.assertIsNone(metrics["fixture_equal_roi_pct"])
        self.assertIsNone(metrics["hit_rate_pct"])

    def test_roi_and_fixture_equal_roi_use_distinct_fixture_weights(self):
        rows = [make_row(self.snapshot, fid=1, line=3.5, odd=1.20, market="corners"),
                make_row(self.snapshot, fid=1, line=4.5, odd=1.20, market="corners"),
                make_row(self.snapshot, fid=2, odd=2.00)]
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = deepcopy(rows)
        self.results = [settlement(self.snapshot, r, "win" if i < 2 else "loss") for i, r in enumerate(rows)]
        metrics = self.audit()["cohorts"]["qualifying_api"]["metrics"]
        self.assertEqual((metrics["positions"], metrics["fixtures"]), (3, 2))
        self.assertEqual(float(metrics["roi_pct"]), -20)
        self.assertEqual(float(metrics["fixture_equal_roi_pct"]), -40)
        self.assertEqual(float(metrics["profit_units"]), -0.6)

    def test_void_and_push_are_neither_missing_statistics_nor_losses(self):
        for outcome in ("void", "push"):
            with self.subTest(outcome=outcome):
                self.results[0]["outcome"] = outcome
                metrics = self.audit()["cohorts"]["original_top"]["metrics"]
                self.assertEqual(float(metrics["roi_pct"]), 0)
                self.assertEqual(metrics["losses"], 0)
                self.assertIsNone(metrics["hit_rate_pct"])

    def test_results_cannot_add_positions_to_any_cohort(self):
        extra = make_row(self.snapshot, fid=999, score=100)
        self.results.append(settlement(self.snapshot, extra))
        self.assertEqual(self.audit()["cohorts"]["original_top"]["metrics"]["positions"], 1)

    def test_result_for_different_line_period_or_freeze_is_not_joined(self):
        for field, value in (("line", 14.5), ("settlement_period", "first_half"), ("direction", "over")):
            with self.subTest(field=field):
                result = settlement(self.snapshot, self.row)
                result["market_identity"][field] = value
                self.results = [result]
                self.assertEqual(self.audit()["cohorts"]["original_top"]["metrics"]["settled"], 0)
        self.results = [settlement(self.snapshot, self.row)]
        self.results[0]["freeze"]["id"] = "different-original-freeze"
        self.assertEqual(self.audit()["cohorts"]["original_top"]["metrics"]["settled"], 0)

    def test_duplicate_results_are_unresolved(self):
        self.results.append(deepcopy(self.results[0]))
        row = self.audit()["cohorts"]["original_top"]["rows"][0]
        self.assertIsNone(row["settlement"])
        self.assertEqual(row["settlement_reason"], "duplicate_settlement")

    def test_incomplete_nonfinal_future_or_sourceless_results_rejected(self):
        for field, value in (("fixture_status", "LIVE"), ("result_source", ""),
                             ("finished_at", "2026-11-01T19:00:00Z"),
                             ("settled_at", "2026-11-02T00:00:00Z"),
                             ("date", "2026-11-02"), ("outcome", None), ("outcome", "half_win")):
            with self.subTest(field=field):
                self.results = [settlement(self.snapshot, self.row)]
                self.results[0][field] = value
                self.assertIsNone(self.audit()["cohorts"]["original_top"]["metrics"]["roi_pct"])

    def test_results_not_available_at_prematch_cutoff(self):
        top = self.audit(cutoff="2026-11-01T10:00:00Z")["cohorts"]["original_top"]
        self.assertEqual(top["metrics"]["settled"], 0)
        self.assertIsNone(top["metrics"]["roi_pct"])

    def test_top_mismatch_not_silently_replaced_from_background(self):
        self.snapshot["top_positions"][0]["final_assessment_pct"] = 99
        row = self.audit()["cohorts"]["original_top"]["rows"][0]
        self.assertEqual(row["original_position"]["final_assessment_pct"], 99)
        self.assertEqual(row["validation"], "unverified")

    def test_original_display_annotations_do_not_invalidate_genuine_top(self):
        self.snapshot["top_positions"][0]["original_display_label"] = "Original annotation"
        top = self.audit()["cohorts"]["original_top"]
        self.assertEqual(top["status"], "complete")
        self.assertEqual(top["metrics"]["settled"], 1)

    def test_equivalent_timestamp_offsets_and_numeric_strings_can_join_result(self):
        self.results[0]["freeze"]["run_id"] = 11
        self.results[0]["freeze"]["captured_at_utc"] = "2026-11-01T10:05:00+01:00"
        self.results[0]["quote"] = deepcopy(self.row["frozen_quote"])
        self.assertEqual(self.audit()["cohorts"]["original_top"]["metrics"]["settled"], 1)

    def test_missing_sources_are_not_reported_as_genuine_zero_sample(self):
        self.snapshots.clear()
        for cohort in self.audit()["cohorts"].values():
            self.assertIsNone(cohort["metrics"]["positions"])
            self.assertEqual(cohort["rows"], [])

    def test_read_only_inputs_and_returned_data_do_not_change_n_or_freeze(self):
        self.snapshot["N"] = 123
        before = deepcopy((self.runs, self.snapshots, self.results))
        out = self.audit()
        json.dumps(out, allow_nan=False)
        out["cohorts"]["original_top"]["rows"][0]["original_position"]["line"] = 999
        self.assertEqual((self.runs, self.snapshots, self.results), before)


if __name__ == "__main__":
    unittest.main()
