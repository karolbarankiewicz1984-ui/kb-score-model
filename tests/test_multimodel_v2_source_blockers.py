"""Recovery preserves recorded values and cannot bypass source completeness."""
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from multimodel_v2.adapters import adapt_api, adapt_api_overlay, api_evidence, load_json
from multimodel_v2.audit import freeze_reference
from multimodel_v2.git_publication import normalized_payload, read_git_publication, validate_receipt
from multimodel_v2.history import compare_revisions, recover_revision
from multimodel_v2.report_pdf import generate_three_pdfs, validate_pdf_bundle
from multimodel_v2.shadow import compare_api, run_shadow
from multimodel_v2.source_audit import classify_run, recovery_policy
from multimodel_v2.source_manifest import build_source_manifest
from tests.test_multimodel_v2_adapters import ARCHIVE, PITCH, PREDICTION, ROOT, capture, metadata_captures, sheet_capture

AUDIT = ROOT / "docs/MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.json"


def proof():
    return json.loads(AUDIT.read_text())["api_git_publication"]


def revision(system="kb21", *, version="2", modified="2026-10-14T09:30:00Z", rows=None):
    # Only parser fixtures, never persisted as source forecasts or registers.
    headers = (["ID", "Data analizy", "Data wydarzenia", "Wydarzenie", "Rynek", "Typ", "P(model)", "KB Score", "Decyzja", "Kurs", "Uwagi"]
               if system == "kb21" else ["Date", "Analysis Time", "Event", "Market", "Pick", "Category", "Odds 11:30"])
    default = (["7", "2026-10-01", "2026-10-06", "PARSER EVENT", "SOURCE MARKET", "SOURCE PICK", "0.57", "80", "SOURCE STATUS", "2.00", "recorded\nmultiline note"]
               if system == "kb21" else ["2026-10-14 00:00:00", "10:30:00", "PARSER EVENT", "SOURCE MARKET", "SOURCE PICK", "SOURCE STATUS", "2.00"])
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["\f", *headers])
    for i, row in enumerate(rows if rows is not None else [default]):
        writer.writerow([str(i), *row])
    writer.writerow(["\f", "other tab"])
    writer.writerow(["0", "not a selection"])
    return capture({"fileId": "parser-only-sheet", "revisionId": version, "revisionModifiedTime": modified,
                    "content": stream.getvalue(), "url": "https://docs.google.com/spreadsheets/d/parser-only-sheet/edit"})


def index(*captures):
    return {"fileId": "parser-only-sheet", "revisions": [{"id": c["payload"]["revisionId"],
        "modifiedTime": c["payload"]["revisionModifiedTime"]} for c in captures]}


