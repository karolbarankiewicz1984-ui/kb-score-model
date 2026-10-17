import tempfile
import unittest
from pathlib import Path

from tools.kb21_queue_report import render_day, write_reports


class QueueReportTests(unittest.TestCase):
    def test_populated_report_never_invents_p_model_or_play(self):
        queue = {"days": ["2026-10-17"], "source_errors": [],
                 "fixtures": [{
                     "date_warsaw": "2026-10-17", "fixture": "A - B",
                     "competition": "Premier League", "fixture_id": "eng.1:12",
                     "kickoff": "2026-10-17T19:00:00+02:00",
                     "assessment": {
                         "fixture": "A - B", "market": None, "str": None,
                         "qual": None, "match": None, "p_model": None
                     }
                 }]}
        report = render_day(queue, "2026-10-17")
        self.assertIn("A - B", report)
        self.assertIn("eng.1:12", report)
        self.assertIn("NIE WYZNACZONO", report)
        self.assertIn("BRAK ZWERYFIKOWANEJ OCENY", report)
        self.assertIn("Calendar Gate: BLOCKED", report)
        self.assertIn("NO PLAY", report)
        self.assertNotIn("Decyzja: PLAY", report)

    def test_dated_output_for_empty_fixture_day(self):
        queue = {"days": ["2026-10-17", "2026-10-18"], "fixtures": []}
        with tempfile.TemporaryDirectory() as tempdir:
            days = write_reports(queue, tempdir)
            self.assertEqual(days, ["2026-10-17", "2026-10-18"])
            self.assertIn("Nie znaleziono kandydatów", (
                Path(tempdir) / "KB21_ANALYST_QUEUE_2026-10-18.md"
            ).read_text(encoding="utf-8"))
            self.assertTrue((Path(tempdir) / "KB21_ANALYST_QUEUE_INDEX.md").exists())

    def test_invalid_queue_is_rejected(self):
        with self.assertRaises(ValueError):
            render_day({"fixtures": None}, "2026-10-17")


if __name__ == "__main__":
    unittest.main()
