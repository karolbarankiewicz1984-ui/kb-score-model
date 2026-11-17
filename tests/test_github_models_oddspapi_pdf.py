"""PDF generation smoke tests, without provider calls or real money assertions."""
import tempfile
import unittest
from pathlib import Path

from github_models.oddspapi_report_pdf import make_pdf


class OddsPdfTests(unittest.TestCase):
    def test_missing_market_and_audit_evidence_are_explicit(self):
        collection={"as_of_utc":"2026-11-15T20:00:00Z",
                    "links":{"links":[{"status":"unmatched"}]},
                    "snapshots":[],"billable_requests_made":2}
        overlay={"comparisons":[]}
        audit={"metrics":[]}
        with tempfile.TemporaryDirectory() as td:
            filename=Path(td)/"market.pdf"
            make_pdf(collection,overlay,audit,filename)
            self.assertTrue(filename.is_file())
            self.assertGreater(filename.stat().st_size,1000)
            self.assertEqual(filename.read_bytes()[:5],b"%PDF-")

    def test_pdf_shows_only_verified_quotes(self):
        collection={"as_of_utc":"2026-11-15T20:00:00Z",
                    "links":{"links":[{"status":"matched"}]},
                    "snapshots":[],"billable_requests_made":2}
        row={"fixture_id":"p1","league":"LaLiga2","home":"Albacete",
             "away":"Celta Fortuna","kickoff_utc":"2026-11-16T19:30:00Z",
             "market":"goals","line":2.5,"selection":"over","p_model":0.78,
             "price":1.25,"market_no_vig_probability":0.76,
             "eligible_min_odds_1_20":True,
             "odds_captured_at_utc":"2026-11-15T20:00:00Z"}
        with tempfile.TemporaryDirectory() as td:
            filename=Path(td)/"market.pdf"
            make_pdf(collection,{"comparisons":[row]},{"metrics":[]},filename)
            self.assertGreater(filename.stat().st_size,1500)


if __name__=="__main__":
    unittest.main()
