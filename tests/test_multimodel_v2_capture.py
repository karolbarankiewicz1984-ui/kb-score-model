"""No-network future response retention, secret handling and immutability."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from multimodel_v2.capture import capture_provider_response, read_provider_capture

NOW = "2026-11-04T08:00:01Z"
SOURCE = {"run_id": "11", "workflow_head_sha": "a" * 40, "code_checkout_sha": "b" * 40}


class ProviderCaptureTests(unittest.TestCase):
    def write(self, root, response=None, **overrides):
        args = dict(provider="API-Football", endpoint="odds", requested_at="2026-11-04T07:59:59Z",
                    received_at="2026-11-04T08:00:00Z", source=deepcopy(SOURCE),
                    output_root=root, clock=lambda: NOW)
        args.update(overrides)
        return capture_provider_response(response if response is not None else {"response": []}, **args)

    def test_receipt_preserves_original_fields_and_distinct_checkout_without_new_forecast(self):
        response={"response":[{"fixture":{"id":17},"bookmakers":[{"id":3,"bets":[{"id":57,"values":[{"value":"Under 6.5","odd":"1.75"}]}]}]}]}
        original=deepcopy(response)
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root,response);stored=read_provider_capture(path,as_of=NOW)
            self.assertEqual(stored["response"],response)
            self.assertEqual(stored["source"],SOURCE)
            self.assertFalse(stored["creates_native_publication"])
            self.assertEqual(stored["n_effect"],0)
            self.assertNotIn("publication",stored)
            self.assertNotIn("market_identity",stored["response"]["response"][0])
        self.assertEqual(response,original)

    def test_redacts_credentials_but_preserves_real_prices(self):
        response={"api_key":"test-secret-only","nested":{"X-RapidAPI-Key":"test-secret-only"},
                  "error":"https://source.invalid/odds?api_key=test-secret-only&fixture=17",
                  "header":"Bearer test-secret-only","price":"1.75"}
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root,response);self.assertNotIn("test-secret-only",path.read_text())
            stored=read_provider_capture(path,as_of=NOW)
            self.assertEqual(stored["response"]["price"],"1.75")
            self.assertEqual(len(stored["redacted_paths"]),4)

    def test_old_or_future_response_cannot_be_recorded_as_fresh(self):
        with tempfile.TemporaryDirectory() as root:
            for stamp in ["2026-11-03T08:00:00Z","2026-11-04T08:00:02Z"]:
                with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError,"not_fresh"):
                    self.write(root,requested_at=stamp,received_at=stamp)

    def test_credential_key_variants_and_diagnostic_headers_are_redacted(self):
        secret="UNIT-ONLY-SECRET-REPRO"
        response={"headers_text":"X-RapidAPI-Key: "+secret,"PITCHAPI_API_KEY":secret,
                  "refresh_token":secret,"diagnostic":"X-ApiSports-Key="+secret}
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root,response)
            self.assertNotIn(secret,path.read_text())
            self.assertEqual(len(read_provider_capture(path,as_of=NOW)["redacted_paths"]),4)

    def test_identical_receipt_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root);original=path.read_bytes()
            with self.assertRaises(FileExistsError):self.write(root)
            self.assertEqual(path.read_bytes(),original)

    def test_reader_rejects_tampered_response(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root);data=json.loads(path.read_bytes());data["response"]={"changed":True};path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"digest_mismatch"):read_provider_capture(path,as_of=NOW)

    def test_reader_enforces_capture_availability_and_retention(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.write(root)
            for cutoff in ["2026-11-04T07:59:59Z","2027-01-01T00:00:00Z"]:
                with self.subTest(cutoff=cutoff),self.assertRaisesRegex(ValueError,"unavailable_or_expired"):
                    read_provider_capture(path,as_of=cutoff)

    def test_no_capture_under_protected_repository(self):
        from multimodel_v2.capture import REPO
        with self.assertRaisesRegex(ValueError,"isolated_output"):
            self.write(REPO/"archive"/"unit-test-should-not-exist")

    def test_symlink_escape_rejected_before_creating_external_date_directory(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as outside:
            (Path(root)/"raw").symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"path_escape"):self.write(root)
            self.assertEqual(list(Path(outside).iterdir()),[])

    def test_query_credentials_and_invalid_retention_or_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for change in [{"endpoint":"odds?api_key=test"},{"retention_days":0},{"retention_days":True},
                           {"source":{"run_id":"unit-test","workflow_head_sha":"short","code_checkout_sha":"b"*40}}]:
                with self.subTest(change=change),self.assertRaises(ValueError):self.write(root,**change)

    def test_credential_bearing_metadata_is_rejected_before_storage(self):
        with tempfile.TemporaryDirectory() as root:
            for changes in [{"provider":"API-Football api_key=UNIT-ONLY-SECRET-REPRO"},
                            {"source":dict(SOURCE,run_id="api_key=UNIT-ONLY-SECRET-REPRO")}]:
                with self.subTest(changes=changes),self.assertRaises(ValueError):self.write(root,**changes)
            self.assertEqual(list(Path(root).iterdir()),[])


if __name__ == "__main__":
    unittest.main()
