"""Native-freeze parser fixtures are test-only, never historical forecasts."""
from copy import deepcopy
from datetime import datetime
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from multimodel_v2.formal_freeze import (
    MAX_BYTES, SCHEMA, inspect_historical_register, read_forward_freeze,
    record_forward_freeze, verify_formal_freeze, main,
)
from tests.test_multimodel_v2_adapters import ROOT, capture, sheet_capture

NOW = "2030-01-01T09:00:00Z"


def formal_payload(system="kb21", *, day="2030-01-02"):
    identity = {"fixture_id": "test-only-fixture", "market": "corners", "market_scope": "team",
                "team_id": "test-home", "direction": "under", "line": "5.5",
                "settlement_period": "regulation_time"}
    return {"schema": SCHEMA, "system": system, "date": day, "complete": True, "selection_count": 1,
            "publication": {"id": "TEST-ONLY-native-publication", "captured_at_utc": "2030-01-01T08:59:00Z",
                            "published_at_utc": "2030-01-01T08:59:45Z", "provenance": "live_pre_match",
                            "source_reference": "test-fixture:native-publisher-version"},
            "picks": [{"native_selection_id": "TEST-ONLY-native-selection", "event_date": day,
                       "fixture_id": "test-only-fixture", "home": "TEST HOME", "away": "TEST AWAY",
                       "home_id": "test-home", "away_id": "test-away",
                       "fixture_source_reference": "test-fixture:native-event-version",
                       "kickoff": day + "T19:00:00+01:00", "market_identity": identity,
                       "frozen_quote": {"market_identity": deepcopy(identity), "bookmaker": "TEST BOOK",
                                        "selected_odd": "1.95", "provider_updated_at": "2030-01-01T08:58:00Z",
                                        "source_reference": "test-fixture:original-provider-quote"},
                       "status": "TEST native status", "probability_original": "0.57",
                       "model_values_original": {"unchanged": "test-native-value"}}]}


def verify(payload, **kwargs):
    args = {"report_date": payload["date"], "as_of": NOW}
    args.update(kwargs)
    return verify_formal_freeze(capture(payload), **args)


def clock():
    return datetime.fromisoformat(NOW.replace("Z", "+00:00"))


