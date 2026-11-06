"""Source observations must never precede the network response they describe."""
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from github_models import public_results, collect_events
from github_models.daily_queue import build_queue


class IngestionContractTests(unittest.TestCase):
    def test_all_supported_csv_divisions_retain_country_and_match_date(self):
        for code, league in public_results.LEAGUES.items():
            with self.subTest(code=code):
                text = f"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\n{code},01/11/2026,A,B,1,0\n"
                rows = public_results.parse_csv(text, league_code=code, season="2627",
                    observed_at_utc="2026-11-06T12:00:00Z")
                self.assertEqual(rows[0]["league"], league)
                self.assertEqual(rows[0]["country_code"], public_results.COUNTRIES[code])
                self.assertEqual(rows[0]["match_date"], "2026-11-01")

    def test_result_receipt_timestamp_is_after_response_body(self):
        state = {"received": False}

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                hour = 12 if state["received"] else 10
                return datetime(2026, 11, 6, hour, tzinfo=timezone.utc)

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                state["received"] = True
                return b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nE0,01/11/2026,A,B,1,0\n"

        with tempfile.TemporaryDirectory() as tmp:
            output, manifest = str(Path(tmp) / "results.json"), str(Path(tmp) / "manifest.json")
            with patch.object(public_results, "datetime", Clock), \
                 patch.object(public_results, "LEAGUES", {"E0": "Premier League"}), \
                 patch.object(public_results, "SEASONS", ("2627",)), \
                 patch.object(public_results, "urlopen", return_value=Response()), \
                 patch("sys.argv", ["public_results", "--output", output, "--manifest", manifest]):
                public_results.main()
            data = json.loads(Path(output).read_text())
            receipt = json.loads(Path(manifest).read_text())["sources"][0]
            self.assertEqual(data[0]["published_at_utc"], "2026-11-06T12:00:00Z")
            self.assertEqual(receipt["observed_at_utc"], data[0]["published_at_utc"])
            self.assertEqual(len(receipt["sha256"]), 64)

    def test_failed_uncapped_source_is_not_an_empty_complete_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = dict(schema="pitchapi-research-fixtures-v1", source="PitchAPI",
                source_status="source_error", target_date="2026-11-06",
                snapshot_utc="2026-11-06T08:00:00Z", fixtures=[])
            Path(tmp, "2026-11-06.json").write_text(json.dumps(payload))
            queue = build_queue(tmp, start_date="2026-11-06", as_of_utc="2026-11-06T09:00:00Z")
            self.assertEqual(queue["invalid_dates"], ["2026-11-06"])
            self.assertIn("invalid_snapshot:incomplete_pitchapi_source_response", queue["exclusion_summary"])


if __name__ == "__main__":
    unittest.main()
