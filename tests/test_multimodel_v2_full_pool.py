"""Immutable full-pool copies and fresh-only native filter tracing, offline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from multimodel_v2.adapters import load_json
from multimodel_v2.full_pool import (
    _bytes, _sha, build_full_pool, capture_full_pool, read_full_pool,
    verify_full_pool, write_full_pool,
)
from multimodel_v2.source_manifest import instant
from tests.test_multimodel_v2_adapters import EXPORT, PREDICTION, capture
from tests.test_multimodel_v2_provenance import evidence

NOW = "2026-11-01T09:00:02Z"
SHA = "a" * 40


def source():
    return {"run_id": 11, "workflow_path": ".github/workflows/api-market-multiday-experiment.yml",
            "workflow_head_sha": "b" * 40, "code_checkout_sha": SHA}


def native_fixture():
    # Explicit in-memory unit fixtures. Never written to original source data.
    _, snapshots = evidence()
    native = deepcopy(snapshots[0])
    native.update(schema="api-market-scan-v3", publication={"id": "unit-test-native-publication",
        "captured_at_utc": "2026-11-01T09:00:01Z", "code_revision": SHA, "provenance": "live_pre_match"})
    row = native["background_candidates"][0]
    row.update(selection="UNIT TEST UNDER", api_pure_pct=70, final_status="ACCEPT")
    top = deepcopy(row);top["frozen_quote"] = deepcopy(row["market_data"]["quotes"][0])
    native["top_positions"] = [top]
    return native


def pure_test_evaluator(payload, cfg):
    """Signature fixture only; production's unchanged callable is injected."""
    row = payload["background_candidates"][0]
    if row["final_assessment_pct"] < cfg["preserve_min_final_score"]:
        return [], {"below_score_threshold": 1}
    if not any(q["selected_odd"] >= cfg["min_quoted_odds"] for q in row["market_data"]["quotes"]):
        return [], {"no_eligible_quote": 1}
    return [row], {}


def forward(native=None, **changes):
    args = dict(recorded_at=NOW, evaluator=pure_test_evaluator,
                decision_config={"preserve_min_final_score": 67, "min_quoted_odds": 1.20},
                clock=lambda: instant(NOW))
    args.update(changes)
    return capture_full_pool(capture(native or native_fixture()), source(), **args)


def rehash(envelope):
    envelope["content_sha256"] = _sha({k:v for k,v in envelope.items() if k != "content_sha256"})
    return envelope