class FormalFreezeTests(unittest.TestCase):
    def test_missing_capture_wrapper_blocks_complete_source_verification(self):
        result = verify_formal_freeze({"payload": formal_payload()}, report_date="2030-01-02", as_of=NOW)
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIn("capture.locator", result["missing_fields"])
        self.assertIn("capture.capture_sha256", result["missing_fields"])
        self.assertEqual(result["verified_picks"], [])
        self.assertEqual(result["original_payload"], formal_payload())

    def test_malformed_capture_metadata_preserves_native_validation_errors(self):
        for locator, digest in [("", "a" * 64), (False, "a" * 64), ("test", "b" * 63), ("test", "X" * 64), ("test", None)]:
            with self.subTest(locator=locator, digest=digest):
                payload = formal_payload(); del payload["publication"]["id"]
                result = verify_formal_freeze({"locator": locator, "capture_sha256": digest, "payload": payload},
                                             report_date="2030-01-02", as_of=NOW)
                self.assertEqual(result["status"], "SOURCE_BLOCKED")
                self.assertIn("publication.id", result["missing_fields"])
                self.assertTrue(any(e["reason"].startswith("formal_capture_") for e in result["rejections"]))

    def test_current_native_freeze_preserves_all_model_values_and_native_identity(self):
        payload = formal_payload(); before = deepcopy(payload)
        result = verify(payload)
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["current_ready"])
        self.assertEqual(result["native_publication_id"], payload["publication"]["id"])
        self.assertEqual(result["verified_picks"], payload["picks"])
        self.assertEqual(result["original_payload"], payload)
        self.assertEqual(payload, before)
        self.assertEqual(result["n_effect"], 0)

    def test_consensus_requires_native_fields_identically_without_time_zone_inference(self):
        payload = formal_payload("consensus")
        self.assertEqual(verify(payload)["status"], "READY")
        del payload["picks"][0]["kickoff"]
        payload["picks"][0]["Analysis Time"] = "11:30"
        result = verify(payload)
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIn("picks[0].kickoff", result["missing_fields"])

    def test_historical_formal_freeze_can_be_audited_but_not_issued_as_new_prematch(self):
        result = verify(formal_payload(), as_of="2030-01-03T09:00:00Z")
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["purpose"], "historical_replay")
        self.assertFalse(result["current_ready"])
        self.assertFalse(result["eligible_as_new_prematch"])

    def test_late_publication_is_blocked_even_when_still_before_kickoff(self):
        payload = formal_payload(day="2030-01-01")
        payload["publication"].update(captured_at_utc="2030-01-01T11:00:00Z", published_at_utc="2030-01-01T11:01:00Z")
        result = verify(payload, as_of="2030-01-01T12:00:00Z")
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIn("publication_after_report_cutoff_or_observation", [e["reason"] for e in result["rejections"]])

    def test_global_earlier_cutoff_applies_to_tomorrows_event(self):
        payload = formal_payload()
        result = verify(payload, report_cutoff="2030-01-01T08:59:30Z")
        self.assertEqual(result["status"], "SOURCE_BLOCKED")
        self.assertIn("publication_after_report_cutoff_or_observation", [e["reason"] for e in result["rejections"]])

    def test_cutoff_cannot_be_extended_past_report_day_1130_warsaw(self):
        with self.assertRaisesRegex(ValueError, "after_warsaw_deadline"):
            verify(formal_payload(), report_cutoff="2030-01-02T11:31:00+01:00")

    def test_warsaw_deadline_tracks_summer_and_winter_offsets(self):
        summer = formal_payload(day="2030-03-31")
        winter = formal_payload(day="2030-10-27")
        self.assertEqual(verify(summer, as_of="2030-03-31T12:00:00Z")["report_cutoff"], "2030-03-31T09:30:00Z")
        self.assertEqual(verify(winter, as_of="2030-10-27T12:00:00Z")["report_cutoff"], "2030-10-27T10:30:00Z")

    def test_missing_native_id_is_not_replaced_by_capture_hash(self):
        payload = formal_payload(); del payload["publication"]["id"]
        result = verify(payload)
        self.assertIsNone(result["native_publication_id"])
        self.assertIn("publication.id", result["missing_fields"])
        self.assertEqual(result["verified_picks"], [])

    def test_source_references_are_required_for_publication_fixture_and_quote(self):
        for section, name in [("publication", "source_reference"), ("pick", "fixture_source_reference"), ("quote", "source_reference")]:
            with self.subTest(section=section):
                payload = formal_payload()
                obj = payload["publication"] if section == "publication" else payload["picks"][0] if section == "pick" else payload["picks"][0]["frozen_quote"]
                del obj[name]
                self.assertEqual(verify(payload)["status"], "SOURCE_BLOCKED")

    def test_team_market_cannot_name_a_team_outside_the_original_fixture(self):
        payload = formal_payload(); row = payload["picks"][0]
        row["market_identity"]["team_id"] = "another-team"
        row["frozen_quote"]["market_identity"]["team_id"] = "another-team"
        result = verify(payload)
        self.assertIn("formal_fixture_team_mismatch", [e["reason"] for e in result["rejections"]])

    def test_quote_wrong_exact_line_is_rejected_without_copying_candidate_identity(self):
        payload = formal_payload(); payload["picks"][0]["frozen_quote"]["market_identity"]["line"] = "5.50001"
        self.assertIn("formal_quote_market_mismatch", [e["reason"] for e in verify(payload)["rejections"]])

    def test_post_capture_or_post_kickoff_quote_is_rejected(self):
        for stamp in ("2030-01-01T08:59:01Z", "2030-01-02T18:00:00Z"):
            with self.subTest(stamp=stamp):
                payload = formal_payload(); payload["picks"][0]["frozen_quote"]["provider_updated_at"] = stamp
                self.assertIn("formal_quote_lookahead", [e["reason"] for e in verify(payload)["rejections"]])

    def test_post_kickoff_publication_is_rejected(self):
        payload = formal_payload(day="2030-01-01"); payload["picks"][0]["kickoff"] = "2030-01-01T08:59:30Z"
        self.assertIn("formal_publication_not_before_kickoff", [e["reason"] for e in verify(payload)["rejections"]])

    def test_missing_timezone_and_invalid_price_are_not_repaired(self):
        for field, value in [("provider_updated_at", "2030-01-01T08:58:00"), ("selected_odd", None), ("selected_odd", True), ("selected_odd", "NaN")]:
            with self.subTest(field=field, value=value):
                payload = formal_payload(); payload["picks"][0]["frozen_quote"][field] = value
                self.assertEqual(verify(payload)["status"], "SOURCE_BLOCKED")

    def test_duplicate_selection_ids_and_exact_markets_are_ambiguous(self):
        for mutation in ("id", "market"):
            with self.subTest(mutation=mutation):
                payload = formal_payload(); other = deepcopy(payload["picks"][0])
                if mutation == "id":
                    other["market_identity"]["line"] = "6.5"; other["frozen_quote"]["market_identity"]["line"] = "6.5"
                else:
                    other["native_selection_id"] = "OTHER-TEST-native-selection"
                payload["picks"].append(other); payload["selection_count"] = 2
                self.assertEqual(verify(payload)["status"], "SOURCE_BLOCKED")

    def test_conflicting_fixture_facts_are_rejected(self):
        payload = formal_payload(); other = deepcopy(payload["picks"][0]); other["home"] = "OTHER TEST HOME"
        other["native_selection_id"] = "OTHER-TEST-native-selection"
        other["market_identity"]["line"] = "6.5"; other["frozen_quote"]["market_identity"]["line"] = "6.5"
        payload["picks"].append(other); payload["selection_count"] = 2
        self.assertIn("conflicting_formal_fixture", [e["reason"] for e in verify(payload)["rejections"]])

    def test_partial_universe_does_not_become_a_complete_zero(self):
        payload = formal_payload(); payload["picks"] = []; payload["selection_count"] = 0
        payload["complete"] = False
        self.assertEqual(verify(payload)["status"], "SOURCE_BLOCKED")
        payload["complete"] = True
        self.assertEqual(verify(payload)["status"], "READY")

    def test_schema_or_system_or_declared_count_mismatch_is_blocked(self):
        for key, value in [("schema", "raw-register-v1"), ("selection_count", 2)]:
            payload = formal_payload(); payload[key] = value
            self.assertEqual(verify(payload)["status"], "SOURCE_BLOCKED")
        result = verify_formal_freeze(capture(formal_payload()), report_date="2030-01-02", as_of=NOW, system="consensus")
        self.assertEqual(result["status"], "SOURCE_BLOCKED")


