"""Native settlement contract fixtures are TEST INPUTS, never observations/N."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from multimodel_v2.settlement import build_native_settlements
from tests.test_multimodel_v2_audit import AUDIT_TIME, frozen_evidence, make_row


def native_snapshot():
    snapshot = frozen_evidence()[1][0]
    snapshot["schema"] = "api-market-scan-v3"
    return snapshot


def outcome(snapshot, row, state="WIN"):
    return {"publication_id": snapshot["publication"]["id"], "date": snapshot["date"],
            "market_identity": deepcopy(row["frozen_quote"]["market_identity"]),
            "frozen_quote": deepcopy(row["frozen_quote"]), "fixture_status": "FT",
            "finished_at": "2026-11-01T22:00:00Z", "settled_at": "2026-11-01T22:01:00Z",
            "outcome": state, "result_source": "test-only original final-statistics evidence"}


class NativeSettlementTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = native_snapshot()
        self.row = self.snapshot["background_candidates"][0]
        self.results = [outcome(self.snapshot, self.row)]

    def audit(self, **kwargs):
        params = {"as_of": AUDIT_TIME, "full_pool_complete": True}
        params.update(kwargs)
        return build_native_settlements(self.snapshot, self.results, **params)

    def top(self, **kwargs):
        return self.audit(**kwargs)["cohorts"]["original_top"]

    def test_three_independent_cohorts_preserve_source_top_and_below67_fouls(self):
        rows = [make_row(self.snapshot, fid=1, score=55),
                make_row(self.snapshot, fid=2, score=75, market="corners"),
                make_row(self.snapshot, fid=3, score=80)]
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = deepcopy(rows[:1])
        self.results = [outcome(self.snapshot, row) for row in rows]
        audit = self.audit()
        self.assertEqual(audit["status"], "READY")
        self.assertEqual([audit["cohorts"][c]["metrics"]["positions"] for c in (
            "original_top", "qualifying_api", "fouls_under")], [1, 2, 2])
        self.assertEqual(audit["cohorts"]["original_top"]["rows"][0]["original_position"], rows[0])

    def test_exact_native_id_market_and_original_quote_resolve_win(self):
        result = self.top()
        self.assertEqual(result["rows"][0]["state"], "WIN")
        self.assertEqual(result["metrics"]["roi_pct"], "75.000000")
        self.assertEqual(result["metrics"]["fixture_equal_roi_pct"], "75.000000")

    def test_prediction_id_alias_requires_same_original_publication(self):
        self.results[0]["prediction_id"] = self.results[0].pop("publication_id")
        self.assertEqual(self.top()["rows"][0]["state"], "WIN")
        self.results[0]["publication_id"] = "another-original-id"
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")
        self.assertIn("outcome_publication_ids_conflict", [r["reason"] for r in self.audit()["rejections"]])

    def test_1391_foreign_id_rows_are_rejected_before_missing_other_fields(self):
        # Counts/ID are observed evidence; these minimal rows are unit fixtures.
        evidence = json.loads((Path(__file__).parents[1] / "docs/MULTIMODEL_V2_E2E_EVIDENCE_2026-11-02.json").read_text())
        foreign = evidence["recorded_settlement_check"]["prediction_id_counts"]
        self.results = [{"prediction_id": native_id} for native_id, count in foreign.items() for _ in range(count)]
        result = self.audit()
        self.assertEqual(result["outcomes_received"], 1391)
        self.assertEqual(len(result["rejections"]), 1391)
        self.assertEqual({r["reason"] for r in result["rejections"]}, {"wrong_native_publication_id"})
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")

    def test_wrong_fixture_line_scope_direction_period_cannot_join(self):
        for field, value in (("fixture_id", 999), ("line", 13.50000001), ("market_scope", "match"),
                             ("direction", "over"), ("settlement_period", "first_half")):
            with self.subTest(field=field):
                self.results = [outcome(self.snapshot, self.row)]
                self.results[0]["market_identity"][field] = value
                result = self.top()
                self.assertEqual(result["rows"][0]["state"], "UNRESOLVED")
                self.assertIsNone(result["metrics"]["roi_pct"])

    def test_wrong_bookmaker_price_or_quote_timestamp_cannot_join(self):
        for field, value in (("bookmaker", "DifferentBook"), ("selected_odd", "1.75000001"),
                             ("provider_updated_at", "2026-11-01T08:58:00Z")):
            with self.subTest(field=field):
                self.results = [outcome(self.snapshot, self.row)]
                self.results[0]["frozen_quote"][field] = value
                self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")
                self.assertIn("outcome_frozen_quote_mismatch", [r["reason"] for r in self.audit()["rejections"]])

    def test_outcome_without_frozen_quote_is_not_optional_price_evidence(self):
        del self.results[0]["frozen_quote"]
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")
        self.assertIsNone(self.top()["metrics"]["roi_pct"])

    def test_recorded_quote_reference_is_part_of_exact_join_if_present(self):
        reference = {"provider": "test-provider", "response_sha256": "a" * 64}
        for quote in (self.row["market_data"]["quotes"][0], self.row["frozen_quote"]):
            quote["source_reference"] = deepcopy(reference)
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        self.results = [outcome(self.snapshot, self.row)]
        self.assertEqual(self.top()["rows"][0]["state"], "WIN")
        self.results[0]["frozen_quote"]["source_reference"]["response_sha256"] = "b" * 64
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")

    def test_duplicate_identical_or_conflicting_results_are_unresolved(self):
        for state in ("WIN", "LOSS"):
            with self.subTest(state=state):
                self.results = [outcome(self.snapshot, self.row), outcome(self.snapshot, self.row, state)]
                row = self.top()["rows"][0]
                self.assertEqual(row["state"], "UNRESOLVED")
                self.assertEqual(row["settlement_reason"], "duplicate_native_settlement")

    def test_missing_result_never_becomes_loss_or_survivor_roi(self):
        extra = make_row(self.snapshot, fid=124)
        self.snapshot["background_candidates"].append(extra)
        self.snapshot["top_positions"].append(deepcopy(extra))
        metrics = self.top()["metrics"]
        self.assertEqual((metrics["positions"], metrics["settled"], metrics["unresolved"], metrics["losses"]), (2, 1, 1, 0))
        self.assertIsNone(metrics["roi_pct"])
        self.assertIsNone(metrics["fixture_equal_roi_pct"])

    def test_void_refunds_stake_without_inventing_loss_or_binary_hit(self):
        self.results[0]["outcome"] = "VOID"
        metrics = self.top()["metrics"]
        self.assertEqual((metrics["voids"], metrics["losses"], metrics["profit_units"]), (1, 0, "0"))
        self.assertEqual(metrics["roi_pct"], "0.000000")
        self.assertIsNone(metrics["hit_rate_pct"])

    def test_cancelled_event_needs_explicit_original_void_decision(self):
        self.results[0].update(outcome="VOID", fixture_status="CANC", settled_at="2026-11-01T10:00:00Z")
        del self.results[0]["finished_at"]
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")
        self.results[0].update(void_reason="Recorded bookmaker cancellation rule", settlement_reference="test-native-void-decision")
        self.assertEqual(self.top()["rows"][0]["state"], "VOID")
        self.assertEqual(self.top()["metrics"]["roi_pct"], "0.000000")

    def test_explicit_void_cannot_predate_its_original_publication(self):
        self.results[0].update(outcome="VOID", fixture_status="CANC", settled_at="2026-11-01T08:00:00Z",
                               void_reason="Recorded reason", settlement_reference="test-native-void-decision")
        self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")

    def test_explicit_unresolved_or_unsupported_outcome_does_not_settle(self):
        for state in ("UNRESOLVED", "HALF_WIN", 1, None, []):
            with self.subTest(state=state):
                self.results[0]["outcome"] = state
                result = self.top()
                self.assertEqual(result["rows"][0]["state"], "UNRESOLVED")
                self.assertIsNone(result["metrics"]["roi_pct"])

    def test_correlated_markets_keep_unit_and_fixture_equal_denominators_separate(self):
        rows = [make_row(self.snapshot, fid=1, line=3.5, odd=1.20, market="corners"),
                make_row(self.snapshot, fid=1, line=4.5, odd=1.20, market="corners"),
                make_row(self.snapshot, fid=2, odd=2.00)]
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = deepcopy(rows)
        self.results = [outcome(self.snapshot, r, "WIN" if i < 2 else "LOSS") for i, r in enumerate(rows)]
        metrics = self.audit()["cohorts"]["qualifying_api"]["metrics"]
        self.assertEqual((metrics["positions"], metrics["fixtures"]), (3, 2))
        self.assertEqual(float(metrics["roi_pct"]), -20)
        self.assertEqual(float(metrics["fixture_equal_roi_pct"]), -40)

    def test_contradictory_fixture_kickoff_or_names_block_all_affected_cohorts(self):
        for field, changed in (("kickoff", "2026-11-01T21:00:00Z"),
                               ("home", "Contradictory home"), ("away", "Contradictory away")):
            with self.subTest(field=field):
                self.setUp()
                rows = [make_row(self.snapshot, fid=1, line=3.5), make_row(self.snapshot, fid=1, line=4.5)]
                rows[1][field] = changed
                self.snapshot["background_candidates"] = rows
                self.snapshot["top_positions"] = deepcopy(rows)
                self.results = [outcome(self.snapshot, row) for row in rows]
                result = self.audit()
                self.assertEqual(result["conflicting_fixture_ids"], ["1"])
                self.assertEqual(result["status"], "SOURCE_BLOCKED")
                for cohort in result["cohorts"].values():
                    self.assertEqual(cohort["status"], "AUDYT NIEPEŁNY")
                    self.assertIsNone(cohort["metrics"]["positions"])
                    self.assertIsNone(cohort["metrics"]["roi_pct"])
                    self.assertIsNone(cohort["metrics"]["fixture_equal_roi_pct"])
                    self.assertEqual(len(cohort["rows"]), 2)

    def test_conflicting_optional_native_team_ids_block_fixture_consistency(self):
        for field in ("home_id", "away_id"):
            with self.subTest(field=field):
                self.setUp()
                rows = [make_row(self.snapshot, fid=1, line=3.5), make_row(self.snapshot, fid=1, line=4.5)]
                rows[0][field], rows[1][field] = 10, 20
                self.snapshot["background_candidates"] = rows
                self.snapshot["top_positions"] = deepcopy(rows)
                self.results = [outcome(self.snapshot, row) for row in rows]
                result = self.audit()
                self.assertEqual(result["conflicting_fixture_ids"], ["1"])
                self.assertIsNone(result["cohorts"]["original_top"]["metrics"]["roi_pct"])

    def test_equivalent_kickoff_offsets_and_matching_optional_ids_are_consistent(self):
        rows = [make_row(self.snapshot, fid=1, line=3.5), make_row(self.snapshot, fid=1, line=4.5)]
        rows[0].update(home_id=10, away_id=20)
        rows[1].update(kickoff="2026-11-01T21:00:00+01:00", home_id="10", away_id="20")
        self.snapshot["background_candidates"] = rows
        self.snapshot["top_positions"] = deepcopy(rows)
        self.results = [outcome(self.snapshot, row) for row in rows]
        result = self.audit()
        self.assertEqual(result["conflicting_fixture_ids"], [])
        self.assertEqual(result["status"], "READY")

    def test_missing_native_team_names_prevents_financial_settlement(self):
        del self.row["home"]
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        self.assertEqual(self.audit()["status"], "SOURCE_BLOCKED")
        self.assertIsNone(self.top()["metrics"]["roi_pct"])

    def test_top_native_team_ids_must_agree_with_original_background(self):
        self.row.update(home_id=10, away_id=20)
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        self.snapshot["top_positions"][0]["home_id"] = 999
        self.assertEqual(self.top()["status"], "AUDYT NIEPEŁNY")
        self.assertIsNone(self.top()["metrics"]["roi_pct"])

    def test_recorded_team_side_cannot_contradict_native_team_id(self):
        self.row.update(home_id=10, away_id=20, team_side="away")
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        result = self.audit()
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIn("native_team_side_identity_mismatch", self.top()["rows"][0]["source_errors"])

    def test_missing_original_frozen_price_prevents_financial_settlement(self):
        del self.row["frozen_quote"]
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        for cohort in self.audit()["cohorts"].values():
            self.assertIsNone(cohort["metrics"]["roi_pct"])
            self.assertEqual(cohort["status"], "AUDYT NIEPEŁNY")

    def test_other_eligible_quote_cannot_replace_original_price_outside_fouls_band(self):
        for quote in (self.row["market_data"]["quotes"][0], self.row["frozen_quote"]):
            quote["selected_odd"] = 1.20
        alternative = deepcopy(self.row["market_data"]["quotes"][0])
        alternative.update(bookmaker="AnotherRecordedBook", selected_odd=1.75)
        self.row["market_data"]["quotes"].append(alternative)
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        self.results = [outcome(self.snapshot, self.row)]
        cohorts = self.audit()["cohorts"]
        self.assertEqual(cohorts["qualifying_api"]["status"], "COMPLETE")
        self.assertEqual(cohorts["fouls_under"]["metrics"]["known_positions"], 1)
        self.assertIsNone(cohorts["fouls_under"]["metrics"]["roi_pct"])

    def test_missing_independent_quote_identity_is_not_filled_from_candidate(self):
        del self.row["market_data"]["quotes"][0]["market_identity"]
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        result = self.audit()
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIsNone(result["cohorts"]["original_top"]["metrics"]["roi_pct"])

    def test_explicit_no_quote_rejection_is_known_nonmember_not_unknown_pool(self):
        extra = make_row(self.snapshot, fid=124, score=80)
        extra["market_data"]["quotes"] = []
        del extra["frozen_quote"]
        self.snapshot["background_candidates"].append(extra)
        result = self.audit()
        self.assertEqual(result["cohorts"]["qualifying_api"]["status"], "COMPLETE")
        self.assertEqual(result["cohorts"]["qualifying_api"]["metrics"]["positions"], 1)
        del extra["market_data"]["quotes"]
        self.assertEqual(self.audit()["cohorts"]["qualifying_api"]["status"], "AUDYT NIEPEŁNY")

    def test_partial_pool_is_not_complete_zero_api_or_fouls(self):
        result = self.audit(full_pool_complete=False)
        self.assertEqual(result["cohorts"]["original_top"]["status"], "COMPLETE")
        for name in ("qualifying_api", "fouls_under"):
            metrics = result["cohorts"][name]["metrics"]
            self.assertIsNone(metrics["positions"])
            self.assertIsNone(metrics["roi_pct"])
            self.assertEqual(metrics["known_positions"], 1)

    def test_count_mismatch_blocks_full_population(self):
        self.snapshot["candidate_count"] = 1473
        result = self.audit()
        self.assertFalse(result["full_pool_declared_complete"])
        self.assertIsNone(result["cohorts"]["qualifying_api"]["metrics"]["positions"])

    def test_external_export_completeness_never_mutates_native_payload(self):
        before = deepcopy(self.snapshot)
        valid = {"full_pool_complete": True, "source_eligible": True, "status": "COMPLETE", "original_top_eligible": True}
        result = self.audit(full_pool_complete=None, full_pool_verification=valid)
        self.assertEqual(result["status"], "READY")
        valid.update(source_eligible=False, status="INCOMPLETE")
        result = self.audit(full_pool_complete=None, full_pool_verification=valid)
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertEqual(result["cohorts"]["original_top"]["status"], "COMPLETE")
        self.assertIsNone(result["cohorts"]["qualifying_api"]["metrics"]["roi_pct"])
        valid["original_top_eligible"] = False
        self.assertIsNone(self.audit(full_pool_complete=None, full_pool_verification=valid)["cohorts"]["original_top"]["metrics"]["roi_pct"])
        self.assertEqual(self.snapshot, before)

    def test_top_frozen_quote_is_independent_of_unselected_background(self):
        top = self.snapshot["top_positions"][0]
        del self.row["frozen_quote"]
        self.results = [outcome(self.snapshot, top)]
        before = deepcopy(self.snapshot)
        result = self.audit()
        self.assertEqual(result["cohorts"]["original_top"]["status"], "COMPLETE")
        self.assertEqual(result["cohorts"]["original_top"]["metrics"]["roi_pct"], "75.000000")
        for name in ("qualifying_api", "fouls_under"):
            self.assertEqual(result["cohorts"][name]["status"], "AUDYT NIEPEŁNY")
            self.assertIsNone(result["cohorts"][name]["metrics"]["roi_pct"])
        self.assertEqual(self.snapshot, before)
        self.assertNotIn("frozen_quote", self.row)

    def test_minimal_native_top_uses_background_quote_reference_without_field_copy(self):
        top = self.snapshot["top_positions"][0]
        del self.row["frozen_quote"]
        del top["market_data"]
        self.results = [outcome(self.snapshot, top)]
        original_top = deepcopy(top)
        result = self.top()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["rows"][0]["original_position"], original_top)
        self.assertNotIn("market_data", result["rows"][0]["original_position"])

    def test_top_and_pool_may_retain_distinct_original_prices_without_cross_join(self):
        quote = deepcopy(self.row["market_data"]["quotes"][0])
        quote.update(bookmaker="OtherOriginalBook", selected_odd=2.00)
        self.row["market_data"]["quotes"].append(quote)
        self.snapshot["top_positions"] = [deepcopy(self.row)]
        self.snapshot["top_positions"][0]["frozen_quote"] = deepcopy(quote)
        self.results = [outcome(self.snapshot, self.row), outcome(self.snapshot, self.snapshot["top_positions"][0])]
        cohorts = self.audit()["cohorts"]
        self.assertEqual(cohorts["original_top"]["metrics"]["roi_pct"], "100.000000")
        self.assertEqual(cohorts["qualifying_api"]["metrics"]["roi_pct"], "75.000000")

    def test_external_top_eligibility_cannot_bypass_native_publication_identity(self):
        verification = {"full_pool_complete": False, "source_eligible": False,
                        "original_top_eligible": True, "status": "INCOMPLETE"}
        del self.snapshot["publication"]["id"]
        result = self.audit(full_pool_complete=None, full_pool_verification=verification)
        self.assertEqual(result["cohorts"]["original_top"]["status"], "AUDYT NIEPEŁNY")
        self.assertIsNone(result["cohorts"]["original_top"]["metrics"]["roi_pct"])

    def test_top_verification_flag_missing_is_not_inferred_from_full_pool(self):
        verification = {"full_pool_complete": True, "source_eligible": True, "status": "COMPLETE"}
        result = self.audit(full_pool_complete=None, full_pool_verification=verification)
        self.assertEqual(result["cohorts"]["original_top"]["status"], "AUDYT NIEPEŁNY")
        self.assertIsNone(result["cohorts"]["original_top"]["metrics"]["roi_pct"])

    def test_duplicate_candidates_do_not_inflate_complete_api_population(self):
        self.snapshot["background_candidates"].append(deepcopy(self.row))
        self.assertEqual(self.audit()["cohorts"]["qualifying_api"]["status"], "AUDYT NIEPEŁNY")
        self.assertIsNone(self.audit()["cohorts"]["qualifying_api"]["metrics"]["roi_pct"])
        self.assertIsNone(self.audit()["cohorts"]["qualifying_api"]["metrics"]["positions"])

    def test_top_order_retained_and_changed_native_top_not_replaced(self):
        other = make_row(self.snapshot, fid=124, score=99)
        self.snapshot["background_candidates"].append(other)
        self.snapshot["top_positions"].append(deepcopy(other))
        self.results.append(outcome(self.snapshot, other))
        self.assertEqual([r["market_identity"]["fixture_id"] for r in self.top()["rows"]], ["123", "124"])
        self.snapshot["top_positions"][0]["final_assessment_pct"] = 100
        result = self.top()
        self.assertEqual(result["rows"][0]["original_position"]["final_assessment_pct"], 100)
        self.assertEqual(result["status"], "AUDYT NIEPEŁNY")

    def test_quote_or_freeze_at_or_after_kickoff_is_rejected(self):
        for which in ("quote", "freeze"):
            with self.subTest(which=which):
                self.setUp()
                if which == "quote":
                    for q in (self.row["market_data"]["quotes"][0], self.row["frozen_quote"]):
                        q["provider_updated_at"] = self.row["kickoff"]
                else:
                    self.snapshot["publication"]["captured_at_utc"] = self.row["kickoff"]
                self.snapshot["top_positions"] = [deepcopy(self.row)]
                self.results = [outcome(self.snapshot, self.row)]
                self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")
                self.assertIsNone(self.top()["metrics"]["roi_pct"])

    def test_result_date_finality_source_or_time_must_be_recorded(self):
        for field, value in (("date", "2026-11-02"), ("fixture_status", "LIVE"), ("result_source", ""),
                             ("finished_at", self.row["kickoff"]), ("settled_at", "2026-11-02T10:00:00Z")):
            with self.subTest(field=field):
                self.results = [outcome(self.snapshot, self.row)]
                self.results[0][field] = value
                self.assertEqual(self.top()["rows"][0]["state"], "UNRESOLVED")

    def test_outcome_not_available_at_replay_cutoff_is_unresolved(self):
        result = self.top(as_of="2026-11-01T21:00:00Z")
        self.assertIsNone(result["metrics"]["roi_pct"])
        self.assertEqual(result["rows"][0]["state"], "UNRESOLVED")

    def test_original_native_id_is_required_not_capture_hash_substitute(self):
        del self.snapshot["publication"]["id"]
        self.assertEqual(self.audit()["status"], "SOURCE_BLOCKED")
        self.assertIsNone(self.top()["metrics"]["roi_pct"])

    def test_replay_is_deterministic_and_cannot_write_n_or_modify_sources(self):
        self.snapshot["N"] = 150
        before = deepcopy((self.snapshot, self.results))
        first = self.audit()
        self.assertEqual(first, self.audit())
        self.assertEqual((self.snapshot, self.results), before)
        self.assertEqual(first["n_effect"], 0)
        self.assertFalse(first["register_writes"])
        self.assertFalse(first["source_algorithms_called"])
        json.dumps(first, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