class FullPoolPreservationTests(unittest.TestCase):
    def test_real_222_native_rows_and_top_51_preserved_without_invented_quote_identity(self):
        c = load_json(PREDICTION); original = deepcopy(c)
        actual_source = {"run_id":40910335546,"workflow_path":".github/workflows/api-market-scan.yml",
            "workflow_head_sha":"1e7f72041c3777e3d094c7036c9d9a6aba7aab6d",
            "code_checkout_sha":"1e7f72041c3777e3d094c7036c9d9a6aba7aab6d"}
        result = build_full_pool(c,actual_source,recorded_at="2026-11-02T18:00:00Z")
        self.assertEqual(result["native_payload"],c["payload"])
        self.assertEqual(result["counts"]["captured_candidates"],222)
        self.assertEqual(result["counts"]["native_top_positions"],51)
        self.assertEqual(result["counts"]["native_score_bands"]["below_67"],171)
        self.assertTrue(result["verification"]["full_pool_complete"])
        self.assertFalse(result["verification"]["source_eligible"])
        self.assertEqual(result["verification"]["status"],"INCOMPLETE")
        self.assertFalse(result["preservation"]["native_fields_synthesized"])
        self.assertTrue(all("market_identity" not in q for r in result["native_payload"]["background_candidates"] for q in r["market_data"]["quotes"]))
        self.assertEqual(c,original)
        verify_full_pool(result,as_of="2026-11-02T18:00:00Z")

    def test_filtered_only_export_cannot_be_recovered_as_full_background(self):
        for declared in (1473,999):
            c=load_json(EXPORT);c["payload"]["candidate_count"]=declared
            with self.subTest(declared=declared),self.assertRaisesRegex(ValueError,"full_candidate_pool_not_recorded"):
                build_full_pool(c,source(),recorded_at=NOW)

    def test_workflow_head_and_checkout_sha_remain_distinct(self):
        result=forward()
        self.assertEqual(result["source"]["workflow_head_sha"],"b"*40)
        self.assertEqual(result["source"]["code_checkout_sha"],SHA)
        self.assertEqual(result["verification"]["status"],"COMPLETE")

    def test_wrong_checkout_blocks_source_without_rewriting_native_revision(self):
        s=source();s["code_checkout_sha"]="c"*40
        r=build_full_pool(capture(native_fixture()),s,recorded_at=NOW)
        self.assertIn("native_publication_checkout_mismatch",r["verification"]["blockers"])
        self.assertEqual(r["native_payload"]["publication"]["code_revision"],SHA)

    def test_missing_original_decisions_are_unknown_not_reconstructed(self):
        r=build_full_pool(capture(native_fixture()),source(),recorded_at=NOW)
        self.assertIsNone(r["candidate_decisions"])
        self.assertIn("original_decision_trace_missing",r["verification"]["blockers"])
        self.assertEqual(r["counts"]["recorded_decisions"],{})

    def test_no_fresh_trace_can_be_injected_into_historical_copy(self):
        with self.assertRaisesRegex(ValueError,"no_new_historical_decision_trace"):
            build_full_pool(capture(native_fixture()),source(),recorded_at=NOW,candidate_decisions={})

    def test_native_top_quote_missing_is_not_filled_from_other_book(self):
        n=native_fixture();n["top_positions"][0].pop("frozen_quote")
        r=forward(n)
        self.assertIn("original_top_frozen_quote_missing",r["verification"]["blockers"])
        self.assertNotIn("frozen_quote",r["native_payload"]["top_positions"][0])

    def test_conflicting_side_specific_price_or_direction_blocks_source(self):
        for change in ({"under_odd":99},{"direction":"over"}):
            n=native_fixture();n["background_candidates"][0]["market_data"]["quotes"][0].update(change)
            n["top_positions"][0]["frozen_quote"].update(change)
            with self.subTest(change=change):
                r=forward(n)
                self.assertFalse(r["verification"]["source_eligible"])
                self.assertTrue(any(code in r["verification"]["blockers"] for code in ("conflicting_quote_price","quote_direction_mismatch")))

    def test_missing_publication_id_stays_missing(self):
        n=native_fixture();n["publication"].pop("id")
        r=build_full_pool(capture(n),source(),recorded_at=NOW)
        self.assertIn("native_publication_id_missing",r["verification"]["blockers"])
        self.assertNotIn("id",r["native_payload"]["publication"])

    def test_declared_count_mismatch_does_not_become_complete_pool(self):
        n=native_fixture();n["candidate_count"]=999
        r=forward(n)
        self.assertFalse(r["verification"]["full_pool_complete"])
        self.assertFalse(r["verification"]["source_eligible"])
        self.assertEqual(len(r["native_payload"]["background_candidates"]),1)

    def test_provider_quote_receipt_references_are_retained_but_late_reference_blocks(self):
        s=source();s["raw_quote_receipts"]=[{"envelope_sha256":"d"*64,"response_sha256":"e"*64,"received_at":"2026-11-01T09:00:00Z","provider":"recorded provider","endpoint":"odds"}]
        r=build_full_pool(capture(native_fixture()),s,recorded_at=NOW)
        self.assertEqual(r["source"]["raw_quote_receipts"],s["raw_quote_receipts"])
        s["raw_quote_receipts"][0]["received_at"]="2026-11-01T09:00:02Z"
        r=build_full_pool(capture(native_fixture()),s,recorded_at=NOW)
        self.assertIn("raw_quote_receipt_after_publication",r["verification"]["blockers"])

    def test_same_fixture_across_distinct_markets_cannot_have_conflicting_facts(self):
        for field,value in [("kickoff","2026-11-01T21:00:00Z"),("home","OTHER HOME"),("away","OTHER AWAY"),("home_id",999),("away_id",888)]:
            n=native_fixture();n["background_candidates"][0].update(home_id=10,away_id=20)
            row=deepcopy(n["background_candidates"][0]);row["line"]=14.5;row["market_data"]["quotes"][0]["market_identity"]["line"]=14.5;row[field]=value
            n["background_candidates"].append(row)
            with self.subTest(field=field):
                r=forward(n)
                self.assertTrue(r["verification"]["full_pool_complete"])
                self.assertFalse(r["verification"]["source_eligible"])
                self.assertIn("conflicting_native_fixture_facts",r["verification"]["blockers"])
                self.assertEqual(r["native_payload"]["background_candidates"][1][field],value)

    def test_original_top_gate_is_independent_of_missing_trace_and_pool_count(self):
        for count in (None,999):
            n=native_fixture()
            if count is not None:n["candidate_count"]=count
            with self.subTest(count=count):
                r=build_full_pool(capture(n),source(),recorded_at=NOW)
                self.assertFalse(r["verification"]["source_eligible"])
                self.assertTrue(r["verification"]["original_top_eligible"])
                self.assertEqual(r["verification"]["original_top_blockers"],[])
                self.assertEqual(r["verification"]["full_pool_complete"],count is None)

    def test_unrelated_rejected_row_gaps_do_not_erase_known_original_top(self):
        n=native_fixture();other=deepcopy(n["background_candidates"][0]);other.update(fixture_id=999,final_assessment_pct=None)
        other["market_data"].pop("quotes");n["background_candidates"].append(other)
        r=build_full_pool(capture(n),source(),recorded_at=NOW)
        self.assertFalse(r["verification"]["source_eligible"])
        self.assertTrue(r["verification"]["original_top_eligible"])

    def test_top_selected_quote_can_reference_background_without_redundant_top_universe(self):
        n=native_fixture();n["top_positions"][0].pop("market_data");before=deepcopy(n)
        r=build_full_pool(capture(n),source(),recorded_at=NOW)
        self.assertNotIn("frozen_quote",r["native_payload"]["background_candidates"][0])
        self.assertNotIn("market_data",r["native_payload"]["top_positions"][0])
        self.assertTrue(r["verification"]["original_top_eligible"])
        self.assertEqual(n,before)

    def test_fixture_conflict_blocks_affected_top_but_not_unrelated_top(self):
        for fixture_id,expected in ((123,False),(999,True)):
            n=native_fixture()
            for line,kickoff in ((14.5,"2026-11-01T20:00:00Z"),(15.5,"2026-11-01T21:00:00Z")):
                other=deepcopy(n["background_candidates"][0]);other.update(fixture_id=fixture_id,line=line,kickoff=kickoff)
                other["market_data"]["quotes"][0]["market_identity"].update(fixture_id=fixture_id,line=line)
                n["background_candidates"].append(other)
            with self.subTest(fixture_id=fixture_id):
                r=build_full_pool(capture(n),source(),recorded_at=NOW)
                self.assertFalse(r["verification"]["source_eligible"])
                self.assertEqual(r["verification"]["original_top_eligible"],expected)

    def test_recorded_quote_reference_mismatch_cannot_qualify_original_top(self):
        for field in ("quote_id","provider_quote_id","source_id","source_reference"):
            n=native_fixture();old={"receipt":"original"} if field=="source_reference" else "original-reference"
            new={"receipt":"different"} if field=="source_reference" else "different-reference"
            n["background_candidates"][0]["market_data"]["quotes"][0][field]=old
            n["top_positions"][0]["market_data"]["quotes"][0][field]=old
            n["top_positions"][0]["frozen_quote"][field]=new
            with self.subTest(field=field):
                r=build_full_pool(capture(n),source(),recorded_at=NOW)
                self.assertFalse(r["verification"]["original_top_eligible"])
                self.assertIn("original_top_frozen_quote_mismatch",r["verification"]["original_top_blockers"])

    def test_original_top_gate_still_requires_native_binding_and_valid_selected_quote_time(self):
        cases=[lambda n:n["publication"].update(code_revision="d"*40),
               lambda n:n["top_positions"][0]["frozen_quote"].update(provider_updated_at="2026-11-01T20:00:00Z"),
               lambda n:n["top_positions"][0]["frozen_quote"].update(selected_odd=1)]
        for change in cases:
            n=native_fixture();change(n)
            r=build_full_pool(capture(n),source(),recorded_at=NOW)
            self.assertFalse(r["verification"]["original_top_eligible"])
            self.assertTrue(r["verification"]["original_top_blockers"])


