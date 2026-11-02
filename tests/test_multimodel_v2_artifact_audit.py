"""Offline ZIP corruption, timestamp, partial coverage and delivery checks."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from multimodel_v2.adapters import adapt_pitchapi, adapt_sheet, load_json, match_pitchapi, read_api_run
from multimodel_v2.artifact_audit import check_delivery, coverage, inspect_api_artifact, inspect_pitch_artifact, read_artifact
from multimodel_v2.report_pdf import generate_three_pdfs
from tests.test_multimodel_v2_adapters import ARCHIVE, PITCH, metadata_captures, sheet_capture


def zip_fixture(root, *, change=None, extras=()):
    # Original recorded repository files in an ephemeral unit-test ZIP.
    # Dynamic metadata identifies test bytes only; it is never audit evidence.
    stream=BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with zipfile.ZipFile(stream,"w") as z:
            for folder in ("v2","audit_input","pdf","multiday_status"):
                for path in sorted((ARCHIVE/folder).glob("*")):
                    if not path.is_file():continue
                    name=str(path.relative_to(ARCHIVE));raw=path.read_bytes()
                    if change:raw=change(name,raw)
                    if raw is not None:z.writestr(name,raw)
            for name,raw in extras:z.writestr(name,raw)
    path=Path(root)/"unit-test-only.zip";path.write_bytes(stream.getvalue())
    run=metadata_captures()[0]["payload"]
    meta={"id":1,"name":"api-market-multiday-experiment","expired":False,
          "size_in_bytes":path.stat().st_size,"digest":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),
          "workflow_run":{"id":run["id"],"head_sha":run["head_sha"]}}
    return path,run,meta


class ArtifactAuditTests(unittest.TestCase):
    def test_original_bytes_dates_and_partial_counts_remain_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root)
            result=inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")
            self.assertEqual([d["published_count"] for d in result["days"]],[7,22])
            self.assertEqual([d["candidate_count"] for d in result["days"]],[222,934])
            self.assertTrue(result["manifest"]["digest_verified"])
            self.assertEqual(result["evidence"]["snapshots"],[])
            self.assertTrue(all(c["field_comparison_passed"] for c in result["comparisons"]))
            self.assertTrue(all(not c["full_shadow_passed"] for c in result["comparisons"]))

    def test_zip_hash_size_run_or_expiry_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root)
            for field,value in [("digest","sha256:"+"0"*64),("size_in_bytes",0),("expired",True),("workflow_run",{"id":2,"head_sha":run["head_sha"]})]:
                with self.subTest(field=field):
                    bad=deepcopy(meta);bad[field]=value
                    with self.assertRaises(ValueError):read_artifact(path,run,bad)

    def test_traversal_member_is_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root,extras=[("../outside.json",b"{}")])
            with self.assertRaisesRegex(ValueError,"unsafe"):
                read_artifact(path,run,meta)
            self.assertFalse((Path(root).parent/"outside.json").exists())

    def test_duplicate_members_are_ambiguous_not_last_write_wins(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root,extras=[("multiday_status/2026-10-29.json",b"{}")])
            with self.assertRaisesRegex(ValueError,"duplicate"):
                read_artifact(path,run,meta)

    def test_missing_pdf_does_not_count_as_complete_delivery(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root,change=lambda n,b:None if n.endswith("2026-10-29.pdf") else b)
            r=inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")
            self.assertEqual(r["days"][0]["missing_members"],["pdf/API_MARKET_SCAN_2026-10-29.pdf"])
            self.assertIsNone(r["days"][0]["original_pdf"])
            self.assertEqual(r["days"][0]["status"]["status"],"ok")

    def test_payload_date_cannot_fill_a_different_filename(self):
        def change(name,raw):
            if name == "v2/API_MARKET_SCAN_PLAYABLE_2026-10-29.json":
                d=json.loads(raw);d["date"]="2026-10-30";return json.dumps(d).encode()
            return raw
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root,change=change)
            with self.assertRaisesRegex(ValueError,"date_mismatch"):
                inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")

    def test_post_kickoff_or_future_quote_is_reported_as_a_violation(self):
        def change(name,raw):
            if name == "v2/API_MARKET_SCAN_PLAYABLE_2026-10-29.json":
                d=json.loads(raw);r=d["positions"][0];r["best_quote"]["provider_updated_at"]=r["kickoff"];return json.dumps(d).encode()
            return raw
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root,change=change)
            r=inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")
            self.assertIn("quote_or_freeze_lookahead",[v["reason"] for v in r["days"][0]["published_time_violations"]])
            self.assertFalse(r["comparisons"][0]["full_shadow_passed"])

    def test_as_of_before_run_completion_cannot_validate_the_freeze(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root)
            r=inspect_api_artifact(read_artifact(path,run,meta),as_of=run["run_started_at"])
            self.assertIn("freeze_outside_run_or_as_of",[v["reason"] for v in r["days"][0]["published_time_violations"]])

    def test_two_artifact_dates_never_prove_d_plus_two(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root)
            r=inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")
            c=coverage("2026-10-29",r["days"],[])
            self.assertFalse(c["three_api_exports_present"])
            self.assertFalse(c["days"][2]["api_export_present"])
            self.assertFalse(c["full_multimodel_ready"])

    def test_historical_pitch_files_in_zip_are_not_new_snapshots_of_this_run(self):
        with tempfile.TemporaryDirectory() as root:
            stream=BytesIO()
            with zipfile.ZipFile(stream,"w") as z:z.writestr("data/pitchapi/prematch/2026-10-29.json",PITCH.read_bytes())
            path=Path(root)/"pitch-test.zip";path.write_bytes(stream.getvalue())
            run=metadata_captures()[0]["payload"];run["path"]=".github/workflows/pitchapi-prematch-context.yml"
            meta={"id":1,"name":"pitchapi-prematch-context","expired":False,"size_in_bytes":path.stat().st_size,
                  "digest":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),"workflow_run":{"id":run["id"],"head_sha":run["head_sha"]}}
            r=inspect_pitch_artifact(read_artifact(path,run,meta))
            self.assertFalse(r["days"][0]["captured_in_this_run"])
            self.assertEqual((r["days"][0]["rows"],r["days"][0]["strict_rows"]),(33,30))

    def test_wrong_workflow_cannot_masquerade_as_api_multiday(self):
        with tempfile.TemporaryDirectory() as root:
            path,run,meta=zip_fixture(root);run["path"]=".github/workflows/api-market-scan.yml"
            with self.assertRaisesRegex(ValueError,"wrong_api"):
                inspect_api_artifact(read_artifact(path,run,meta),as_of="2026-11-02T18:00:00Z")

    def test_template_id_is_retained_but_is_not_a_recorded_forecast_or_n(self):
        c=sheet_capture("kb21");c["payload"]["range"]["values"].append([118])
        r=adapt_sheet(c,"kb21")
        self.assertEqual(len(r["rows"]),2)
        self.assertEqual(r["recorded_selection_rows"],1)
        self.assertEqual(r["non_selection_rows"],1)
        self.assertEqual(r["rows"][1]["original"]["ID"],118)

    def test_pitch_context_after_original_cutoff_cannot_enter_frozen_replay(self):
        run,artifacts=metadata_captures()
        api=read_api_run(ARCHIVE,run_capture=run,artifacts_capture=artifacts)
        pitch=adapt_pitchapi(load_json(PITCH))
        row=next(r for r in api["bundles"][0]["rows"] if match_pitchapi(r,[pitch]))
        self.assertIsNone(match_pitchapi(row,[pitch],as_of="2026-10-28T20:00:00Z"))
        self.assertIsNotNone(match_pitchapi(row,[pitch],as_of=run["payload"]["updated_at"]))


class DeliveryAuditTests(unittest.TestCase):
    def test_pdf_reports_observed_partial_sources_without_claiming_complete_or_absent(self):
        from pypdf import PdfReader
        run,artifacts=metadata_captures()
        api=read_api_run(ARCHIVE,run_capture=run,artifacts_capture=artifacts)
        pitch=adapt_pitchapi(load_json(PITCH))
        with tempfile.TemporaryDirectory() as root:
            paths=generate_three_pdfs("2026-10-29",[],[],[],as_of="2026-11-02T18:00:00Z",output_dir=Path(root)/"pdfs",
                                     source_bundles=api["bundles"]+[pitch])
            first=PdfReader(paths[0]).pages[0].extract_text()
            self.assertIn("odczytano eksport (7 pozycji)",first)
            self.assertIn("30 rekordów kontekstu",first)
            self.assertIn("pokrycie niepełne",first)

    def test_valid_files_do_not_prove_recipient_delivery_or_complete_forecasts(self):
        with tempfile.TemporaryDirectory() as root:
            paths=generate_three_pdfs("2026-11-02",[],[],[],as_of="2026-11-02T18:00:00Z",output_dir=Path(root)/"pdfs")
            expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            r=check_delivery(paths[0].parent,"2026-11-02",expected)
            self.assertEqual(r["status"],"FILES_VERIFIED_AVAILABLE")
            self.assertEqual(len(r["files"]),3)
            self.assertFalse(r["recipient_receipt_confirmed"])
            self.assertFalse(r["complete_forecast_delivery"])

    def test_mismatched_pdf_digest_rejects_delivery_claim(self):
        with tempfile.TemporaryDirectory() as root:
            paths=generate_three_pdfs("2026-11-02",[],[],[],as_of="2026-11-02T18:00:00Z",output_dir=Path(root)/"pdfs")
            expected={p.name:"0"*64 for p in paths}
            with self.assertRaisesRegex(ValueError,"hash_mismatch"):
                check_delivery(paths[0].parent,"2026-11-02",expected)


if __name__ == "__main__":
    unittest.main()
