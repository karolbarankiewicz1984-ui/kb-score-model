"""Seven separate calendar-day PDFs from one frozen run, no rescoring."""
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

import fitz

from github_models.weekly_reports import build, SCHEMA


def fixture():
    return dict(fixture_id="saturday", home="Eibar", away="Cadiz",
                league="LaLiga2", kickoff_utc="2026-11-21T17:30:00Z")


class WeeklyReportsTests(unittest.TestCase):
    def setup_files(self, root, *, missing=None):
        base = date(2026, 11, 15)
        dates = [(base + timedelta(days=i)).isoformat() for i in range(7)]
        (root / "queues").mkdir(parents=True)
        (root / "filters").mkdir(parents=True)
        (root / "pdf").mkdir(parents=True)
        q = dict(dates=dates, missing_dates=missing or [], invalid_dates=[],
                 fixtures=[] if missing else [fixture()])
        selected = dict(input_cutoff_utc="2026-11-15T09:00:00Z",
                        candidates=[] if missing else [
                            dict(fixture_id="saturday", variant="A", market="goals",
                                 selection="under", line=3.5, probability=.81)])
        (root / "queues" / "2026-11-15.json").write_text(json.dumps(q))
        (root / "filters" / "ABC_2026-11-15.json").write_text(json.dumps(selected))
        return q

    def test_seven_pdfs_include_real_last_day_fixture(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            self.setup_files(root)
            report = build(root, "2026-11-15")
            self.assertEqual(report["schema"], SCHEMA)
            self.assertEqual(report["horizon_days"], 7)
            self.assertTrue(report["all_source_dates_valid"])
            self.assertEqual(len(report["reports"]), 7)
            self.assertEqual([r["date"] for r in report["reports"]][-1], "2026-11-21")
            self.assertEqual([r["unique_positions"] for r in report["reports"]],
                             [0, 0, 0, 0, 0, 0, 1])
            with fitz.open(root/"pdf"/"GITHUB_MODELS_V2_ABC_2026-11-21.pdf") as doc:
                result = "\n".join(p.get_text() for p in doc)
                self.assertIn("Eibar", result)
                self.assertIn("Cadiz", result)
                self.assertIn("Poniżej 3,5", result)
                self.assertIn("18:30", result)
            manifest = json.loads((root / "filters" /
                                   "SEVEN_DAY_MANIFEST_2026-11-15.json").read_text())
            self.assertFalse(manifest["odds_verified"])
            self.assertFalse(manifest["probabilities_calibrated"])
            self.assertEqual(manifest["frozen_at_utc"], "2026-11-15T09:00:00Z")

    def test_missing_saturday_is_reported_not_fabricated(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            self.setup_files(root, missing=["2026-11-21"])
            result = build(root, "2026-11-15")
            self.assertFalse(result["all_source_dates_valid"])
            self.assertEqual(result["reports"][-1]["source_status"],
                             "source_snapshot_missing")
            self.assertEqual(result["reports"][-1]["unique_positions"], 0)

    def test_missing_or_duplicate_date_scope_fails_closed(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            self.setup_files(root)
            with self.assertRaisesRegex(ValueError, "do_not_match"):
                build(root, "2026-11-15", days=6)
            for days in (0, 8, True):
                with self.assertRaises(ValueError):
                    build(root, "2026-11-15", days=days)


if __name__ == "__main__":
    unittest.main()