class ForwardTraceTests(unittest.TestCase):
    def test_below_67_rows_kept_with_original_evaluator_rejection_code(self):
        n=native_fixture();low=deepcopy(n["background_candidates"][0]);low.update(line=14.5,final_assessment_pct=66)
        low["market_data"]["quotes"][0]["market_identity"]["line"]=14.5
        n["background_candidates"].append(low)
        r=forward(n)
        self.assertEqual(r["counts"]["captured_candidates"],2)
        self.assertEqual(r["counts"]["native_score_bands"]["below_67"],1)
        self.assertEqual(r["candidate_decisions"]["records"][1]["rejection_reasons"],["below_score_threshold"])
        self.assertEqual(r["native_payload"]["background_candidates"][1],low)
        self.assertEqual(r["verification"]["status"],"COMPLETE")

    def test_explicit_rejected_empty_quotes_is_known_absence_not_missing_pool(self):
        n=native_fixture();row=deepcopy(n["background_candidates"][0]);row["line"]=14.5;row["market_data"]["quotes"]=[]
        n["background_candidates"].append(row)
        r=forward(n)
        self.assertTrue(r["verification"]["rows"][1]["known_no_offer"])
        self.assertTrue(r["verification"]["full_pool_complete"])
        self.assertTrue(r["verification"]["source_eligible"])
        self.assertEqual(r["candidate_decisions"]["records"][1]["rejection_reasons"],["no_eligible_quote"])

    def test_absent_quotes_key_is_unknown_even_if_an_evaluator_rejects(self):
        n=native_fixture();n["background_candidates"][0]["market_data"].pop("quotes")
        reject=lambda p,c:([],{"missing_quote":1})
        r=forward(n,evaluator=reject)
        self.assertFalse(r["verification"]["rows"][0]["known_no_offer"])
        self.assertFalse(r["verification"]["source_eligible"])

    def test_original_config_and_input_do_not_change_when_evaluator_mutates_its_copy(self):
        n=native_fixture();old=deepcopy(n);cfg={"preserve_min_final_score":67,"min_quoted_odds":1.2}
        def mutate(payload,config):
            payload["background_candidates"][0]["line"]=999
            config["preserve_min_final_score"]=1
            return payload["background_candidates"],{}
        forward(n,evaluator=mutate,decision_config=cfg)
        self.assertEqual(n,old)
        self.assertEqual(cfg["preserve_min_final_score"],67)

    def test_old_original_cannot_be_retraced_even_when_recorded_at_is_forged_old(self):
        spy=Mock(side_effect=pure_test_evaluator)
        with self.assertRaisesRegex(ValueError,"trusted_clock_window"):
            forward(evaluator=spy,clock=lambda:instant("2026-11-02T09:00:02Z"))
        spy.assert_not_called()

    def test_direct_forward_builder_also_checks_actual_collector_clock(self):
        with self.assertRaisesRegex(ValueError,"trusted_clock_window"):
            build_full_pool(capture(native_fixture()),source(),recorded_at=NOW,mode="forward",
                            clock=lambda:instant("2026-11-02T09:00:02Z"))

    def test_future_recorded_at_and_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"trusted_clock_window"):
            forward(recorded_at="2026-11-01T09:00:03Z")
        with self.assertRaisesRegex(ValueError,"trusted_clock_timezone"):
            forward(clock=lambda:instant(NOW).replace(tzinfo=None))

    def test_slow_callback_crossing_kickoff_cannot_publish_prematch(self):
        clock=Mock(side_effect=[instant(NOW),instant("2026-11-01T20:00:01Z")])
        with self.assertRaisesRegex(ValueError,"trusted_clock_window|after_kickoff"):
            forward(clock=clock)

    def test_post_kickoff_invocation_rejected_before_filter(self):
        n=native_fixture();n["background_candidates"][0]["kickoff"]=NOW
        spy=Mock(side_effect=pure_test_evaluator)
        with self.assertRaisesRegex(ValueError,"after_kickoff"):
            forward(n,evaluator=spy)
        spy.assert_not_called()

    def test_ambiguous_evaluator_decisions_rejected(self):
        with self.assertRaisesRegex(ValueError,"decision_ambiguous"):
            forward(evaluator=lambda p,c:([],{"a":1,"b":1}))

    def test_bad_original_trace_row_hash_is_not_silently_repaired(self):
        n=native_fixture();n["candidate_decisions"]={"records":[{"native_index":0,"row_sha256":"0"*64,"decision":"ACCEPTED","rejection_reasons":[]}]}
        with self.assertRaisesRegex(ValueError,"original_decision_row_digest_mismatch"):
            build_full_pool(capture(n),source(),recorded_at=NOW)

    def test_malformed_recorded_decision_values_fail_closed_without_type_error(self):
        for malformed in ([],{},None):
            n=native_fixture();n["candidate_decisions"]=deepcopy(forward()["candidate_decisions"])
            n["candidate_decisions"]["records"][0]["decision"]=malformed
            with self.subTest(malformed=malformed):
                r=build_full_pool(capture(n),source(),recorded_at=NOW)
                self.assertFalse(r["verification"]["source_eligible"])
                self.assertEqual(r["counts"]["recorded_decisions"],{"UNKNOWN":1})
                self.assertIn("original_candidate_decision_invalid",r["verification"]["blockers"])