class RecordedHistoryTests(unittest.TestCase):
    def test_multiline_csv_preserves_original_id_and_values(self):
        c = revision(); old = deepcopy(c)
        result = recover_revision(c, index(c), "kb21")
        row = result["rows"][0]
        self.assertEqual((row["export_index"], row["source_record_key"]), (0, ["7"]))
        self.assertEqual(row["original"]["P(model)"], "0.57")
        self.assertEqual(row["original"]["Uwagi"], "recorded\nmultiline note")
        self.assertEqual(row["time_class"], "REVISION_AFTER_EVENT_DATE")
        self.assertFalse(row["eligible_as_new_prematch"])
        self.assertIsNone(row["fixture_id"])
        self.assertIsNone(row["forecast_frozen_at"])
        self.assertEqual(result["n_effect"], 0)
        self.assertEqual(c, old)

    def test_consensus_midnight_rendering_is_calendar_not_kickoff(self):
        c = revision("consensus")
        row = recover_revision(c, index(c), "consensus")["rows"][0]
        self.assertEqual(row["date"], "2026-10-14")
        self.assertEqual(row["time_class"], "SOURCE_DATE_NOT_VERIFIED_EVENT_DATE")
        self.assertIsNone(row["forecast_frozen_at"])
        self.assertFalse(row["eligible_as_new_prematch"])

    def test_same_day_revision_never_infers_pre_kickoff(self):
        c = revision(modified="2026-10-06T06:00:00Z")
        row = recover_revision(c, index(c), "kb21")["rows"][0]
        self.assertEqual(row["time_class"], "SAME_EVENT_DATE_KICKOFF_UNKNOWN")
        self.assertFalse(row["eligible_as_new_prematch"])

    def test_before_event_revision_still_requires_exact_freeze_evidence(self):
        c = revision(modified="2026-10-05T06:00:00Z")
        row = recover_revision(c, index(c), "kb21")["rows"][0]
        self.assertEqual(row["time_class"], "REVISION_BEFORE_EVENT_DATE")
        self.assertFalse(row["eligible_as_new_prematch"])

    def test_foreign_file_revision_or_timestamp_rejected(self):
        c = revision()
        for key, value in [("fileId", "another-file"), ("revisionId", "999"), ("revisionModifiedTime", "2026-10-15T09:30:00Z")]:
            with self.subTest(key=key):
                bad = deepcopy(c); bad["payload"][key] = value
                with self.assertRaises(ValueError):
                    recover_revision(bad, index(c), "kb21")

    def test_missing_table_rejected(self):
        c = revision(); c["payload"]["content"] = "other,columns\n1,2\n"
        with self.assertRaisesRegex(ValueError, "missing_or_ambiguous"):
            recover_revision(c, index(c), "kb21")

    def test_duplicate_tables_rejected_instead_of_selecting_favorable_one(self):
        c = revision(); c["payload"]["content"] *= 2
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            recover_revision(c, index(c), "kb21")

    def test_connector_index_must_be_monotonic(self):
        c = revision(); c["payload"]["content"] = c["payload"]["content"].replace("0,7,", "oops,7,")
        with self.assertRaisesRegex(ValueError, "export_index"):
            recover_revision(c, index(c), "kb21")

    def test_placeholder_id_does_not_create_selection(self):
        c = revision(rows=[["118", "", "", "", "", "", "", "", "", "", ""]])
        r = recover_revision(c, index(c), "kb21")
        self.assertEqual(r["rows"], [])
        self.assertEqual(r["non_selection_rows"], 1)

    def test_result_change_and_numeric_formatting_reported_separately(self):
        a = revision(version="1", modified="2026-10-12T09:30:00Z")
        b = revision()
        b["payload"]["content"] = b["payload"]["content"].replace("2.00", "2.0").replace("SOURCE STATUS", "RECORDED UPDATE")
        result = compare_revisions(recover_revision(a, index(a,b), "kb21"), recover_revision(b,index(a,b),"kb21"))
        self.assertEqual(result["changes"][0]["changed_fields"], ["Decyzja"])
        self.assertEqual(result["changes"][0]["numeric_format_only"], ["Kurs"])
        self.assertFalse(result["earliest_original_forecast_inferred"])
        self.assertEqual(result["n_effect"], 0)

    def test_duplicate_native_ids_are_not_resolved_by_row_order(self):
        a, b = revision(version="1", modified="2026-10-12T09:30:00Z"), revision()
        ra, rb = recover_revision(a,index(a,b),"kb21"),recover_revision(b,index(a,b),"kb21")
        rb["rows"].append(deepcopy(rb["rows"][0]))
        result = compare_revisions(ra,rb)
        self.assertEqual(result["ambiguous_record_keys"], [["7"]])
        self.assertEqual(result["changes"], [])

    def test_revision_comparison_order_and_source_guard(self):
        c = revision(); r = recover_revision(c,index(c),"kb21")
        with self.assertRaisesRegex(ValueError,"order"):
            compare_revisions(r,r)
        bad = deepcopy(r);bad["file_id"] = "other"
        with self.assertRaisesRegex(ValueError,"different_history"):
            compare_revisions(r,bad)