class HistoricalRegisterTests(unittest.TestCase):
    def test_historical_kb_is_not_promoted_and_original_fields_are_retained(self):
        source = sheet_capture("kb21"); before = deepcopy(source)
        r = inspect_historical_register(source, "kb21", report_date="2026-11-02", as_of="2026-11-02T18:00:00Z")
        self.assertEqual(r["status"], "SOURCE_BLOCKED")
        self.assertEqual(r["recorded_selection_rows"], 1)
        self.assertEqual(r["source_dated_selection_rows"], 0)
        self.assertEqual(r["current_formal_picks"], [])
        self.assertEqual(r["original_rows"][0]["probability_original"], 0.57)
        self.assertEqual(source, before)
        self.assertEqual(r["historical_rows_promoted"], 0)
        self.assertEqual(r["n_effect"], 0)

    def test_current_dated_selection_and_analysis_time_are_still_not_formal(self):
        source = sheet_capture("consensus"); source["payload"]["range"]["values"][1][0] = "2026-11-02"
        r = inspect_historical_register(source, "consensus", report_date="2026-11-02", as_of="2026-11-02T09:00:00Z")
        self.assertEqual(r["source_dated_selection_rows"], 1)
        self.assertEqual(r["current_formal_picks"], [])
        self.assertIn("picks[].event_date", r["missing_fields"])
        self.assertIsNone(r["original_rows"][0]["kickoff"])


