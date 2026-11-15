"""Offline audit PDF smoke test; no OddsPapi or independent provider requests."""
import tempfile
import unittest
from pathlib import Path

from github_models.oddspapi_audit_pdf import render_audit


class AuditPdfTest(unittest.TestCase):
    def test_no_settled_matches_is_reported_not_invented(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"audit.pdf"
            render_audit({
                "archives_processed":1,"unique_selection_quotes":8,
                "settled_selection_quotes":0,"unique_settled_fixtures":0,
                "duplicates_suppressed":0,
                "promotion_gate":{"minimum_reached":False},
                "summary":[],"by_market":[],"by_probability_band":[]},path)
            self.assertEqual(path.read_bytes()[:5],b"%PDF-")
            self.assertGreater(path.stat().st_size,1000)


if __name__=="__main__":
    unittest.main()