class GitPublicationTests(unittest.TestCase):
    def setUp(self):
        p = proof();self.run,self.receipt=p["run"],p["receipt"]
        self.capture=load_json(PREDICTION);self.bundle=adapt_api(self.capture)

    def evidence(self):
        return api_evidence(self.bundle,self.run,git_receipt=self.receipt)

    def test_actual_git_publication_recovers_source_without_fake_artifact(self):
        e = self.evidence()
        m = build_source_manifest("2026-10-29",e["runs"],e["snapshots"],as_of=self.run["updated_at"])
        self.assertEqual(m["status"],"covered")
        self.assertEqual(m["sources"][0]["source_kind"],"git_publication")
        self.assertEqual(m["sources"][0]["artifact_names"],[])
        self.assertIsNone(m["sources"][0]["snapshot_artifact"])
        self.assertEqual(m["records"],[])
        self.assertNotIn("no_verified_run",[r["reason"] for r in m["rejections"]])

    def test_actual_shadow_remains_blocked_with_top_retained_and_no_roi(self):
        result=compare_api(self.capture,self.bundle,evidence=self.evidence(),as_of=self.run["updated_at"])
        self.assertTrue(result["field_comparison_passed"])
        self.assertEqual(result["original_top_rows"],51)
        self.assertEqual(result["strict_v2_audits"]["original_top"]["positions"],51)
        self.assertEqual(result["strict_v2_audits"]["original_top"]["status"],"incomplete")
        self.assertIsNone(result["strict_v2_audits"]["original_top"]["roi_pct"])
        self.assertFalse(result["full_shadow_passed"])

    def test_native_id_is_preserved_in_freeze_reference(self):
        snapshot=self.evidence()["snapshots"][0];ref=freeze_reference(snapshot)
        self.assertEqual(ref["id"],self.capture["payload"]["publication"]["id"])
        self.assertEqual(ref["source_ref"],self.receipt["source_ref"])
        self.assertNotIn("artifact_name",ref)

    def test_unrelated_run_and_failed_run_cannot_bind(self):
        for key,value in [("id",40906734194),("head_sha","b"*40),("conclusion","failure")]:
            with self.subTest(key=key):
                bad=deepcopy(self.run);bad[key]=value
                with self.assertRaisesRegex(ValueError,"binding_mismatch"):
                    api_evidence(self.bundle,bad,git_receipt=self.receipt)

    def test_missing_or_echoed_runtime_proof_is_rejected(self):
        for replacement in [[],["2026-10-29T16:19:16Z echo " + s.split(" ",1)[1] for s in self.receipt["proof_lines"]]]:
            bad=deepcopy(self.receipt);bad["proof_lines"]=replacement
            with self.assertRaisesRegex(ValueError,"runtime_proof"):
                api_evidence(self.bundle,self.run,git_receipt=bad)

    def test_skipped_publication_step_cannot_bind(self):
        bad=deepcopy(self.receipt)
        for s in bad["job"]["steps"]:
            if s["name"] == "Freeze and publish unlimited API ranking":s["conclusion"]="skipped"
        with self.assertRaisesRegex(ValueError,"step_not_successful"):
            api_evidence(self.bundle,self.run,git_receipt=bad)

    def test_hash_or_path_or_time_tampering_rejected(self):
        for key,value in [("capture_sha256","b"*64),("path","data/other.json"),("committed_at","2026-10-29T17:00:00Z")]:
            with self.subTest(key=key):
                bad=deepcopy(self.receipt);bad[key]=value
                with self.assertRaises(ValueError):api_evidence(self.bundle,self.run,git_receipt=bad)

    def test_snapshot_price_mutation_cannot_bypass_receipt(self):
        e=self.evidence();e["snapshots"][0]["background_candidates"][0]["market_data"]["quotes"][0]["selected_odd"]=9.99
        m=build_source_manifest("2026-10-29",e["runs"],e["snapshots"],as_of=self.run["updated_at"])
        self.assertEqual(m["status"],"blocked")
        self.assertIn("git_snapshot_payload_mismatch",[r["reason"] for r in m["rejections"]])

    def test_historical_git_source_cannot_cover_november(self):
        e=self.evidence()
        m=build_source_manifest("2026-11-01",e["runs"],e["snapshots"],as_of="2026-11-01T15:05:48Z")
        self.assertEqual(m["status"],"blocked")
        self.assertEqual(m["records"],[])

    def test_git_blob_is_read_only_and_mismatch_is_rejected(self):
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        bad=deepcopy(self.capture);bad["capture_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"git_blob_capture_mismatch"):
            read_git_publication(ROOT,bad,self.run,self.receipt["job"],"",head)

    def test_full_shadow_uses_bound_historical_lineage_but_never_passes_missing_current_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run,artifacts=metadata_captures()
            inputs={"run":run["payload"],"artifacts":artifacts["payload"],
                    "kb":sheet_capture("kb21")["payload"],"consensus":sheet_capture("consensus")["payload"],"proof":proof()}
            for name,payload in inputs.items():(root/f"{name}.json").write_text(json.dumps(payload))
            report,_,_=run_shadow(ARCHIVE,root/"run.json",root/"artifacts.json",root/"kb.json",root/"consensus.json",[PITCH],
                start_date="2026-11-01",as_of="2026-11-01T15:05:48Z",api_predictions=[PREDICTION],api_git_proofs=[root/"proof.json"])
            full=report["comparisons"][-1]
            self.assertEqual(full["run_binding"]["status"],"verified")
            self.assertNotIn("run_binding_missing",full["blockers"])
            self.assertFalse(report["full_parallel_1_to_1_complete"])
            self.assertFalse(report["readiness"]["can_complete_three_real_data_reports"])


class SourceDiagnosticTests(unittest.TestCase):
    def setUp(self):
        a=json.loads(AUDIT.read_text());self.skip=a["api_runs"]["skipped"];self.failure=a["api_runs"]["failure"]

    def classify(self, observed, log=""):
        return classify_run(observed["run"],observed["jobs"],observed["artifacts"],scan_step="Independent scan per date",job_log=log)

    def test_successful_dst_guard_is_not_a_completed_scan(self):
        result=self.classify(self.skip,self.skip["runtime_notice"])
        self.assertEqual(result["reason"],"scan_skipped_no_new_source")
        self.assertEqual(result["status"],"SKIPPED")
        self.assertFalse(result["source_eligible"])
        self.assertEqual(result["cause"],"opposite_dst_slot_confirmed")
        self.assertFalse(result["scan_executed_successfully"])

    def test_echo_of_guard_is_not_confirmation_of_actual_branch(self):
        result=self.classify(self.skip,self.skip["runtime_notice"].replace("##[notice]","echo ::notice::"))
        self.assertEqual(result["cause"],"skip_cause_unconfirmed")

    def test_unavailable_failure_logs_do_not_prove_billing_or_api_quota(self):
        result=self.classify(self.failure)
        self.assertEqual(result["reason"],"failed_before_recorded_steps")
        self.assertEqual(result["cause"],"unconfirmed_requires_original_annotations_or_logs")

    def test_cross_run_or_truncated_job_evidence_rejected(self):
        for key,value in [("total_count",2),("jobs",[])]:
            bad=deepcopy(self.skip);bad["jobs"][key]=value
            with self.assertRaises(ValueError):self.classify(bad)

    def test_actual_git_persisted_run_requires_no_upload_artifact(self):
        p=proof()
        result=classify_run(p["run"],{"jobs":[p["receipt"]["job"]]}, {"artifacts":[]},
                            scan_step="Freeze and publish unlimited API ranking",git_receipt=p["receipt"])
        self.assertEqual(result["status"],"RECORDED_SOURCE_LINKED")
        self.assertEqual(result["artifact_count"],0)


class RawOverlayTests(unittest.TestCase):
    def test_existing_raw_snapshot_is_readable_but_never_native_top_or_odds(self):
        source=load_json(ROOT / "data/api_football/market_snapshots/2026-10-29/161914.json")
        before=deepcopy(source)
        result=adapt_api_overlay(source)
        self.assertEqual(result["system"],"api_market_overlay")
        self.assertEqual(len(result["rows"]),len(source["payload"]["items"]))
        self.assertTrue(result["rows"])
        self.assertEqual(result["verified_rows"],0)
        self.assertIsNone(result["native_top"])
        self.assertFalse(result["background_complete"])
        for old,new in zip(source["payload"]["items"],result["rows"]):
            self.assertEqual(old,new["original"])
            self.assertIsNone(new["odds_original"])
            self.assertIsNone(new["score"])
        self.assertEqual(source,before)

    def test_raw_snapshot_cannot_enter_native_forecast_adapter(self):
        source=load_json(ROOT / "data/api_football/market_snapshots/2026-10-29/161914.json")
        with self.assertRaisesRegex(ValueError,"unsupported_api_schema"):
            adapt_api(source)
        with self.assertRaisesRegex(ValueError,"unsupported_api_overlay"):
            adapt_api_overlay(load_json(PREDICTION))

    def test_pdf_distinguishes_git_source_and_overlay_from_upload_and_forecast(self):
        from pypdf import PdfReader
        p=proof();bundle=adapt_api(load_json(PREDICTION))
        e=api_evidence(bundle,p["run"],git_receipt=p["receipt"])
        overlay=adapt_api_overlay(load_json(ROOT / "data/api_football/market_snapshots/2026-10-29/161914.json"))
        with tempfile.TemporaryDirectory() as folder:
            paths=generate_three_pdfs("2026-10-29",e["runs"],e["snapshots"],[],as_of="2026-11-01T15:26:00Z",
                                     output_dir=Path(folder)/"pdfs",source_bundles=[overlay])
            self.assertEqual(len(validate_pdf_bundle(paths[0].parent,"2026-10-29")),3)
            text="\n".join(page.extract_text() for page in PdfReader(paths[0]).pages)
            self.assertIn("Publikacja Git:",text)
            self.assertIn("surową nakładkę",text)
            self.assertNotIn("Artefakt: None",text)


class RecoveryPolicyTests(unittest.TestCase):
    def policy(self, **changes):
        args=dict(as_of="2026-11-01T15:05:48Z",report_freeze="2026-11-01T11:30:00+01:00",
                  evidence_kind="forecast",original_available=False)
        args.update(changes);return recovery_policy(**args)

    def test_metadata_can_be_read_now_without_forecast_backfill(self):
        r=self.policy(evidence_kind="metadata")
        self.assertEqual(r["status"],"SAFE_READ_METADATA")
        self.assertFalse(r["eligible_for_original_freeze"])

    def test_missing_source_after_daily_freeze_cannot_be_backdated(self):
        self.assertEqual(self.policy()["status"],"FORBIDDEN_RETROSPECTIVE_PREMATCH")

    def test_future_days_wait_for_real_prospective_sources(self):
        for day in ("02","03"):
            self.assertEqual(self.policy(report_freeze=f"2026-11-{day}T11:30:00+01:00")["status"],"WAIT_FOR_PROSPECTIVE_ORIGINAL_SOURCE")

    def test_recorded_original_can_be_read_after_kickoff_without_new_prediction(self):
        r=self.policy(original_available=True,original_captured_at="2026-11-01T10:00:00+01:00",kickoff="2026-11-01T12:00:00+01:00")
        self.assertTrue(r["eligible_for_original_freeze"])
        self.assertTrue(r["other_provenance_checks_required"])
        self.assertTrue(r["read_existing_only"])

    def test_later_quote_is_only_later_edition(self):
        r=self.policy(evidence_kind="quote",original_available=True,original_captured_at="2026-11-01T13:00:00+01:00",kickoff="2026-11-01T18:00:00+01:00")
        self.assertEqual(r["status"],"LATER_EDITION_ONLY")
        self.assertFalse(r["eligible_for_original_freeze"])

    def test_after_kickoff_observation_is_historical_only(self):
        r=self.policy(original_available=True,original_captured_at="2026-11-01T13:00:00+01:00",kickoff="2026-11-01T12:00:00+01:00")
        self.assertEqual(r["status"],"HISTORICAL_ONLY_AFTER_KICKOFF")

    def test_unknown_source_time_never_infers_freeze(self):
        self.assertEqual(self.policy(original_available=True)["status"],"HISTORICAL_ONLY_UNVERIFIED_TIMING")

    def test_results_never_become_prematch_evidence(self):
        self.assertEqual(self.policy(evidence_kind="result")["status"],"HISTORICAL_SETTLEMENT_ONLY")

    def test_paid_scan_is_forbidden_even_for_future_date(self):
        self.assertEqual(self.policy(paid_scan=True,report_freeze="2026-11-03T11:30:00+01:00")["status"],"FORBIDDEN_PAID_SCAN")

    def test_future_capture_is_not_an_available_original(self):
        with self.assertRaisesRegex(ValueError,"not_yet_available"):
            self.policy(original_available=True,original_captured_at="2026-11-02T10:00:00+01:00",kickoff="2026-11-02T18:00:00+01:00")


if __name__ == "__main__":
    unittest.main()