class ForwardPublicationTests(unittest.TestCase):
    def test_numeric_native_id_preserves_original_type_across_record_and_read(self):
        payload = formal_payload(); payload["publication"]["id"] = 7
        with tempfile.TemporaryDirectory() as root:
            result = record_forward_freeze(payload, root, clock=clock)
            self.assertEqual(result["native_publication_id"], 7)
            self.assertEqual(read_forward_freeze(result["path"])["payload"]["publication"]["id"], 7)

    def test_exclusive_receipt_keeps_native_payload_and_never_adds_n(self):
        payload = formal_payload(); before = deepcopy(payload)
        with tempfile.TemporaryDirectory() as root:
            r = record_forward_freeze(payload, root, clock=clock)
            stored = read_forward_freeze(r["path"])
            self.assertEqual(stored["payload"], payload)
            self.assertEqual(r["native_publication_id"], payload["publication"]["id"])
            self.assertEqual(r["n_effect"], 0)
            self.assertEqual(payload, before)
            self.assertFalse(list(Path(root).rglob(".pending-freeze-*")))

    def test_replay_or_changed_content_under_same_native_id_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            payload = formal_payload(); result = record_forward_freeze(payload, root, clock=clock)
            raw = Path(result["path"]).read_bytes()
            for changed in (False, True):
                if changed: payload["picks"][0]["frozen_quote"]["selected_odd"] = "2.05"
                with self.assertRaises(FileExistsError):record_forward_freeze(payload, root, clock=clock)
                self.assertEqual(Path(result["path"]).read_bytes(), raw)

    def test_old_or_future_publication_cannot_be_backfilled_as_current(self):
        for stamp in ("2029-12-31T08:59:45Z", "2030-01-01T09:00:01Z"):
            with tempfile.TemporaryDirectory() as root:
                payload = formal_payload(); payload["publication"]["published_at_utc"] = stamp
                with self.assertRaisesRegex(ValueError, "forward_only"):
                    record_forward_freeze(payload, root, clock=clock)
                self.assertEqual(list(Path(root).iterdir()), [])

    def test_aged_capture_is_not_given_a_fresh_native_freeze(self):
        payload = formal_payload(); payload["publication"]["captured_at_utc"] = "2030-01-01T08:54:59Z"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "forward_only"):
                record_forward_freeze(payload, root, clock=clock)

    def test_protected_checkout_and_symlink_escapes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside_checkout"):
            record_forward_freeze(formal_payload(), ROOT / "archive", clock=clock)
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            (Path(root) / "kb21").symlink_to(other, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink_escape"):
                record_forward_freeze(formal_payload(), root, clock=clock)
            self.assertEqual(list(Path(other).iterdir()), [])

    def test_corrupt_receipt_does_not_verify(self):
        with tempfile.TemporaryDirectory() as root:
            result = record_forward_freeze(formal_payload(), root, clock=clock)
            path = Path(result["path"]); receipt = json.loads(path.read_bytes())
            receipt["native_freeze"]["picks"][0]["frozen_quote"]["selected_odd"] = "9.9"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "integrity"):
                read_forward_freeze(path)

    def test_reader_rejects_symlink_and_nonregular_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            result = record_forward_freeze(formal_payload(), root, clock=clock)
            link = Path(root) / "test-receipt-link.json"; link.symlink_to(result["path"])
            with self.assertRaisesRegex(ValueError, "symlink"):
                read_forward_freeze(link)
            with self.assertRaisesRegex(ValueError, "regular_file"):
                read_forward_freeze(root)

    def test_reader_checks_size_before_loading_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "oversized-test-receipt.json"
            with path.open("wb") as stream:
                stream.truncate(MAX_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "size_limit"):
                read_forward_freeze(path)

    def test_reader_rejects_tampered_record_time_even_when_native_digest_matches(self):
        with tempfile.TemporaryDirectory() as root:
            result = record_forward_freeze(formal_payload(), root, clock=clock)
            path = Path(result["path"]); receipt = json.loads(path.read_bytes())
            receipt["recorded_at_utc"] = "2030-01-02T09:00:00Z"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "forward_time_mismatch"):
                read_forward_freeze(path)


class FormalFreezeCliTests(unittest.TestCase):
    def test_verify_cli_returns_summary_without_model_values_or_pick_details(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "test-native-freeze.json"
            source.write_text(json.dumps(formal_payload()))
            out = StringIO()
            with redirect_stdout(out):
                main(["verify", "--source", str(source), "--date", "2030-01-02", "--as-of", NOW])
            result = json.loads(out.getvalue())
            self.assertEqual(result["verified_pick_count"], 1)
            self.assertEqual(result["status"], "READY")
            self.assertNotIn("original_payload", result)
            self.assertNotIn("verified_picks", result)

    def test_register_cli_returns_missing_fields_without_private_register_notes(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "test-register-capture.json"
            source.write_text(json.dumps(sheet_capture("kb21")["payload"]))
            out = StringIO()
            with redirect_stdout(out):
                main(["inspect-register", "--source", str(source), "--date", "2026-11-02", "--as-of", "2026-11-02T18:00:00Z", "--system", "kb21"])
            result = json.loads(out.getvalue())
            self.assertEqual(result["status"], "SOURCE_BLOCKED")
            self.assertNotIn("original_rows", result)

    def test_record_cli_has_no_option_to_backdate_trusted_clock(self):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(["record", "--source", "test-only.json", "--output-dir", "/tmp/test-only", "--as-of", NOW])


if __name__ == "__main__":
    unittest.main()
