"""Offline checks of provenance, Warsaw dates and independent observation rules."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from multimodel_v2.fouls_under import (
    BELOW_THRESHOLD, NO_CANDIDATES, WATCH, fouls_under_watchlist,
)
from multimodel_v2.source_manifest import build_source_manifest, instant

SHA = "a" * 40
DAY = "2026-11-01"
CUTOFF = "2026-11-01T10:00:00Z"
ARTIFACT = "api-market-multiday-experiment"


def evidence():
    identity = {"fixture_id": 123, "market": "fouls", "market_scope": "team",
                "team_id": 10, "direction": "under", "line": 13.5,
                "settlement_period": "regulation_time"}
    row = dict(identity, home="Gospodarze", away="Goście",
               kickoff="2026-11-01T20:00:00Z", final_assessment_pct=67,
               market_data={"quotes": [{"market_identity": copy.deepcopy(identity),
                   "bookmaker": "RecordedBook", "selected_odd": 1.75,
                   "provider_updated_at": "2026-11-01T08:59:00Z"}]})
    run = {"id": 11, "status": "completed", "conclusion": "success", "head_sha": SHA,
           "path": ".github/workflows/api-market-multiday-experiment.yml",
           "run_started_at": "2026-11-01T08:00:00Z", "updated_at": "2026-11-01T09:30:00Z",
           "artifacts": [{"name": ARTIFACT, "expired": False}],
           "date_statuses": [{"date": DAY, "status": "ok", "artifact_name": ARTIFACT}]}
    snapshot = {"date": DAY, "run_id": 11, "head_sha": SHA, "artifact_name": ARTIFACT,
                "generated_at_utc": "2026-11-01T09:00:00Z", "background_candidates": [row]}
    return [run], [snapshot]


def change_market(row, **changes):
    row.update(changes)
    for quote in row["market_data"]["quotes"]:
        quote["market_identity"].update(changes)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.runs, self.snapshots = evidence()
        self.row = self.snapshots[0]["background_candidates"][0]
        self.quote = self.row["market_data"]["quotes"][0]

    def manifest(self, day=DAY, cutoff=CUTOFF):
        return build_source_manifest(day, self.runs, self.snapshots, as_of=cutoff)

    def assertRejected(self, reason, *, blocked=False):
        result = self.manifest()
        self.assertEqual(result["records"], [])
        self.assertIn(reason, [r["reason"] for r in result["rejections"]])
        if blocked:
            self.assertEqual(result["status"], "blocked")

    def test_complete_source_has_run_sha_artifact_snapshot_kickoff_and_identity(self):
        result = self.manifest()
        self.assertEqual(result["status"], "covered")
        self.assertEqual(len(result["records"]), 1)
        source = result["records"][0]["source"]
        self.assertEqual(source["run_id"], "11")
        self.assertEqual(source["conclusion"], "success")
        self.assertEqual(source["head_sha"], SHA)
        self.assertEqual(source["artifact_names"], [ARTIFACT])
        self.assertEqual(source["snapshot_at"], "2026-11-01T09:00:00Z")
        self.assertEqual(result["records"][0]["market_identity"]["line"], "13.5")
        json.dumps(result, allow_nan=False)

    def test_unfinished_failed_cancelled_or_skipped_run_blocks_date(self):
        for status, conclusion in (("in_progress", None), ("completed", "failure"),
                                    ("completed", "cancelled"), ("completed", "skipped")):
            with self.subTest(status=status, conclusion=conclusion):
                self.runs[0].update(status=status, conclusion=conclusion)
                self.assertRejected("run_not_successful", blocked=True)

    def test_missing_run_blocks_date(self):
        self.runs.clear()
        self.assertRejected("no_verified_run", blocked=True)

    def test_successful_closing_workflow_is_not_scan_evidence(self):
        self.runs[0]["path"] = ".github/workflows/api-market-closing.yml"
        self.assertRejected("wrong_workflow", blocked=True)

    def test_completed_run_must_exist_by_observation_cutoff(self):
        self.runs[0]["updated_at"] = "2026-11-01T10:00:01Z"
        self.assertRejected("run_outside_cutoff", blocked=True)

    def test_completion_cannot_precede_start(self):
        self.runs[0]["updated_at"] = "2026-11-01T07:00:00Z"
        self.assertRejected("run_outside_cutoff", blocked=True)

    def test_no_retroactive_run_for_previous_local_day(self):
        self.runs[0]["run_started_at"] = "2026-11-02T08:00:00Z"
        self.runs[0]["updated_at"] = "2026-11-02T09:00:00Z"
        result = self.manifest(cutoff="2026-11-02T10:00:00Z")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("run_after_report_date", [x["reason"] for x in result["rejections"]])

    def test_duplicate_run_metadata_is_ambiguous(self):
        self.runs.append(copy.deepcopy(self.runs[0]))
        self.assertRejected("duplicate_run_id", blocked=True)

    def test_sha_must_be_full_commit_sha(self):
        self.runs[0]["head_sha"] = "aaaaaaa"
        self.assertRejected("invalid_sha", blocked=True)

    def test_snapshot_must_belong_to_exact_run_sha(self):
        self.snapshots[0]["head_sha"] = "b" * 40
        self.assertRejected("snapshot_sha_mismatch", blocked=True)

    def test_artifact_must_be_available_and_belong_to_run(self):
        for artifacts in ([], [{"name": ARTIFACT, "expired": True}],
                          [{"name": ARTIFACT}], [{"name": "other", "expired": False}]):
            with self.subTest(artifacts=artifacts):
                self.runs[0]["artifacts"] = artifacts
                self.assertRejected("date_not_covered", blocked=True)

    def test_snapshot_cannot_reference_unlisted_artifact(self):
        self.snapshots[0]["artifact_name"] = "other"
        self.assertRejected("snapshot_artifact_unavailable", blocked=True)

    def test_date_needs_explicit_unique_ok_status(self):
        for statuses in ([], [{"date": DAY, "status": "error", "artifact_name": ARTIFACT}],
                          self.runs[0]["date_statuses"] * 2):
            with self.subTest(statuses=statuses):
                self.runs[0]["date_statuses"] = statuses
                self.assertRejected("date_not_covered", blocked=True)

    def test_two_day_run_does_not_cover_third_date(self):
        self.runs[0]["date_statuses"].append(
            {"date": "2026-11-02", "status": "ok", "artifact_name": ARTIFACT})
        second = copy.deepcopy(self.snapshots[0])
        second["date"] = "2026-11-02"
        second["background_candidates"][0]["kickoff"] = "2026-11-02T20:00:00Z"
        self.snapshots.append(second)
        self.assertEqual(self.manifest("2026-11-02")["status"], "covered")
        self.assertEqual(self.manifest("2026-11-03")["status"], "blocked")

    def test_missing_snapshot_blocks_even_with_successful_run_and_date_status(self):
        self.snapshots.clear()
        self.assertRejected("no_verified_snapshot_for_date", blocked=True)

    def test_wrong_snapshot_date_is_not_reassigned(self):
        self.snapshots[0]["date"] = "2026-10-31"
        self.assertRejected("snapshot_date_mismatch", blocked=True)

    def test_missing_snapshot_timestamp(self):
        del self.snapshots[0]["generated_at_utc"]
        self.assertRejected("missing_timestamp", blocked=True)

    def test_missing_rows_is_different_from_verified_empty_scan(self):
        self.snapshots[0]["background_candidates"] = []
        self.assertEqual(self.manifest()["status"], "covered")
        del self.snapshots[0]["background_candidates"]
        self.assertRejected("missing_snapshot_rows", blocked=True)

    def test_snapshot_must_be_inside_run_interval(self):
        for stamp in ("2026-11-01T07:59:59Z", "2026-11-01T09:30:01Z"):
            with self.subTest(stamp=stamp):
                self.snapshots[0]["generated_at_utc"] = stamp
                self.assertRejected("snapshot_outside_run", blocked=True)

    def test_capture_at_or_after_kickoff_is_never_prematch(self):
        for kickoff in ("2026-11-01T09:00:00Z", "2026-11-01T08:59:59Z"):
            with self.subTest(kickoff=kickoff):
                self.row["kickoff"] = kickoff
                self.assertRejected("snapshot_lookahead")

    def test_quote_must_not_come_from_future_of_snapshot(self):
        self.quote["provider_updated_at"] = "2026-11-01T09:00:01Z"
        self.assertRejected("quote_lookahead")

    def test_quote_at_capture_is_valid(self):
        self.quote["provider_updated_at"] = self.snapshots[0]["generated_at_utc"]
        self.assertEqual(len(self.manifest()["records"]), 1)

    def test_kickoff_date_uses_warsaw_not_utc(self):
        self.row["kickoff"] = "2026-11-01T23:30:00Z"  # 00:30 on Nov 2 locally
        self.assertRejected("kickoff_date_mismatch")
        self.row["kickoff"] = "2026-10-31T23:30:00Z"  # Nov 1 locally, already started
        self.assertRejected("snapshot_lookahead")

    def test_missing_odds_or_price_is_not_filled(self):
        self.row["market_data"]["quotes"] = []
        self.assertRejected("missing_odds")
        self.row["market_data"]["quotes"] = [self.quote]
        del self.quote["selected_odd"]
        self.assertRejected("invalid_number")

    def test_invalid_numeric_prices_rejected(self):
        for odd in (None, True, 1, 0, -1, "NaN", "Infinity", float("inf"), "junk"):
            with self.subTest(odd=odd):
                self.quote["selected_odd"] = odd
                self.assertEqual(self.manifest()["records"], [])

    def test_bookmaker_and_quote_timestamp_required(self):
        self.quote["bookmaker"] = " "
        self.assertRejected("missing_bookmaker")
        self.quote["bookmaker"] = "RecordedBook"
        self.quote.pop("provider_updated_at")
        self.assertRejected("missing_timestamp")

    def test_all_market_identity_dimensions_must_match_quote(self):
        changes = {"fixture_id": 124, "market": "corners", "market_scope": "match",
                   "team_id": 20, "direction": "over", "line": 13.50000001,
                   "settlement_period": "extra_time"}
        original = copy.deepcopy(self.quote["market_identity"])
        for field, value in changes.items():
            with self.subTest(field=field):
                self.quote["market_identity"] = dict(original, **{field: value})
                self.assertEqual(self.manifest()["records"], [])

    def test_quote_identity_cannot_be_inferred_from_candidate(self):
        del self.quote["market_identity"]
        self.assertRejected("incomplete_market_identity")

    def test_exact_line_does_not_round_but_accepts_equivalent_decimal(self):
        self.quote["market_identity"]["line"] = "13.50"
        self.assertEqual(len(self.manifest()["records"]), 1)
        self.quote["market_identity"]["line"] = "13.50000001"
        self.assertRejected("quote_market_mismatch")

    def test_scope_settlement_team_and_line_are_never_defaulted(self):
        original = copy.deepcopy(self.row)
        for field in ("market_scope", "settlement_period", "team_id", "line", "direction"):
            with self.subTest(field=field):
                self.snapshots[0]["background_candidates"] = [copy.deepcopy(original)]
                del self.snapshots[0]["background_candidates"][0][field]
                self.assertEqual(self.manifest()["records"], [])

    def test_selected_and_side_price_must_agree(self):
        self.quote["under_odd"] = 1.99
        self.assertRejected("conflicting_odds")

    def test_one_bad_quote_does_not_hide_independently_verified_quote(self):
        bad = copy.deepcopy(self.quote)
        bad["market_identity"]["line"] = 11.5
        self.row["market_data"]["quotes"].append(bad)
        self.assertEqual(len(self.manifest()["records"][0]["quotes"]), 1)

    def test_duplicate_fixture_and_market_rejected_rather_than_double_counted(self):
        self.snapshots[0]["background_candidates"].append(copy.deepcopy(self.row))
        self.assertRejected("duplicate_fixture_market")

    def test_different_markets_on_same_fixture_are_allowed(self):
        other = copy.deepcopy(self.row)
        change_market(other, line=14.5)
        self.snapshots[0]["background_candidates"].append(other)
        self.assertEqual(len(self.manifest()["records"]), 2)

    def test_conflicting_kickoffs_poison_all_markets_on_fixture(self):
        other = copy.deepcopy(self.row)
        change_market(other, line=14.5)
        other["kickoff"] = "2026-11-01T21:00:00Z"
        self.snapshots[0]["background_candidates"].append(other)
        self.assertRejected("conflicting_fixture")

    def test_reruns_keep_earliest_freeze_independent_of_input_order(self):
        later_run = copy.deepcopy(self.runs[0])
        later_run["id"] = 12
        later_snapshot = copy.deepcopy(self.snapshots[0])
        later_snapshot.update(run_id=12, generated_at_utc="2026-11-01T09:10:00Z")
        later_snapshot["background_candidates"][0]["final_assessment_pct"] = 99
        self.runs.append(later_run)
        self.snapshots.insert(0, later_snapshot)
        result = self.manifest()
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["final_assessment_pct"], "67")
        self.assertEqual(result["records"][0]["source"]["run_id"], "11")

    def test_inputs_and_output_are_independent(self):
        before = copy.deepcopy((self.runs, self.snapshots))
        result = self.manifest()
        result["records"][0]["quotes"][0]["bookmaker"] = "changed"
        self.assertEqual((self.runs, self.snapshots), before)

    def test_malformed_source_objects_fail_closed_with_reasons(self):
        self.runs.extend([None, {}, {"id": True}])
        self.snapshots.append(None)
        result = self.manifest()
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("invalid_run", [x["reason"] for x in result["rejections"]])
        self.assertIn("invalid_snapshot", [x["reason"] for x in result["rejections"]])

    def test_malformed_nested_evidence_is_rejected(self):
        for value in (None, [], "bad", {"quotes": "bad"}):
            with self.subTest(value=value):
                self.row["market_data"] = value
                self.assertRejected("missing_odds")
        self.row["market_data"] = {"quotes": [self.quote]}
        self.quote["market_identity"] = "bad"
        self.assertRejected("incomplete_market_identity")

    def test_unhashable_identity_and_team_values_are_rejected(self):
        self.row["market_scope"] = []
        self.assertRejected("incomplete_market_identity")
        self.row["market_scope"] = "team"
        self.row["home"] = []
        self.assertRejected("missing_teams")

    def test_artifact_with_foreign_run_metadata_is_rejected(self):
        self.runs[0]["artifacts"][0]["workflow_run"] = {"id": 12, "head_sha": SHA}
        self.assertRejected("artifact_run_mismatch", blocked=True)

    def test_conflicting_snapshot_copies_cannot_be_selected_by_input_order(self):
        other = copy.deepcopy(self.snapshots[0])
        other["background_candidates"][0]["final_assessment_pct"] = 99
        self.snapshots.append(other)
        self.assertRejected("conflicting_snapshot_copy")
        self.snapshots.reverse()
        self.assertRejected("conflicting_snapshot_copy")

    def test_same_fixture_with_conflicting_facts_across_runs_is_rejected(self):
        other = copy.deepcopy(self.snapshots[0])
        other["background_candidates"][0]["kickoff"] = "2026-11-01T21:00:00Z"
        self.snapshots.append(other)
        self.assertRejected("conflicting_fixture")

    def test_nonfinite_score_is_not_emitted_as_invalid_json(self):
        self.row["final_assessment_pct"] = float("nan")
        result = self.manifest()
        self.assertIsNone(result["records"][0]["final_assessment_pct"])
        json.dumps(result, allow_nan=False)

    def test_explicit_conflicting_quote_direction_rejected(self):
        self.quote["direction"] = "over"
        self.assertRejected("quote_market_mismatch")

    def test_timestamp_overflow_fails_closed(self):
        self.quote["provider_updated_at"] = "0001-01-01T00:00:00+01:00"
        self.assertRejected("invalid_timestamp")

    def test_naive_times_are_rejected_everywhere(self):
        for obj, key in ((self.runs[0], "run_started_at"), (self.runs[0], "updated_at"),
                         (self.snapshots[0], "generated_at_utc"), (self.row, "kickoff"),
                         (self.quote, "provider_updated_at")):
            with self.subTest(key=key):
                old = obj[key]
                obj[key] = "2026-11-01T09:00:00"
                self.assertEqual(self.manifest()["records"], [])
                obj[key] = old
        with self.assertRaises(ValueError):
            self.manifest(cutoff="2026-11-01T10:00:00")

    def test_invalid_report_date_is_explicit_error(self):
        for day in ("2026-11-1", "2026-02-30", "2026-11-01T00:00:00Z"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                self.manifest(day)


class WarsawDSTTests(unittest.TestCase):
    def manifest_for(self, day, started, captured, finished, kickoff, cutoff):
        runs, snapshots = evidence()
        runs[0].update(run_started_at=started, updated_at=finished)
        runs[0]["date_statuses"][0]["date"] = day
        snapshots[0].update(date=day, generated_at_utc=captured)
        row = snapshots[0]["background_candidates"][0]
        row["kickoff"] = kickoff
        row["market_data"]["quotes"][0]["provider_updated_at"] = captured
        return build_source_manifest(day, runs, snapshots, as_of=cutoff)

    def test_spring_gap_compares_real_instants(self):
        result = self.manifest_for("2026-03-29", "2026-03-29T00:00:00Z",
            "2026-03-29T01:30:00+01:00", "2026-03-29T01:00:00Z",
            "2026-03-29T03:15:00+02:00", "2026-03-29T01:05:00Z")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["kickoff"], "2026-03-29T01:15:00Z")

    def test_autumn_repeated_hour_distinguishes_offsets(self):
        result = self.manifest_for("2026-10-25", "2026-10-25T00:00:00Z",
            "2026-10-25T02:45:00+02:00", "2026-10-25T01:00:00Z",
            "2026-10-25T02:30:00+01:00", "2026-10-25T01:05:00Z")
        self.assertEqual(len(result["records"]), 1)
        # The same wall-clock kickoff in the earlier offset has already passed.
        result = self.manifest_for("2026-10-25", "2026-10-25T00:00:00Z",
            "2026-10-25T02:45:00+02:00", "2026-10-25T01:00:00Z",
            "2026-10-25T02:30:00+02:00", "2026-10-25T01:05:00Z")
        self.assertEqual(result["records"], [])

    def test_warsaw_midnight_on_both_sides_of_dst(self):
        for day, start, capture, finish, kickoff, cutoff in (
            ("2026-03-29", "2026-03-28T22:00:00Z", "2026-03-28T22:30:00Z",
             "2026-03-28T22:45:00Z", "2026-03-28T23:30:00Z", "2026-03-28T23:00:00Z"),
            ("2026-10-25", "2026-10-24T21:00:00Z", "2026-10-24T21:30:00Z",
             "2026-10-24T21:45:00Z", "2026-10-24T22:30:00Z", "2026-10-24T22:00:00Z"),
        ):
            with self.subTest(day=day):
                result = self.manifest_for(day, start, capture, finish, kickoff, cutoff)
                self.assertEqual(len(result["records"]), 1)

    def test_explicit_offsets_avoid_ambiguous_naive_dst_times(self):
        self.assertLess(instant("2026-10-25T02:45:00+02:00"),
                        instant("2026-10-25T02:30:00+01:00"))


class FoulsUnderTests(unittest.TestCase):
    def setUp(self):
        self.runs, self.snapshots = evidence()
        self.row = self.snapshots[0]["background_candidates"][0]
        self.quote = self.row["market_data"]["quotes"][0]

    def watch(self, cutoff=CUTOFF):
        return fouls_under_watchlist(DAY, self.runs, self.snapshots, as_of=cutoff)

    def test_score_boundary_and_status_never_play(self):
        for score, expected in ((0, BELOW_THRESHOLD), (66.999, BELOW_THRESHOLD),
                                (67, WATCH), (100, WATCH)):
            with self.subTest(score=score):
                self.row["final_assessment_pct"] = score
                result = self.watch()
                self.assertEqual(result["candidates"][0]["status"], expected)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["candidates"][0]["api_assessment"], str(score))
                self.assertNotIn("p_model", result["candidates"][0])
                self.assertNotIn("ev", result["candidates"][0])

    def test_odds_band_includes_both_boundaries(self):
        for odd, count in ((1.49, 0), (1.50, 1), (2.00, 1), (2.01, 0)):
            with self.subTest(odd=odd):
                self.quote["selected_odd"] = odd
                self.assertEqual(len(self.watch()["candidates"]), count)

    def test_only_under_fouls_and_90_minutes(self):
        for changes in ({"market": "corners"}, {"direction": "over"},
                        {"settlement_period": "first_half"}, {"settlement_period": "extra_time"}):
            with self.subTest(changes=changes):
                runs, snapshots = evidence()
                change_market(snapshots[0]["background_candidates"][0], **changes)
                result = fouls_under_watchlist(DAY, runs, snapshots, as_of=CUTOFF)
                self.assertEqual(result["status"], NO_CANDIDATES)

    def test_team_and_whole_match_are_separate_exact_identities(self):
        match = copy.deepcopy(self.row)
        change_market(match, market_scope="match", team_id=None, line=25.5)
        self.snapshots[0]["background_candidates"].append(match)
        result = self.watch()
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual({r["market_identity"]["market_scope"] for r in result["candidates"]},
                         {"team", "match"})

    def test_missing_or_invalid_api_score_means_no_verified_candidates(self):
        for score in (None, True, -1, 101, "NaN", float("inf"), "not a score"):
            with self.subTest(score=score):
                self.row["final_assessment_pct"] = score
                self.assertEqual(self.watch()["status"], NO_CANDIDATES)

    def test_observation_cannot_be_issued_at_or_after_kickoff(self):
        for cutoff in ("2026-11-01T20:00:00Z", "2026-11-01T21:00:00Z"):
            with self.subTest(cutoff=cutoff):
                self.assertEqual(self.watch(cutoff)["status"], NO_CANDIDATES)
        # Authentic historical freeze remains available solely for audit.
        manifest = build_source_manifest(DAY, self.runs, self.snapshots,
                                         as_of="2026-11-01T21:00:00Z")
        self.assertEqual(len(manifest["records"]), 1)

    def test_missing_source_or_price_produces_explicit_no_candidates(self):
        self.snapshots.clear()
        self.assertEqual(self.watch()["status"], NO_CANDIDATES)
        self.runs, self.snapshots = evidence()
        self.snapshots[0]["background_candidates"][0]["market_data"]["quotes"] = []
        self.assertEqual(self.watch()["status"], NO_CANDIDATES)

    def test_best_quote_is_selected_only_from_verified_band(self):
        for bookmaker, odd in (("HigherOutsideBand", 2.10), ("EligibleBook", 1.99)):
            quote = dict(copy.deepcopy(self.quote), bookmaker=bookmaker, selected_odd=odd)
            self.row["market_data"]["quotes"].append(quote)
        result = self.watch()["candidates"][0]
        self.assertEqual(result["quote"]["bookmaker"], "EligibleBook")
        self.assertEqual(result["quote"]["selected_odd"], "1.99")

    def test_missing_bookmaker_is_not_relabelled_sts_or_superbet(self):
        self.quote["bookmaker"] = None
        self.assertEqual(self.watch()["status"], NO_CANDIDATES)

    def test_filter_preserves_top_n_and_nested_source_inputs(self):
        self.snapshots[0].update(top_positions=[{"official": "unchanged"}], N=100)
        before = copy.deepcopy((self.runs, self.snapshots))
        result = self.watch()
        self.assertEqual((self.runs, self.snapshots), before)
        result["candidates"][0]["market_identity"]["line"] = "999"
        self.assertEqual((self.runs, self.snapshots), before)
        json.dumps(self.watch(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
