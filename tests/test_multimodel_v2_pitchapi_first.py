import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from multimodel_v2.pitchapi_first import three_day_pitchapi_inventory


class PitchAPIFirstTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.as_of = "2026-11-05T10:30:00+00:00"

    def write(self, day="2026-11-06", *, stamp="2026-11-05T09:00:00Z",
              kickoff="2026-11-06T18:00:00Z", previous="2026-11-01T18:00:00Z"):
        sample = {"samples": [{"kickoff_utc": previous}], "complete_samples": 1}
        payload = {"schema": "pitchapi-prematch-context-v1", "target_date": day,
                   "source": "PitchAPI", "snapshot_utc": stamp,
                   "fixtures": [{"pitch_match_id": "m_1", "home": "A", "away": "B",
                                 "kickoff_utc": kickoff, "home_recent": sample,
                                 "away_recent": sample, "both_sides_sufficient": False}]}
        (self.root / (day + ".json")).write_text(json.dumps(payload))

    def test_three_dates_and_context_not_bets(self):
        self.write()
        rows = three_day_pitchapi_inventory("2026-11-05", self.root, as_of=self.as_of)
        self.assertEqual([r["status"] for r in rows], ["missing", "context_only", "missing"])
        self.assertEqual(rows[1]["fixtures_count"], 1)
        self.assertFalse(rows[1]["top_authorized"])
        self.assertFalse(rows[1]["quotes_authorized"])

    def test_rejects_wrong_warsaw_report_day(self):
        with self.assertRaisesRegex(ValueError, "start_date_not_current_warsaw_day"):
            three_day_pitchapi_inventory("2026-11-06", self.root, as_of=self.as_of)

    def test_rejects_late_snapshot(self):
        self.write(stamp="2026-11-05T12:00:00Z")
        rows = three_day_pitchapi_inventory("2026-11-05", self.root, as_of=self.as_of)
        self.assertEqual(rows[1]["status"], "invalid")

    def test_rejects_future_historical_match(self):
        self.write(previous="2026-11-05T09:30:00Z")
        rows = three_day_pitchapi_inventory("2026-11-05", self.root, as_of=self.as_of)
        self.assertEqual(rows[1]["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
