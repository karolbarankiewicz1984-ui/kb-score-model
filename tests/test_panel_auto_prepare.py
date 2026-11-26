import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import json

from tools import panel_auto_prepare as auto

NOW = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
RAW = json.dumps({"generated_at_utc":"2026-11-26T09:00:00Z"}).encode()

class AutoTest(unittest.TestCase):
    def run_case(self, raw=RAW, matching=True, audit="2026-11-25T21:00:00Z"):
        def recent(role):
            return [{"id": n} for n in {"odds":[3],"abc":[5,4],"audit":[2]}[role]]
        def fetch(role, n, path):
            with ZipFile(path, "w") as z:
                name = {"odds":"pitch_queue.json","abc":"reports/github_models/queues/2026-11-26.json","audit":"audit.json"}[role]
                z.writestr(name, raw if role=="odds" or (role=="abc" and n==4 and matching) else b"{}")
        def build(a,o,u,day,ids,out):
            self.assertEqual(ids, {"odds":3,"abc":4,"audit":2})
            self.assertEqual(day,"2026-11-26")
            out.write_bytes(b"validated")
        with tempfile.TemporaryDirectory() as d, patch.object(auto,"recent",side_effect=recent), patch.object(auto,"fetch",side_effect=fetch), patch.object(auto,"build",side_effect=build), patch.object(auto,"check",return_value={"audit_as_of_utc":audit}):
            out = Path(d)/"latest.zip"
            try:
                ids = auto.prepare(out,NOW)
            except Exception:
                self.assertFalse(out.exists())
                raise
            self.assertEqual(out.read_bytes(),b"validated")
            return ids

    def test_exact_match(self):
        self.assertEqual(self.run_case()["abc"],4)

    def test_old_queue(self):
        with self.assertRaisesRegex(ValueError,"no_current_warsaw_day_odds"):
            self.run_case(b'{"generated_at_utc":"2026-11-25T09:00:00Z"}')

    def test_future_queue(self):
        with self.assertRaisesRegex(ValueError,"no_current_warsaw_day_odds"):
            self.run_case(b'{"generated_at_utc":"2026-11-26T13:00:00Z"}')

    def test_wrong_queue(self):
        with self.assertRaisesRegex(ValueError,"no_exact_abc_queue_match"):
            self.run_case(matching=False)

    def test_stale_audit(self):
        with self.assertRaisesRegex(ValueError,"audit_not_recent"):
            self.run_case(audit="2026-11-23T21:00:00Z")

    def test_bad_run(self):
        with patch.object(auto,"api",return_value={"workflow_runs":[{"id":1,"head_branch":"other"}]}):
            with self.assertRaisesRegex(ValueError,"invalid_run_metadata"):
                auto.recent("abc")

if __name__ == "__main__":
    unittest.main()
