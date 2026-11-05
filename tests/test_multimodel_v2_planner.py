"""Three-day qualification fixtures only; no scans, forecasts or archive writes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from multimodel_v2.planner import plan_report_dates, report_deadline, scheduled_slot, validate_three_day_sources

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    # Typed test evidence, not historical source data or published picks.
    run = {"id": "planner-test-run", "path": ".github/workflows/api-market-multiday-experiment.yml",
           "head_sha": "a" * 40, "event": "schedule", "status": "completed", "conclusion": "success",
           "run_started_at": "2026-11-02T09:00:00Z", "updated_at": "2026-11-02T09:40:00Z"}
    jobs = {"total_count": 1, "jobs": [{"id": "planner-test-job", "run_id": run["id"],
             "steps": [{"name": "Independent scan per date", "conclusion": "success"}]}]}
    artifacts = {"artifacts": [{"name": "api-market-multiday-experiment", "expired": False,
        "digest": "sha256:" + "d" * 64,
        "workflow_run": {"id": run["id"], "head_sha": run["head_sha"]}}]}
    days = []
    for index, day in enumerate(plan_report_dates("2026-11-02")):
        identity = {"fixture_id": "unit-only-" + str(index), "market": "fouls", "market_scope": "team",
                    "team_id": "unit-only-team", "direction": "under", "line": "10.5",
                    "settlement_period": "regulation_time"}
        row = dict(identity, kickoff=day + "T17:00:00Z", quotes=[{
            "market_identity": deepcopy(identity), "bookmaker": "UNIT TEST BOOK",
            "selected_odd": "1.80", "provider_updated_at": "2026-11-02T09:15:00Z"}])
        days.append({"date": day, "file_date": day, "status": {"date": day, "status": "ok"},
                     "run_id": run["id"], "head_sha": run["head_sha"], "code_sha": "b" * 40,
                     "artifact_name": artifacts["artifacts"][0]["name"], "artifact_digest": artifacts["artifacts"][0]["digest"],
                     "digest_verified": True, "generated_at_utc": "2026-11-02T09:19:00Z",
                     "frozen_at_utc": "2026-11-02T09:20:00Z", "native_publication_id": "unit-native-" + day,
                     "full_pool_complete": True, "candidate_count": 1, "rows": [row]})
    return run, jobs, artifacts, days


class DatePlannerTests(unittest.TestCase):
    def test_three_calendar_days_across_year_boundary(self):
        self.assertEqual(plan_report_dates("2026-12-31"), ["2026-12-31", "2027-01-01", "2027-01-02"])

    def test_two_days_more_days_and_boolean_are_rejected(self):
        for days in (2, 4, 1, True, "3", 3.0):
            with self.subTest(days=days), self.assertRaisesRegex(ValueError, "exactly_three"):
                plan_report_dates("2026-11-02", days=days)

    def test_invalid_report_date_is_rejected(self):
        for day in ("2026-02-30", "2026-1-02", None):
            with self.subTest(day=day), self.assertRaises(ValueError):
                plan_report_dates(day)

    def test_warsaw_deadline_tracks_both_dst_boundaries(self):
        self.assertEqual(report_deadline("2026-03-28"), "2026-03-28T11:30:00+01:00")
        self.assertEqual(report_deadline("2026-03-29"), "2026-03-29T11:30:00+02:00")
        self.assertEqual(report_deadline("2026-10-24"), "2026-10-24T11:30:00+02:00")
        self.assertEqual(report_deadline("2026-10-25"), "2026-10-25T11:30:00+01:00")

    def test_nominal_slots_across_both_dst_boundaries(self):
        for day, active in [("2026-03-28", 9), ("2026-03-29", 8), ("2026-10-24", 8), ("2026-10-25", 9)]:
            for hour in (8, 9):
                with self.subTest(day=day, hour=hour):
                    slot = scheduled_slot(day, f"0 {hour} * * *")
                    self.assertEqual(slot["execute"], hour == active)
                    self.assertEqual(slot["status"], "ACTIVE" if hour == active else "OPPOSITE_DST_SLOT")

    def test_late_start_uses_nominal_slot_even_after_midnight(self):
        s = scheduled_slot("2026-10-24", "0 8 * * *", actual_started_at="2026-10-25T03:00:00Z")
        self.assertTrue(s["execute"])
        self.assertEqual(s["nominal_at_warsaw"], "2026-10-24T10:00:00+02:00")
        self.assertEqual(s["delay_seconds"], 19 * 3600)

    def test_schedule_date_and_slot_are_not_inferred_from_actual_start(self):
        self.assertEqual(scheduled_slot(None, "0 9 * * *", actual_started_at="2026-11-02T09:00:00Z")["status"], "UNVERIFIED")
        self.assertEqual(scheduled_slot("2026-11-02", "0 10 * * *")["status"], "UNVERIFIED")

    def test_manual_dispatch_has_no_fictional_nominal_schedule(self):
        s = scheduled_slot(None, None, event_name="workflow_dispatch")
        self.assertEqual(s["status"], "MANUAL")
        self.assertIsNone(s["nominal_at_utc"])


class ThreeDayQualificationTests(unittest.TestCase):
    def setUp(self):
        self.run, self.jobs, self.artifacts, self.days = fixture()

    def validate(self, **options):
        args = {"as_of": "2026-11-02T10:30:00Z", "scheduled_date": "2026-11-02",
                "cron_slot": "0 9 * * *", "checkout_sha": "b" * 40}
        args.update(options)
        return validate_three_day_sources("2026-11-02", self.run, self.jobs, self.artifacts, self.days, **args)

    def day_issues(self, result, index=0):
        return result["days"][index]["issues"]

    def test_complete_original_evidence_qualifies_without_writes_or_n(self):
        before = deepcopy((self.run, self.jobs, self.artifacts, self.days))
        r = self.validate()
        self.assertEqual(r["status"], "READY")
        self.assertTrue(r["source_ready"])
        self.assertTrue(r["deadline_met"])
        self.assertTrue(r["original_prematch_valid"])
        self.assertNotEqual(r["actual_checkout_sha"], r["workflow_head_sha"])
        self.assertEqual(r["paid_api_calls"], 0)
        self.assertFalse(r["register_writes"])
        self.assertEqual(r["n_effect"], 0)
        self.assertEqual(before, (self.run, self.jobs, self.artifacts, self.days))

    def test_missing_third_date_is_explicit_not_a_successful_two_day_report(self):
        self.days.pop()
        r = self.validate()
        self.assertEqual(r["status"], "SOURCE_BLOCKED")
        self.assertIn("missing_date", self.day_issues(r, 2))

    def test_duplicate_date_is_not_first_or_last_write_wins(self):
        self.days.append(deepcopy(self.days[0]))
        self.assertIn("duplicate_date_evidence", self.day_issues(self.validate()))

    def test_wrong_status_and_file_dates_cannot_fill_correct_date(self):
        self.days[0]["status"]["date"] = "2026-11-03"
        self.days[0]["file_date"] = "2026-11-03"
        issues = self.day_issues(self.validate())
        self.assertIn("status_date_mismatch", issues)
        self.assertIn("file_date_mismatch", issues)

    def test_per_date_error_is_blocked(self):
        self.days[1]["status"]["status"] = "error"
        self.assertIn("date_status_not_ok", self.day_issues(self.validate(), 1))

    def test_expired_missing_or_unbound_artifact_is_blocked(self):
        for change in (lambda a: a.update(expired=True), lambda a: a["workflow_run"].update(id="other-run"),
                       lambda a: a["workflow_run"].update(head_sha="c" * 40)):
            with self.subTest(change=change):
                self.artifacts = fixture()[2]
                change(self.artifacts["artifacts"][0])
                r = self.validate()
                self.assertFalse(r["source_ready"])
                self.assertIn("dated_artifact_missing", self.day_issues(r))

    def test_unrelated_run_outputs_do_not_replace_or_invalidate_bound_date_artifact(self):
        self.artifacts["artifacts"].append({"name": "unrelated-lab-output", "expired": True})
        self.assertTrue(self.validate()["source_ready"])

    def test_optional_full_source_capsule_has_explicit_allowed_artifact_name(self):
        self.artifacts["artifacts"][0]["name"] = "multimodel-v2-full-source"
        for day in self.days:
            day["artifact_name"] = "multimodel-v2-full-source"
        self.assertTrue(self.validate()["source_ready"])

    def test_digest_claim_without_matching_captured_bytes_metadata_is_blocked(self):
        for key, value in [("digest_verified", False), ("digest_verified", "true"), ("artifact_digest", "sha256:" + "e" * 64)]:
            with self.subTest(key=key, value=value):
                self.days = fixture()[3]
                self.days[0][key] = value
                self.assertIn("dated_artifact_digest_unverified", self.day_issues(self.validate()))

    def test_actual_checkout_not_workflow_head_is_required(self):
        self.days[0]["code_sha"] = self.run["head_sha"]
        self.assertIn("date_checkout_sha_unverified", self.day_issues(self.validate()))
        self.assertIn("actual_checkout_sha_missing", self.validate(checkout_sha=None)["issues"])

    def test_published_only_export_never_becomes_complete_pool(self):
        self.days[0].update(full_pool_complete=False, published_only=True)
        r = self.validate()
        self.assertIn("full_pool_not_complete", self.day_issues(r))
        self.assertFalse(r["source_ready"])

    def test_declared_background_count_without_saved_rows_is_blocked(self):
        self.days[0]["candidate_count"] = 1473
        self.assertIn("full_candidate_rows_missing_or_count_mismatch", self.day_issues(self.validate()))

    def test_native_publication_id_is_not_generated_from_digest(self):
        self.days[0].pop("native_publication_id")
        self.assertIn("native_publication_id_missing", self.day_issues(self.validate()))

    def test_independent_quote_identity_is_never_copied_from_candidate(self):
        self.days[0]["rows"][0]["quotes"][0].pop("market_identity")
        r = self.validate()
        self.assertFalse(r["source_ready"])
        self.assertTrue(any("incomplete_market_identity" in i for i in self.day_issues(r)))

    def test_explicit_observed_no_quote_does_not_create_fake_odds(self):
        self.days[0]["rows"][0]["quotes"] = []
        r = self.validate()
        self.assertTrue(r["source_ready"])
        self.assertEqual(self.days[0]["rows"][0]["quotes"], [])

    def test_missing_quote_observation_does_not_equal_observed_empty_array(self):
        self.days[0]["rows"][0].pop("quotes")
        self.assertIn("row:0:independent_quotes_missing", self.day_issues(self.validate()))

    def test_post_kickoff_freeze_is_rejected(self):
        self.days[0]["rows"][0]["kickoff"] = self.days[0]["frozen_at_utc"]
        self.assertIn("row:0:freeze_not_prematch", self.day_issues(self.validate()))

    def test_post_freeze_quote_and_exact_line_mismatch_are_rejected(self):
        quote = self.days[0]["rows"][0]["quotes"][0]
        quote["provider_updated_at"] = "2026-11-02T09:21:00Z"
        self.assertIn("row:0:quote_lookahead", self.day_issues(self.validate()))
        quote["provider_updated_at"] = "2026-11-02T09:15:00Z"
        quote["market_identity"]["line"] = "10.5000000001"
        self.assertIn("row:0:quote_market_mismatch", self.day_issues(self.validate()))

    def test_row_kickoff_warsaw_date_must_match_its_target(self):
        self.days[0]["rows"][0]["kickoff"] = "2026-11-02T23:30:00Z"
        self.assertIn("row:0:kickoff_date_mismatch", self.day_issues(self.validate()))

    def test_duplicate_exact_markets_do_not_inflate_pool(self):
        self.days[0]["rows"] *= 2
        self.days[0]["candidate_count"] = 2
        self.assertIn("duplicate_exact_market", self.day_issues(self.validate()))

    def test_same_fixture_different_markets_require_consistent_native_facts(self):
        for field,value in (("kickoff", "2026-11-02T18:00:00Z"), ("home", "CONTRADICTORY HOME"),
                            ("away", "CONTRADICTORY AWAY"), ("home_id", "other-home"),
                            ("away_id", "other-away")):
            with self.subTest(field=field):
                self.days=fixture()[3]
                first=self.days[0]["rows"][0]
                first.update(home="UNIT HOME",away="UNIT AWAY",home_id="unit-home",away_id="unit-away")
                other=deepcopy(first)
                other["line"]="11.5";other["quotes"][0]["market_identity"]["line"]="11.5"
                other[field]=value
                self.days[0]["rows"].append(other);self.days[0]["candidate_count"]=2
                self.assertIn("conflicting_fixture_facts",self.day_issues(self.validate()))

    def test_same_fixture_cannot_have_different_kickoff_dates_in_three_day_pool(self):
        original=self.days[0]["rows"][0]["fixture_id"]
        self.days[1]["rows"][0]["fixture_id"]=original
        self.days[1]["rows"][0]["quotes"][0]["market_identity"]["fixture_id"]=original
        result=self.validate()
        self.assertEqual([d["status"] for d in result["days"]],["READY"]*3)
        self.assertIn("conflicting_fixture_across_report_dates",result["issues"])
        self.assertFalse(result["source_ready"])

    def test_malformed_hash_keys_remain_structured_source_blockers(self):
        for change in ("date_list","artifact_name_list","metadata_name_dict","origin_list"):
            with self.subTest(change=change):
                self.run,self.jobs,self.artifacts,self.days=fixture()
                if change=="date_list":self.days[0]["date"]=[]
                elif change=="artifact_name_list":self.days[0]["artifact_name"]=[]
                elif change=="metadata_name_dict":self.artifacts["artifacts"][0]["name"]={}
                else:self.artifacts["artifacts"][0]["workflow_run"]=["invalid"]
                result=self.validate()
                self.assertEqual(result["status"],"SOURCE_BLOCKED")

    def test_late_source_can_remain_prematch_but_misses_original_deadline(self):
        self.run.update(run_started_at="2026-11-02T12:00:00Z", updated_at="2026-11-02T12:40:00Z")
        for d in self.days:
            d.update(generated_at_utc="2026-11-02T12:19:00Z", frozen_at_utc="2026-11-02T12:20:00Z")
        r = self.validate(as_of="2026-11-02T13:00:00Z")
        self.assertEqual(r["schedule"]["status"], "ACTIVE")
        self.assertTrue(r["original_prematch_valid"])
        self.assertFalse(r["deadline_met"])
        self.assertFalse(r["source_ready"])
        self.assertIn("report_deadline_missed", self.day_issues(r))

    def test_deadline_is_inclusive_at_1130_warsaw(self):
        self.run["updated_at"] = "2026-11-02T10:30:00Z"
        self.assertTrue(self.validate()["deadline_met"])
        self.run["updated_at"] = "2026-11-02T10:30:00.000001Z"
        self.assertFalse(self.validate(as_of="2026-11-02T10:31:00Z")["deadline_met"])

    def test_reading_an_original_after_the_match_never_changes_its_deadline(self):
        self.assertTrue(self.validate(as_of="2026-11-10T10:30:00Z")["source_ready"])

    def test_run_not_yet_available_at_as_of_is_rejected(self):
        self.assertIn("run_outside_as_of", self.validate(as_of="2026-11-02T09:30:00Z")["issues"])

    def test_absent_run_id_never_binds_missing_ids_together(self):
        self.run["id"] = None
        self.jobs["jobs"][0]["run_id"] = None
        self.artifacts["artifacts"][0]["workflow_run"]["id"] = None
        for d in self.days:
            d["run_id"] = None
        self.assertIn("run_identity_missing", self.validate()["issues"])

    def test_successful_job_with_skipped_scan_is_not_source_ready(self):
        self.jobs["jobs"][0]["steps"][0]["conclusion"] = "skipped"
        r = self.validate()
        self.assertFalse(r["source_ready"])
        self.assertIn("scan_not_executed_successfully", r["issues"])

    def test_opposite_dst_slot_is_skipped_only_with_actual_notice(self):
        self.jobs["jobs"][0]["steps"][0]["conclusion"] = "skipped"
        self.artifacts = {"artifacts": []}
        self.days = []
        log = "2026-11-02T09:01:00Z ##[notice]Opposite DST slot skipped by design: 0 8 * * *"
        r = self.validate(cron_slot="0 8 * * *", checkout_sha=None, job_log=log)
        self.assertEqual(r["status"], "SKIPPED")
        self.assertFalse(r["source_ready"])
        self.assertEqual(r["issues"], [])
        self.assertNotEqual(self.validate(cron_slot="0 8 * * *", job_log=log.replace("##[notice]", "echo ::notice::"))["status"], "SKIPPED")

    def test_scan_running_on_opposite_slot_is_not_an_intentional_skip(self):
        r = self.validate(cron_slot="0 8 * * *")
        self.assertEqual(r["status"], "SOURCE_BLOCKED")
        self.assertIn("scan_executed_on_opposite_dst_slot", r["issues"])

    def test_malformed_run_timestamps_remain_structured_blockers(self):
        self.run["run_started_at"] = "not-a-timestamp"
        r = self.validate()
        self.assertEqual(r["status"], "SOURCE_BLOCKED")
        self.assertIn("run_timestamps_missing_or_invalid", r["issues"])

    def test_existing_two_day_e2e_evidence_is_blocked_without_filling_1473_rows(self):
        actual = json.loads((ROOT / "docs/MULTIMODEL_V2_E2E_EVIDENCE_2026-11-02.json").read_text())
        run = deepcopy(actual["run_metadata"]["api"])
        jobs = fixture()[1]
        jobs["jobs"][0]["run_id"] = run["id"]
        artifact = {"name": "api-market-multiday-experiment", "expired": False,
                    "digest": "sha256:" + actual["api"]["manifest"]["zip_sha256"],
                    "workflow_run": {"id": run["id"], "head_sha": run["head_sha"]}}
        r = validate_three_day_sources("2026-11-01", run, jobs, {"artifacts": [artifact]}, actual["api"]["days"],
            as_of=actual["as_of"], event_name="schedule", scheduled_date="2026-11-01", cron_slot="0 9 * * *",
            checkout_sha=actual["workflow_code_lineage"]["api_experiment_checkout_sha"])
        self.assertEqual(r["status"], "SOURCE_BLOCKED")
        self.assertFalse(r["deadline_met"])
        self.assertIn("missing_date", self.day_issues(r, 2))
        self.assertIn("full_candidate_rows_missing_or_count_mismatch", self.day_issues(r))
        self.assertEqual(actual["api"]["days"][0]["candidate_count"], 1473)


if __name__ == "__main__":
    unittest.main()
