"""Four-repair integration uses ephemeral unit sources, never real forecasts.

ZIP member and capsule digests are genuinely recomputed/read by production
validators; no readiness or source verifier is mocked.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from multimodel_v2.adapters import adapt_pitchapi, load_json
from multimodel_v2.artifact_audit import read_artifact
from multimodel_v2.capture import capture_provider_response
from multimodel_v2.full_pool import capture_full_pool
from multimodel_v2.repair_pipeline import assess_repair_sources, main
from multimodel_v2.source_manifest import instant
from tests.test_multimodel_v2_adapters import PITCH, capture, sheet_capture
from tests.test_multimodel_v2_formal_freeze import formal_payload
from tests.test_multimodel_v2_full_pool import native_fixture, pure_test_evaluator, rehash, source

START = "2026-11-01"
AS_OF = "2026-11-01T10:00:00Z"
DAYS = ("2026-11-01", "2026-11-02", "2026-11-03")
RECORDED = "2026-11-01T09:00:02Z"


class RepairFixture:
    """Temporary typed native fixtures, not an upstream prediction generator."""
    def __init__(self, root):
        self.root = Path(root)
        self.run = {"id": 11, "head_sha": "b" * 40,
                    "path": ".github/workflows/api-market-multiday-experiment.yml",
                    "status": "completed", "conclusion": "success", "event": "workflow_dispatch",
                    "run_started_at": "2026-11-01T08:00:00Z", "updated_at": "2026-11-01T09:30:00Z"}
        self.jobs = {"total_count": 1, "jobs": [{"id": "unit-only-job", "run_id": 11,
                      "steps": [{"name": "Independent scan per date", "conclusion": "success"}]}]}
        pitch_original = next(r["original"] for r in adapt_pitchapi(load_json(PITCH))["rows"] if r["verified_prematch"])
        self.natives, self.capsules, self.formals, self.pitch, self.extra_members = [], [], {"kb21": [], "consensus": []}, [], {}
        for offset, day in enumerate(DAYS):
            native = native_fixture()
            native["date"] = day
            native["publication"]["id"] = "UNIT-NATIVE-" + day
            row = native["background_candidates"][0]
            row.update(fixture_id=123 + offset, kickoff=day + "T20:00:00Z",
                       home_id=10, away_id=20, competition="UNIT TEST LEAGUE")
            row["market_data"]["quotes"][0]["market_identity"]["fixture_id"] = 123 + offset
            top = deepcopy(row)
            top["frozen_quote"] = deepcopy(row["market_data"]["quotes"][0])
            native["top_positions"] = [top]
            self.natives.append(native)
            self.capsules.append(self.capsule(native))
            for system in self.formals:
                formal = formal_payload(system, day=day)
                formal["publication"].update(id="UNIT-FORMAL-" + system + "-" + day,
                    captured_at_utc="2026-11-01T09:00:00Z", published_at_utc="2026-11-01T09:00:01Z")
                pick = formal["picks"][0]
                pick.update(fixture_id=123 + offset, home=row["home"], away=row["away"],
                            home_id=10, away_id=20, kickoff=row["kickoff"], native_selection_id="UNIT-SELECT-" + day)
                pick["market_identity"] = {k: deepcopy(row[k]) for k in (
                    "fixture_id", "market", "market_scope", "team_id", "direction", "line", "settlement_period")}
                pick["frozen_quote"] = deepcopy(row["market_data"]["quotes"][0])
                pick["frozen_quote"]["source_reference"] = "unit-fixture:original-provider-quote"
                self.formals[system].append(formal)
            context = deepcopy(pitch_original)
            context.update(pitch_match_id="UNIT-PITCH-" + day, home=row["home"], away=row["away"],
                           league="UNIT TEST LEAGUE", kickoff_utc=row["kickoff"])
            self.pitch.append({"schema": "pitchapi-prematch-context-v1", "target_date": day,
                               "snapshot_utc": "2026-11-01T08:59:00Z", "fixtures": [context]})

    def capsule(self, native, source_metadata=None):
        return capture_full_pool(capture(native), source_metadata or source(), recorded_at=RECORDED,
            evaluator=pure_test_evaluator, decision_config={"preserve_min_final_score": 67, "min_quoted_odds": 1.20},
            clock=lambda: instant(RECORDED))

    def archive(self):
        import zipfile
        self.zip_path = self.root / "unit-verified.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            for capsule in self.capsules:
                day = capsule["date"]
                archive.writestr("full_pool/" + day + "/unit.json", json.dumps(capsule))
                archive.writestr("multiday_status/" + day + ".json", json.dumps({"date": day, "status": "ok"}))
            for name, value in self.extra_members.items():
                archive.writestr(name, json.dumps(value))
        self.artifact = {"id": 1, "name": "api-market-multiday-experiment", "expired": False,
                         "size_in_bytes": self.zip_path.stat().st_size,
                         "digest": "sha256:" + hashlib.sha256(self.zip_path.read_bytes()).hexdigest(),
                         "workflow_run": {"id": 11, "head_sha": "b" * 40}}
        return read_artifact(self.zip_path, self.run, self.artifact)

    def assess(self, **changes):
        options = dict(start_date=START, run=self.run, jobs=self.jobs, archives=[self.archive()],
                       formal_captures={s: [capture(p) for p in picks] for s, picks in self.formals.items()},
                       pitch_captures=[capture(p) for p in self.pitch], as_of=AS_OF, checkout_sha="a" * 40)
        options.update(changes)
        return assess_repair_sources(**options)

    def attach_raw_receipt(self, *, workflow_head_sha="b" * 40):
        path = capture_provider_response({"response": []}, provider="API-Football", endpoint="odds",
            requested_at="2026-11-01T08:58:59Z", received_at="2026-11-01T08:59:00Z",
            source={"run_id": 11, "workflow_head_sha": workflow_head_sha, "code_checkout_sha": "a" * 40},
            output_root=self.root / "raw-input", clock=lambda: "2026-11-01T08:59:01Z")
        receipt = json.loads(path.read_bytes())
        self.extra_members["raw/2026-11-01/unit.json"] = receipt
        for envelope in self.capsules:
            envelope["source"]["raw_quote_receipts"] = [{"envelope_sha256": receipt["integrity"]["sha256"],
                "response_sha256": receipt["integrity"]["response_sha256"], "received_at": receipt["received_at"]}]
            rehash(envelope)


class RepairIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = RepairFixture(self.temporary.name)

    def test_complete_forward_evidence_is_test_ready_without_claiming_shadow_pass(self):
        original = deepcopy((self.fixture.natives, self.fixture.formals, self.fixture.pitch))
        result = self.fixture.assess()
        self.assertEqual(result["status"], "READY_FOR_PARALLEL_TEST")
        self.assertTrue(result["ready_for_parallel_1_to_1"])
        self.assertFalse(result["full_shadow_passed"])
        self.assertTrue(all(d["ready_for_new_prematch_report"] for d in result["days"]))
        self.assertTrue(all(e["source"]["raw_quote_receipts"] is None for e in self.fixture.capsules))
        self.assertEqual(original, (self.fixture.natives, self.fixture.formals, self.fixture.pitch))
        self.assertEqual(result["n_effect"], 0)
        self.assertFalse(result["models_executed"])
        self.assertEqual(result["paid_api_calls"], 0)
        self.assertTrue(all(c["metrics"]["roi_pct"] is None for d in result["days"] for c in d["settlements"]["cohorts"].values()))

    def test_formal_published_after_api_original_capture_is_not_available_then(self):
        for records in self.fixture.formals.values():
            records[0]["publication"]["published_at_utc"] = "2026-11-01T09:10:00Z"
        result = self.fixture.assess()
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertIn("formal_publication_after_original_api_freeze:kb21", result["days"][0]["comparison_blockers"])

    def test_late_pitch_snapshot_cannot_enter_earlier_shared_freeze(self):
        self.fixture.pitch[0]["snapshot_utc"] = "2026-11-01T09:00:01Z"
        result = self.fixture.assess()
        self.assertFalse(result["days"][0]["ready_for_frozen_parallel_test"])
        self.assertIn("pitch_fixture_not_covered_at_original_cutoff:123", result["days"][0]["comparison_blockers"])

    def test_native_team_id_conflict_is_not_hidden_by_matching_names(self):
        for records in self.fixture.formals.values():
            row = records[0]["picks"][0]
            row["home_id"] = 999
            row["market_identity"]["team_id"] = 999
            row["frozen_quote"]["market_identity"]["team_id"] = 999
        result = self.fixture.assess()
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertIn("cross_source_native_team_ids_unverified:kb21:123", result["days"][0]["comparison_blockers"])

    def test_second_original_api_fixture_requires_its_own_peer_evidence(self):
        native = self.fixture.natives[0]
        row = deepcopy(native["background_candidates"][0]); row["fixture_id"] = 999
        row["market_data"]["quotes"][0]["market_identity"]["fixture_id"] = 999
        native["background_candidates"].append(row)
        self.fixture.capsules[0] = self.fixture.capsule(native)
        result = self.fixture.assess()
        self.assertEqual(result["days"][0]["required_api_fixture_ids"], ["123", "999"])
        self.assertEqual(len(result["days"][0]["common_fixtures_at_original_cutoff"]), 1)
        self.assertFalse(result["days"][0]["ready_for_frozen_parallel_test"])
        self.assertFalse(result["ready_for_parallel_1_to_1"])

    def test_missing_third_date_cannot_be_replaced_by_two_valid_days(self):
        self.fixture.capsules.pop()
        result = self.fixture.assess()
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertFalse(result["days"][2]["ready_for_frozen_parallel_test"])
        self.assertIn("missing_date", result["planner"]["days"][2]["issues"])

    def test_formal_wrapper_missing_hash_and_locator_blocks_source(self):
        formals = {s: [capture(p) for p in picks] for s, picks in self.fixture.formals.items()}
        formals["kb21"][0] = {"payload": formals["kb21"][0]["payload"]}
        result = self.fixture.assess(formal_captures=formals)
        source_result = result["days"][0]["formal_sources"]["kb21"]
        self.assertEqual(source_result["status"], "SOURCE_BLOCKED")
        self.assertIn("capture.capture_sha256", source_result["missing_fields"])
        self.assertFalse(result["ready_for_parallel_1_to_1"])

    def test_artifact_member_mutation_after_digest_verification_is_detected(self):
        archive = self.fixture.archive()
        name = next(iter(archive["files"]))
        archive["files"][name] += b" "
        result = self.fixture.assess(archives=[archive])
        self.assertIn("artifact_member_changed_after_verification", result["issues"])
        self.assertFalse(result["ready_for_parallel_1_to_1"])

    def test_native_capsule_mutation_inside_valid_zip_is_not_trusted(self):
        self.fixture.capsules[0]["native_payload"]["background_candidates"][0]["line"] = 999
        result = self.fixture.assess()
        self.assertIn("full_pool_digest_mismatch", result["issues"])
        self.assertFalse(result["ready_for_parallel_1_to_1"])

    def test_referenced_raw_receipt_must_exist_in_verified_transport(self):
        self.fixture.capsules[0]["source"]["raw_quote_receipts"] = [{"envelope_sha256": "c" * 64,
            "response_sha256": "d" * 64, "received_at": "2026-11-01T08:59:00Z"}]
        rehash(self.fixture.capsules[0])
        result = self.fixture.assess()
        self.assertIn("raw_quote_receipt_missing_or_ambiguous", result["issues"])
        self.assertFalse(result["days"][0]["ready_for_frozen_parallel_test"])

    def test_valid_raw_response_receipt_binding_preserves_test_readiness(self):
        self.fixture.attach_raw_receipt()
        self.assertTrue(self.fixture.assess()["ready_for_parallel_1_to_1"])

    def test_bound_raw_receipt_cannot_use_another_workflow_head(self):
        self.fixture.attach_raw_receipt(workflow_head_sha="c" * 40)
        result = self.fixture.assess()
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertIn("raw_quote_receipt_binding_mismatch", result["issues"])

    def test_historical_replay_readiness_does_not_issue_new_prematch_report(self):
        result = self.fixture.assess(as_of="2026-11-04T10:00:00Z")
        self.assertTrue(result["ready_for_parallel_1_to_1"])
        self.assertFalse(any(d["ready_for_new_prematch_report"] for d in result["days"]))
        self.assertTrue(all(d["formal_sources"]["kb21"]["purpose"] == "historical_replay" for d in result["days"]))

    def test_private_historical_register_rows_are_never_in_public_summary(self):
        register = sheet_capture("kb21"); register["payload"]["range"]["values"][0].append("Uwagi")
        register["payload"]["range"]["values"][1].append("PRIVATE-UNIT-ONLY-NOTE")
        result = self.fixture.assess(formal_captures={"kb21": [register], "consensus": []})
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertNotIn("PRIVATE-UNIT-ONLY-NOTE", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("original_rows", json.dumps(result))

    def test_wrong_native_settlement_id_is_rejected_without_survivor_roi(self):
        result = self.fixture.assess(outcomes=[{"prediction_id": "UNIT-FOREIGN-PUBLICATION"}])
        self.assertTrue(result["ready_for_parallel_1_to_1"])
        for day in result["days"]:
            self.assertEqual(day["settlements"]["rejection_counts"], {"wrong_native_publication_id": 1})
            self.assertIsNone(day["settlements"]["cohorts"]["original_top"]["metrics"]["roi_pct"])
            self.assertEqual(day["settlements"]["cohorts"]["original_top"]["metrics"]["losses"], 0)

    def test_malformed_pitch_is_blocked_without_crashing_other_source_inspection(self):
        result = self.fixture.assess(pitch_captures=[{"payload": []}])
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertIn("pitch:pitch_capture_wrapper_invalid", result["issues"])

    def test_malformed_register_is_blocked_without_an_exception(self):
        result = self.fixture.assess(formal_captures={"kb21": [{"payload": {"metadata": "invalid"}}], "consensus": []})
        self.assertEqual(result["days"][0]["formal_sources"]["kb21"]["status"], "SOURCE_BLOCKED")
        self.assertFalse(result["ready_for_parallel_1_to_1"])

    def test_missed_original_deadline_blocks_per_day_new_report_flags(self):
        self.fixture.run["updated_at"] = "2026-11-01T10:31:00Z"
        result = self.fixture.assess(as_of="2026-11-01T10:32:00Z")
        self.assertFalse(result["ready_for_parallel_1_to_1"])
        self.assertFalse(any(d["ready_for_new_prematch_report"] for d in result["days"]))
        self.assertTrue(all("report_deadline_missed" in d["issues"] for d in result["planner"]["days"]))

    def test_independent_models_retain_distinct_native_markets_on_same_verified_fixture(self):
        for system, market in (("kb21", "corners"), ("consensus", "yellow")):
            for document in self.fixture.formals[system]:
                row = document["picks"][0]
                row["market_identity"]["market"] = market
                row["frozen_quote"]["market_identity"]["market"] = market
        result = self.fixture.assess()
        self.assertTrue(result["ready_for_parallel_1_to_1"])
        self.assertTrue(all(d["comparison_scope"] == "all_original_api_fixtures_independent_native_market_cohorts" for d in result["days"]))


class RepairPipelineCliTests(unittest.TestCase):
    def test_cli_replays_real_verified_test_zip_and_emits_only_json(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = RepairFixture(root)
            fixture.archive()
            base = Path(root)
            def write(name, payload):
                path = base / name
                path.write_text(json.dumps(payload))
                return str(path)
            config = {"run": write("run.json", fixture.run), "jobs": write("jobs.json", fixture.jobs),
                      "artifacts": [{"zip": str(fixture.zip_path), "artifact_id": 1,
                                     "metadata": write("artifacts.json", {"artifacts": [fixture.artifact]})}],
                      "formal": {s: [write(s + day + ".json", payload) for day, payload in zip(DAYS, items)]
                                 for s, items in fixture.formals.items()},
                      "pitch": [write("pitch-" + day + ".json", payload) for day, payload in zip(DAYS, fixture.pitch)],
                      "checkout_sha": "a" * 40}
            manifest = write("manifest.json", config)
            out = StringIO()
            with redirect_stdout(out):
                main(["--manifest", manifest, "--start", START, "--as-of", AS_OF])
            result = json.loads(out.getvalue())
            self.assertEqual(result["status"], "READY_FOR_PARALLEL_TEST")
            self.assertFalse(result["full_shadow_passed"])


if __name__ == "__main__":
    unittest.main()
