"""Offline rollout tests. Generated provider inputs are explicitly UNIT TESTS.

The native CODE fixture is byte-identical to experiment SHA in its manifest;
test inputs never enter repository archives or reports. Network is forbidden.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from multimodel_v2.bundle import inspect_bundle, inspect_uploaded_bundle, prepare_upload, STAGES
from multimodel_v2.capture import capture_provider_response, read_provider_capture
from multimodel_v2.producer import NativeProducerRecorder, digest, native_environment, immutable_json
from multimodel_v2.publication_bridge import ForwardPublicationObserver
from multimodel_v2.outcome_bridge import build_linked_native_outcomes
from multimodel_v2.settlement import build_native_settlements
from multimodel_v2.report_pdf import generate_three_pdfs, validate_pdf_bundle
from multimodel_v2.source_manifest import instant
from tests.test_multimodel_v2_formal_freeze import formal_payload
from tests.test_multimodel_v2_settlement import native_snapshot

FIXTURE = Path(__file__).parent / "fixtures/multimodel_v2/native_experiment"
MANIFEST = json.loads((FIXTURE / "source_manifest.json").read_text())
NATIVE = MANIFEST["native_sha"]
RECORDER = "c" * 40
SOURCE = {"run_id": 123, "workflow_head_sha": "b" * 40, "code_checkout_sha": NATIVE,
          "workflow_path": ".github/workflows/api-market-multiday-experiment.yml"}
NOW = "2030-01-01T09:00:00+00:00"
DAYS = ["2030-01-01", "2030-01-02", "2030-01-03"]


class FixedDatetime(datetime):
    current = instant(NOW)
    @classmethod
    def now(cls, tz=None):
        value = cls.current
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)


def test_fixture(day):
    return {"fixture": {"id": 100 + int(day[-2:]), "date": day + "T20:00:00+00:00", "status": {"short": "NS"}},
            "league": {"country": "England", "name": "Premier League"},
            "teams": {"home": {"id": 10, "name": "UNIT TEST HOME"}, "away": {"id": 20, "name": "UNIT TEST AWAY"}}}


def test_history():
    return [{"fixture_id": i, "date": f"2029-12-{i:02d}T18:00:00Z", "home_id": 10, "away_id": 20,
             "goals": {"home": 4, "away": 4}, "league": "Premier League", "country": "England",
             "teams": [{"team_id": t, "shots": 20, "fouls": 10} for t in (10, 20)]} for i in range(1, 21)]


def test_odds():
    values = [{"value": f"{direction} {i + .5}", "odd": "1.8"} for i in range(24) for direction in ("Over", "Under")]
    return [{"bookmakers": [{"id": 1, "name": "UNIT TEST BOOK", "bets": [
        {"id": 221, "name": "Shots. Home Total", "values": values},
        {"id": 5, "name": "Goals Over/Under", "values": values}]}]}]


class ProducerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.offline = patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.offline.start()
        self.addCleanup(self.offline.stop)
        connect = patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        connect.start()
        self.addCleanup(connect.stop)

    def native_root(self, name):
        root = self.base / name
        shutil.copytree(FIXTURE, root)
        path = root / "data/api_football/daily/2029-12-31.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"rows": test_history()}))
        return root

    def pipeline(self, name, enabled):
        native, output, calls = self.native_root(name), self.base / (name + "-capture"), []
        FixedDatetime.current = instant(NOW)
        with patch("datetime.datetime", FixedDatetime), patch.dict(os.environ, {"GITHUB_SHA": SOURCE["workflow_head_sha"]}), redirect_stdout(io.StringIO()):
            for day in DAYS:
                for stage in STAGES:
                    if stage == "status":
                        # The existing workflow writes this original file after
                        # all native commands; recorder only copies its bytes.
                        path = native / f"reports/api_market_scan/multiday_status/{day}.json"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps({"date": day, "status": "ok"}))
                    with native_environment(native, day):
                        scan = importlib.import_module("api_market_scan")
                        def get(base, key, endpoint, **params):
                            FixedDatetime.current += timedelta(seconds=1)
                            calls.append((endpoint, deepcopy(params)))
                            response = [test_fixture(day)] if endpoint == "fixtures" else test_odds() if endpoint == "odds" else []
                            return {"errors": [], "paging": {"current": 1, "total": 1}, "parameters": deepcopy(params),
                                    "response": response}, {"x-apisports-key": "UNIT_TEST_SECRET"}
                        scan.API_CLIENT.get = get
                        recorder = NativeProducerRecorder(native, output, SOURCE, recorder_sha=RECORDER,
                            enabled=enabled, clock=lambda: FixedDatetime.now(timezone.utc))
                        recorder.run_stage(stage, day)
                        self.assertEqual(recorder.errors, [], (stage, recorder.errors))
        return native, output, calls

    def inspect(self, root, **kwargs):
        return inspect_bundle(root, start_date=DAYS[0], as_of="2030-01-01T10:00:00Z", source=SOURCE, recorder_sha=RECORDER, **kwargs)

    def test_native_code_fixture_has_exact_source_hashes_and_blob_ids(self):
        for entry in MANIFEST["files"]:
            content = (FIXTURE / entry["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            self.assertEqual(hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest(), entry["blob_oid"])

    def test_three_day_native_pipeline_1to1_no_extra_calls_top_freeze_n_and_consumer(self):
        baseline, no_output, calls = self.pipeline("baseline", False)
        observed, output, observed_calls = self.pipeline("observed", True)
        self.assertFalse(no_output.exists())
        self.assertEqual(calls, observed_calls)
        for day in DAYS:
            for path in (f"data/api_football/market_scan/{day}.json", f"reports/api_market_scan/audit_input/{day}.json",
                         f"reports/api_market_scan/v2/API_MARKET_SCAN_PLAYABLE_{day}.json"):
                left, right = json.loads((baseline / path).read_text()), json.loads((observed / path).read_text())
                self.assertEqual(left, right, path)
            payload = json.loads((observed / f"data/api_football/market_scan/{day}.json").read_text())
            capsule = json.loads(next((output / "full_pool" / day).glob("*.json")).read_text())
            self.assertGreater(len(payload["background_candidates"]), 0)
            self.assertEqual(capsule["native_payload"], payload)
            self.assertGreater(capsule["counts"]["native_score_bands"]["below_67"], 0)
            self.assertEqual(capsule["n_effect"], 0)
            self.assertIn("native_publication_checkout_mismatch", capsule["verification"]["blockers"])
            self.assertTrue((observed / f"reports/api_market_scan/pdf/API_MARKET_SCAN_{day}.pdf").read_bytes().startswith(b"%PDF"))
        result = self.inspect(output)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["capture_complete"])
        self.assertFalse(result["source_ready"])
        self.assertFalse(result["full_shadow_passed"])
        self.assertNotIn("UNIT_TEST_SECRET", "".join(p.read_text() for p in output.rglob("*.json")))
        upload = prepare_upload(output, enabled=True, start_date=DAYS[0], as_of="2030-01-01T10:00:00Z",
                                source=SOURCE, recorder_sha=RECORDER)
        self.assertTrue(upload["upload"])
        self.assertFalse(upload["source_ready"])
        # Upload bytes are consumed by the existing authenticated ZIP reader
        # and strict repair qualification, without mocking either validator.
        import zipfile
        from multimodel_v2.artifact_audit import read_artifact
        from multimodel_v2.repair_pipeline import assess_repair_sources
        archive_path = self.base / "capture.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in output.rglob("*"):
                if path.is_file():
                    archive.write(path, str(path.relative_to(output)))
        run = {"id": SOURCE["run_id"], "head_sha": SOURCE["workflow_head_sha"], "path": SOURCE["workflow_path"],
               "status": "completed", "conclusion": "success", "event": "workflow_dispatch",
               "run_started_at": "2030-01-01T09:00:00Z", "updated_at": "2030-01-01T10:00:00Z"}
        artifact = {"id": 123, "name": "multimodel-v2-full-source", "expired": False,
                    "size_in_bytes": archive_path.stat().st_size,
                    "digest": "sha256:" + hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                    "workflow_run": {"id": run["id"], "head_sha": run["head_sha"]}}
        archive = read_artifact(archive_path, run, artifact)
        uploaded = inspect_uploaded_bundle(archive, start_date=DAYS[0], as_of="2030-01-01T10:00:00Z",
                                           source=SOURCE, recorder_sha=RECORDER)
        self.assertEqual(uploaded, result)
        wrong_revision = inspect_uploaded_bundle(archive, start_date=DAYS[0], as_of="2030-01-01T10:00:00Z",
                                           source=SOURCE, recorder_sha="d" * 40)
        self.assertFalse(wrong_revision["capture_complete"])
        qualified = assess_repair_sources(DAYS[0], run, {"jobs": [{"run_id": run["id"], "steps": [
            {"name": "Independent scan per date", "conclusion": "success"}]}]}, [archive],
            {"kb21": [], "consensus": []}, [], as_of="2030-01-01T10:00:00Z", checkout_sha=NATIVE)
        self.assertEqual(qualified["status"], "SOURCE_BLOCKED")
        self.assertFalse(qualified["ready_for_parallel_1_to_1"])
        self.assertFalse(qualified["full_shadow_passed"])
        # A5 reporting remains honest when native quote identities are absent.
        paths = generate_three_pdfs(DAYS[0], [], [], [], as_of=NOW, output_dir=self.base / "a5-missing")
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(v["validated"] for v in validate_pdf_bundle(paths[0].parent, DAYS[0])))

    def test_bundle_partial_empty_disabled_and_revision_mismatch(self):
        self.assertEqual(prepare_upload(self.base / "missing")["status"], "DISABLED")
        self.assertEqual(self.inspect(self.base / "missing")["status"], "SOURCE_BLOCKED")
        _, output, _ = self.pipeline("partial", True)
        path = output / f"producer/{DAYS[1]}/freeze.json"
        path.unlink()
        self.assertIn("missing_stage:" + DAYS[1] + ":freeze", self.inspect(output)["errors"])
        result = inspect_bundle(output, start_date=DAYS[0], as_of=NOW, source=SOURCE, recorder_sha="d" * 40)
        self.assertTrue(any("revision_mismatch" in e for e in result["errors"]))

    def test_bundle_retention_and_tampering(self):
        _, output, _ = self.pipeline("retention", True)
        result = inspect_bundle(output, start_date=DAYS[0], as_of="2030-04-05T12:00:00Z", source=SOURCE, recorder_sha=RECORDER)
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        path = next((output / "raw").glob("*/*.json"))
        value = json.loads(path.read_text()); value["response"]["tampered"] = True
        path.write_text(json.dumps(value))
        self.assertTrue(any("digest_mismatch" in e for e in self.inspect(output)["errors"]))

    def test_original_return_identity_exception_and_aliases_restored(self):
        native = self.native_root("identity")
        with native_environment(native, DAYS[0]):
            scan = importlib.import_module("api_market_scan")
            publish = importlib.import_module("api_market_report_diversify")
            original_alias = publish.archive_publication
            response = ({"response": []}, {"authorization": "UNIT_TEST_SECRET"})
            original = Mock(return_value=response)
            scan.api_get = original
            recorder = NativeProducerRecorder(native, self.base / "identity-output", SOURCE,
                recorder_sha=RECORDER, enabled=True, clock=lambda: instant(NOW))
            with recorder.observe():
                self.assertIs(scan.api_get("fixtures"), response)
                self.assertIsNot(publish.archive_publication, original_alias)
            self.assertIs(scan.api_get, original)
            self.assertIs(publish.archive_publication, original_alias)
            original.side_effect = RuntimeError("ORIGINAL_NATIVE_EXCEPTION")
            with self.assertRaisesRegex(RuntimeError, "ORIGINAL_NATIVE_EXCEPTION"), recorder.observe():
                scan.api_get("fixtures")
            self.assertIs(scan.api_get, original)
            self.assertEqual(original.call_count, 2)

    def test_recorder_failure_preserves_original_value(self):
        native = self.native_root("failure")
        with native_environment(native, DAYS[0]):
            scan = importlib.import_module("api_market_scan")
            response = ({"response": []}, {})
            scan.api_get = Mock(return_value=response)
            recorder = NativeProducerRecorder(native, self.base / "failure-output", SOURCE,
                recorder_sha=RECORDER, enabled=True, clock=lambda: instant(NOW))
            with patch.object(recorder, "_raw", side_effect=OSError("UNIT_TEST_SECRET")), recorder.observe():
                self.assertIs(scan.api_get("fixtures"), response)
            self.assertEqual(recorder.errors, ["OSError"])

    def test_output_inside_either_checkout_rejected(self):
        for root in (Path(__file__).resolve().parents[1] / "data", self.native_root("protected") / "capture"):
            with self.assertRaisesRegex(ValueError, "outside_checkouts"):
                NativeProducerRecorder(root.parent if root.name == "capture" else FIXTURE, root, SOURCE, recorder_sha=RECORDER)

    def test_cli_help_does_not_import_native_or_require_credentials(self):
        for module in ("multimodel_v2.producer", "multimodel_v2.bundle"):
            result = subprocess.run([sys.executable, "-B", "-m", module, "--help"],
                capture_output=True, text=True, timeout=15, check=True)
            self.assertIn("usage:", result.stdout)

    def test_native_checkout_pin_mismatch_rejected_before_stage(self):
        from multimodel_v2.producer import main
        root = self.native_root("wrong-pin")
        with patch("multimodel_v2.producer.checkout_sha", return_value="e" * 40), redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit), patch.object(NativeProducerRecorder, "run_stage") as run:
                main(["scan", DAYS[0], "--native-root", str(root), "--output-root", str(self.base / "pin-output"),
                      "--native-sha", NATIVE, "--recorder-sha", RECORDER, "--enabled"])
            run.assert_not_called()

    def test_bundle_unclaimed_file_symlink_and_secret_rejected(self):
        _, output, _ = self.pipeline("security", True)
        (output / "unclaimed.json").write_text('{"api_key":"UNIT_TEST_SECRET"}')
        (output / "link.json").symlink_to(output / "unclaimed.json")
        result = self.inspect(output)
        self.assertIn("bundle_symlink_or_escape", result["errors"])
        self.assertTrue(any("unredacted_secret" in e for e in result["errors"]))
        self.assertIn("unclaimed_bundle_files", result["errors"])

    def test_bundle_cutoff_cannot_be_extended_by_late_asof(self):
        _, output, _ = self.pipeline("late", True)
        with patch("multimodel_v2.bundle.report_deadline", return_value="2030-01-01T08:59:00Z"):
            self.assertTrue(any("after_report_cutoff" in e for e in self.inspect(output)["errors"]))

    def test_malformed_stage_and_altered_native_output_block_without_crash(self):
        _, output, _ = self.pipeline("malformed", True)
        native_output = next((output / "native").glob("*/freeze/*.json"))
        native_output.write_text('{}')
        self.assertTrue(any("native_output_digest_mismatch" in e for e in self.inspect(output)["errors"]))
        path = output / f"producer/{DAYS[0]}/scan.json"
        value = json.loads(path.read_text()); value.pop("raw_receipts")
        value["sha256"] = digest({k: v for k, v in value.items() if k != "sha256"})
        path.write_text(json.dumps(value))
        self.assertTrue(any("file_lists_invalid" in e for e in self.inspect(output)["errors"]))

    def test_failed_native_stage_retains_exception_and_blocks_bundle(self):
        native = self.native_root("failed-stage")
        output = self.base / "failed-output"
        with native_environment(native, DAYS[0]), redirect_stdout(io.StringIO()):
            scan = importlib.import_module("api_market_scan")
            scan.API_CLIENT.get = Mock(side_effect=RuntimeError("UNIT TEST NATIVE FAILURE"))
            recorder = NativeProducerRecorder(native, output, SOURCE, recorder_sha=RECORDER,
                enabled=True, clock=lambda: instant(NOW))
            with self.assertRaisesRegex(RuntimeError, "NATIVE FAILURE"):
                recorder.run_stage("scan", DAYS[0])
        summary = json.loads((output / f"producer/{DAYS[0]}/scan.json").read_text())
        self.assertFalse(summary["native_ok"])
        self.assertEqual(summary["status"], "SOURCE_BLOCKED")
        self.assertFalse(self.inspect(output)["capture_complete"])

    def test_native_settlement_is_observed_without_additional_calls_or_inventing_period(self):
        native = self.native_root("settlement")
        day = "2026-11-01"
        snapshot = native_snapshot()
        row = snapshot["background_candidates"][0]
        output, calls = self.base / "settlement-capture", []
        with patch("datetime.datetime", FixedDatetime), patch.dict(os.environ, {"GITHUB_SHA": NATIVE}), native_environment(native, day), redirect_stdout(io.StringIO()):
            FixedDatetime.current = instant("2026-11-01T09:00:00Z")
            storage = importlib.import_module("api_market_storage")
            policy = importlib.import_module("api_market_policy")
            publication = storage.archive_publication(snapshot, day, policy.load_policy())
            FixedDatetime.current = instant("2026-11-01T22:00:00Z")
            scan = importlib.import_module("api_market_scan")
            def get(base, key, endpoint, **params):
                calls.append((endpoint, params))
                FixedDatetime.current += timedelta(seconds=1)
                if endpoint == "fixtures":
                    rows = [{"fixture": {"id": row["fixture_id"], "date": row["kickoff"], "status": {"short": "FT"}},
                             "teams": {"home": {"id": row["team_id"]}, "away": {"id": 999}}}]
                else:
                    rows = [{"team": {"id": row["team_id"]}, "statistics": [{"type": "Fouls", "value": 5}]}]
                return {"errors": [], "parameters": params, "response": rows}, {}
            scan.API_CLIENT.get = get
            recorder = NativeProducerRecorder(native, output, SOURCE, recorder_sha=RECORDER,
                enabled=True, clock=lambda: FixedDatetime.now(timezone.utc))
            recorder.run_stage("settle", day)
            self.assertEqual(len(calls), 2)
            self.assertIn("native_settlement_linkage_incomplete", recorder.errors)
        path = output / f"outcomes/{day}/{publication['publication']['id']}.json"
        result = json.loads(path.read_text())
        self.assertEqual(result["observations"], [])
        self.assertTrue(result["rejections"])
        self.assertEqual(result["native_publication_id"], publication["publication"]["id"])

    def test_late_native_background_is_preserved_without_retroactive_decisions(self):
        native, output = self.native_root("late-original"), self.base / "late-original-capture"
        with patch("datetime.datetime", FixedDatetime), native_environment(native, "2026-11-01"):
            FixedDatetime.current = instant("2026-11-01T22:00:00Z")
            storage = importlib.import_module("api_market_storage")
            policy = importlib.import_module("api_market_policy")
            recorder = NativeProducerRecorder(native, output, SOURCE, recorder_sha=RECORDER,
                enabled=True, clock=lambda: FixedDatetime.now(timezone.utc))
            with recorder.observe():
                original = storage.archive_publication(native_snapshot(), "2026-11-01", policy.load_policy())
            self.assertIn("forward_capture_after_kickoff", recorder.errors)
        capsule = json.loads(next((output / "full_pool/2026-11-01").glob("*.json")).read_text())
        self.assertEqual(capsule["native_payload"], original)
        self.assertEqual(capsule["capture_mode"], "copy_original")
        self.assertIsNone(capsule["candidate_decisions"])
        self.assertEqual(capsule["fresh_predictions_created"], 0)


class ProposedWorkflowTests(unittest.TestCase):
    def test_native_provenance_proposal_preserves_candidates_and_keeps_workflow_sha_separate(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            native = Path(temp) / "native"
            shutil.copytree(FIXTURE, native)
            subprocess.run(["git", "apply", "--check", str(root / "docs/proposals/multimodel-v2-native-provenance.patch")],
                           cwd=native, check=True, capture_output=True)
            subprocess.run(["git", "apply", str(root / "docs/proposals/multimodel-v2-native-provenance.patch")],
                           cwd=native, check=True, capture_output=True)
            with native_environment(native, "2026-11-01"), patch.dict(os.environ, {"GITHUB_SHA": "b" * 40}):
                storage = importlib.import_module("api_market_storage")
                policy = importlib.import_module("api_market_policy")
                payload = native_snapshot(); before = deepcopy(payload)
                with patch.object(storage.subprocess, "check_output", return_value="d" * 40 + "\n"):
                    published = storage.archive_publication(payload, payload["date"], policy.load_policy(),
                        now=instant("2026-11-01T09:00:00Z"))
                self.assertEqual(published["publication"]["code_revision"], "d" * 40)
                self.assertEqual(published["publication"]["workflow_head_sha"], "b" * 40)
                self.assertEqual(published["top_positions"], before["top_positions"])
                self.assertEqual(published["background_candidates"][0]["fixture_id"], before["background_candidates"][0]["fixture_id"])

    def test_proposals_apply_only_in_scratch_and_shell_blocks_parse(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / ".github/workflows/api-market-multiday-experiment.yml"
            target.parent.mkdir(parents=True)
            target.write_bytes((root / target.relative_to(temp)).read_bytes())
            for name in ("multimodel-v2-recorder-bootstrap.patch", "multimodel-v2-full-source-upload.patch"):
                proposal = root / "docs/proposals" / name
                subprocess.run(["git", "apply", "--check", str(proposal)], cwd=temp, check=True, capture_output=True)
                subprocess.run(["git", "apply", str(proposal)], cwd=temp, check=True, capture_output=True)
            text = target.read_text()
            self.assertIn("ref: " + NATIVE, text)
            self.assertIn("steps.native_bundle.outputs.upload == 'true'", text)
            self.assertIn('code_checkout_sha=subprocess.check_output', text)
            self.assertIn('native_stage scan tools/api_market_scan.py', text)
            # GitHub expressions are substituted by the runner, outside shell.
            lines, blocks, current = text.splitlines(), [], None
            for line in lines:
                if line.strip() == "run: |":
                    current = []
                    blocks.append(current)
                elif current is not None and line.startswith("          "):
                    current.append(line[10:])
                else:
                    current = None
            self.assertGreater(len(blocks), 4)
            for block in blocks:
                subprocess.run(["bash", "-n"], input="\n".join(block) + "\n", text=True, check=True, capture_output=True)


class FormalPublicationBridgeTests(unittest.TestCase):
    def test_disabled_and_missing_authentic_publisher_never_write(self):
        with tempfile.TemporaryDirectory() as temp:
            for enabled in (False, True):
                observer = ForwardPublicationObserver("kb21", temp, enabled=enabled)
                original = {"status": "CANDIDATE_ONLY"}
                self.assertIs(observer.after_publish(original), original)
                self.assertEqual(observer.last_result["status"], "SOURCE_BLOCKED" if enabled else "DISABLED")
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_only_native_current_original_reference_and_id_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            for system in ("kb21", "consensus"):
                payload = formal_payload(system)
                before = deepcopy(payload)
                observer = ForwardPublicationObserver(system, Path(temp) / system, enabled=True,
                    publisher_reference=payload["publication"]["source_reference"], clock=lambda: instant(NOW))
                self.assertIs(observer.after_publish(payload), payload)
                self.assertEqual(observer.last_result["status"], "RECORDED")
                self.assertEqual(payload, before)
                self.assertIs(observer.after_publish(payload), payload)
                self.assertEqual(observer.last_result["status"], "SOURCE_BLOCKED")  # immutable retry

    def test_historical_or_incomplete_payload_cannot_be_issued_as_new(self):
        with tempfile.TemporaryDirectory() as temp:
            payload = formal_payload()
            observer = ForwardPublicationObserver("kb21", temp, enabled=True,
                publisher_reference=payload["publication"]["source_reference"], clock=lambda: instant("2030-01-03T12:00:00Z"))
            observer.after_publish(payload)
            self.assertEqual(observer.last_result["status"], "SOURCE_BLOCKED")
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_malformed_original_publication_never_changes_publisher_return(self):
        observer = ForwardPublicationObserver("kb21", "unused", enabled=True, publisher_reference="authentic-publisher")
        original = {"system": "kb21", "publication": None}
        self.assertIs(observer.after_publish(original), original)
        self.assertEqual(observer.last_result["status"], "SOURCE_BLOCKED")


class OutcomeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.snapshot = native_snapshot()
        self.row = self.snapshot["background_candidates"][0]
        self.final_at = "2026-11-01T22:00:00Z"
        self.stat_at = "2026-11-01T22:01:00Z"
        self.as_of = "2026-11-01T22:02:00Z"
        self.observation = dict(self.row["frozen_quote"]["market_identity"],
            prediction_id=self.snapshot["publication"]["id"], actual=5, hit=1)
        self.receipts = [self.receipt("fixtures", {"errors": [], "response": [{"fixture": {
            "id": self.row["fixture_id"], "date": self.row["kickoff"], "status": {"short": "FT"}}}]}, self.final_at),
            self.receipt("fixtures/statistics", {"errors": [], "parameters": {"fixture": self.row["fixture_id"]}, "response": []}, self.stat_at)]

    def receipt(self, endpoint, response, stamp):
        path = capture_provider_response(response, provider="API-Football", endpoint=endpoint,
            requested_at=stamp, received_at=stamp, source=SOURCE, output_root=self.temp.name, clock=lambda: instant(stamp))
        return read_provider_capture(path, as_of=self.as_of)

    def bridge(self, **kwargs):
        args = dict(as_of=self.as_of, actual_metric=lambda *args: 5, outcome_hit=lambda *args: 1)
        args.update(kwargs)
        return build_linked_native_outcomes(self.snapshot, [self.observation], self.receipts, **args)

    def test_same_native_id_frozen_quote_and_observed_final_time_without_invented_finish(self):
        result = self.bridge()
        self.assertEqual(result["rejections"], [])
        observed = result["observations"][0]
        self.assertNotIn("finished_at", observed)
        self.assertEqual(observed["frozen_quote"], self.row["frozen_quote"])
        audit = build_native_settlements(self.snapshot, result, as_of=self.as_of, full_pool_complete=True)
        self.assertEqual(audit["cohorts"]["original_top"]["rows"][0]["state"], "WIN")

    def test_wrong_native_id_rejected_before_other_missing_fields(self):
        self.observation = {"prediction_id": "FOREIGN_NATIVE_PUBLICATION"}
        self.assertEqual(self.bridge()["rejections"][0]["reason"], "wrong_native_publication_id")

    def test_no_selected_quote_no_default_period_no_final_no_statistics_no_hit(self):
        for change in ("quote", "period", "final", "stats", "actual", "hit"):
            with self.subTest(change=change):
                original = deepcopy((self.snapshot, self.observation, self.receipts))
                if change == "quote":
                    for row in self.snapshot["background_candidates"] + self.snapshot["top_positions"]:
                        row.pop("frozen_quote", None)
                elif change == "period": self.observation.pop("settlement_period")
                elif change == "final": self.receipts = self.receipts[1:]
                elif change == "stats": self.receipts = self.receipts[:1]
                else: self.observation[change] = 999
                self.assertEqual(self.bridge()["observations"], [])
                self.snapshot, self.observation, self.receipts = original

    def test_modified_final_receipt_cannot_settle(self):
        result = self.bridge()
        result["observations"][0]["final_status_receipt"]["response"]["response"][0]["fixture"]["status"]["short"] = "NS"
        audit = build_native_settlements(self.snapshot, result, as_of=self.as_of, full_pool_complete=True)
        self.assertEqual(audit["cohorts"]["original_top"]["rows"][0]["state"], "UNRESOLVED")

    def test_observed_time_cannot_be_presented_as_actual_finished_at(self):
        result = self.bridge()
        result["observations"][0]["finished_at"] = self.final_at
        audit = build_native_settlements(self.snapshot, result, as_of=self.as_of, full_pool_complete=True)
        self.assertEqual(audit["cohorts"]["original_top"]["rows"][0]["state"], "UNRESOLVED")

    def test_observed_final_without_original_statistics_cannot_settle(self):
        result = self.bridge()
        result["observations"][0].pop("statistics_receipt")
        audit = build_native_settlements(self.snapshot, result, as_of=self.as_of, full_pool_complete=True)
        self.assertEqual(audit["cohorts"]["original_top"]["rows"][0]["state"], "UNRESOLVED")

    def test_original_actual_and_hit_callables_receive_native_values(self):
        metric, hit = Mock(return_value=5), Mock(return_value=True)
        self.assertEqual(self.bridge(actual_metric=metric, outcome_hit=hit)["rejections"], [])
        self.assertEqual(metric.call_args.args[2], self.row)
        hit.assert_called_once_with(5.0, float(self.row["line"]), self.row["direction"])