class FullPoolStorageTests(unittest.TestCase):
    def test_immutable_date_partition_and_reader_verify_hash_and_native_fields(self):
        r=forward()
        with tempfile.TemporaryDirectory() as root:
            path=write_full_pool(r,root)
            self.assertEqual(path.parent.name,"2026-11-01")
            self.assertEqual(path.name,"unit-test-native-publication.json")
            self.assertEqual(read_full_pool(path,as_of=NOW),r)
            with self.assertRaises(FileExistsError):write_full_pool(r,root)
            self.assertEqual(path.read_bytes(),_bytes(r))

    def test_retention_rejects_expired_reads_without_deleting_evidence(self):
        r=forward(retention_days=1)
        with tempfile.TemporaryDirectory() as root:
            path=write_full_pool(r,root)
            with self.assertRaisesRegex(ValueError,"expired"):
                read_full_pool(path,as_of="2026-11-02T09:00:03Z")
            self.assertTrue(path.is_file())

    def test_reader_rejects_time_before_copy_was_recorded(self):
        with self.assertRaisesRegex(ValueError,"not_available"):
            verify_full_pool(forward(),as_of="2026-11-01T09:00:01Z")

    def test_size_and_retention_limits_reject_invalid_options(self):
        for opts in ({"max_bytes":100},{"max_bytes":True},{"retention_days":0},{"retention_days":91}):
            with self.subTest(opts=opts),self.assertRaises(ValueError):forward(**opts)

    def test_native_price_mutation_breaks_integrity(self):
        r=forward();r["native_payload"]["background_candidates"][0]["market_data"]["quotes"][0]["selected_odd"]=9.99
        with self.assertRaisesRegex(ValueError,"digest_mismatch"):
            verify_full_pool(r,as_of=NOW)

    def test_stored_complete_flags_are_recomputed_not_trusted(self):
        r=build_full_pool(capture(native_fixture()),source(),recorded_at=NOW)
        r["verification"]["source_eligible"]=True;rehash(r)
        with self.assertRaisesRegex(ValueError,"verification_tampered"):
            verify_full_pool(r,as_of=NOW)

    def test_count_tampering_and_retention_extension_are_detected(self):
        r=forward();r["counts"]["captured_candidates"]=999;rehash(r)
        with self.assertRaisesRegex(ValueError,"counts_tampered"):verify_full_pool(r,as_of=NOW)
        r=forward();r["expires_at_utc"]="2027-11-01T09:00:02Z";rehash(r)
        with self.assertRaisesRegex(ValueError,"retention_tampered"):verify_full_pool(r,as_of=NOW)

    def test_api_secrets_are_redacted_recursively_without_changing_forecast_fields(self):
        n=native_fixture();token="unit-secret-value-12345678"
        n["metadata"]={"API_FOOTBALL_KEY":token,"headers":{"X-RapidAPI-Key":token},"url":"https://example.invalid/odds?api_key="+token}
        n["background_candidates"][0]["debug_token"]=token
        r=forward(n,secret_values=[token])
        encoded=_bytes(r).decode()
        self.assertNotIn(token,encoded)
        self.assertEqual(r["native_payload"]["background_candidates"][0]["line"],13.5)
        self.assertTrue(r["preservation"]["secret_redaction_paths"])
        self.assertNotEqual(r["preservation"]["original_payload_sha256"],r["preservation"]["retained_payload_sha256"])
        verify_full_pool(r,as_of=NOW)

    def test_all_provider_header_variants_and_embedded_assignments_are_redacted(self):
        secret="sensitive-provider-credential-123"
        n=native_fixture();n["diagnostics"]={
            "PITCHAPI_API_KEY":secret,"refresh_token":secret,"X-ApiSports-Key":secret,
            "lines":["X-RapidAPI-Key: "+secret,"X-ApiSports-Key="+secret,
                     "API_FOOTBALL_KEY="+secret,"Authorization: Bearer "+secret]}
        r=forward(n)
        self.assertNotIn(secret,_bytes(r).decode())
        self.assertEqual(r["native_payload"]["background_candidates"],n["background_candidates"])

    def test_protected_repository_path_is_never_an_export_destination(self):
        root=Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(ValueError,"protected_production"):
            write_full_pool(forward(),root/"archive"/"never-created-full-pool")
        self.assertFalse((root/"archive"/"never-created-full-pool").exists())

    def test_entire_checkout_is_excluded_from_new_full_pool_storage(self):
        root=Path(__file__).resolve().parents[1]
        for folder in (root,root/"docs"/"never-created-full-pool",root/"work"/"never-created-full-pool"):
            with self.subTest(folder=folder),self.assertRaisesRegex(ValueError,"protected_production"):
                write_full_pool(forward(),folder)

    def test_symlinked_date_partition_cannot_redirect_output(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as other:
            (Path(root)/"2026-11-01").symlink_to(other,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"symlinked"):
                write_full_pool(forward(),root)
            self.assertEqual(list(Path(other).iterdir()),[])


if __name__ == "__main__":
    unittest.main()
