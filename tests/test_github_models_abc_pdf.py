"""Regression tests for the unified GitHub ABC PDF presentation."""
import json
from pathlib import Path
import tempfile
import unittest

import fitz
from github_models.abc_audit_pdf import build as build_audit
from github_models.abc_report import build as build_forecast, label_market, select_overview

class ABCPDFTests(unittest.TestCase):
    def test_market_labels_and_balanced_shortlist(self):
        self.assertEqual(label_market(dict(market="goals", selection="under", line=3.5)),
                         "Bramki: Poniżej 3,5")
        self.assertEqual(label_market(dict(market="1X2", selection="X")),
                         "Wynik meczu: X (remis)")
        rows = [dict(fixture_id=str(n), market="fouls", selection="over",
                     line=19.5, probability=.99 - n / 1000) for n in range(12)]
        rows += [dict(fixture_id="g", market="goals", selection="over",
                      line=1.5, probability=.81)]
        result = select_overview(rows)
        self.assertEqual(sum(x["market"] == "fouls" for x in result), 3)
        self.assertEqual(sum(x["market"] == "goals" for x in result), 1)

    def test_forecast_pdf_and_full_json(self):
        predictions = {"as_of_utc":"2026-11-07T08:00:00+00:00", "predictions":[]}
        events = {"markets":[
            {"fixture_id":"1","model_id":"m","market":"fouls","line":19.5,
             "selection":"over","probability":.88},
            {"fixture_id":"1","model_id":"m","market":"fouls","line":19.5,
             "selection":"under","probability":.12},
        ]}
        queue = {"fixtures":[{"fixture_id":"1","home":"Łódź FC","away":"Żagiel",
                               "kickoff_utc":"2026-11-07T16:00:00Z"}]}
        with tempfile.TemporaryDirectory() as d:
            j = Path(d)/"ABC_2026-11-07.json"
            pdf = Path(d)/"ABC_2026-11-07.pdf"
            result = build_forecast(predictions, events, queue, j, pdf)
            self.assertEqual(result["counts"], {"A":1,"B":1,"C":1})
            self.assertEqual(json.loads(j.read_text(encoding="utf-8"))["counts"],
                             result["counts"])
            self.assertGreater(pdf.stat().st_size, 1000)
            with fitz.open(pdf) as doc:
                text = "\n".join(page.get_text() for page in doc)
                self.assertIn("Wariant A", text)
                self.assertIn("Wariant B", text)
                self.assertIn("Wariant C", text)
                self.assertIn("Powyżej 19,5", text)
                self.assertIn("brak", text)
                self.assertIn("07.11 17:00", text)

    def test_audit_pdf_marks_empty_as_unresolved_not_loss(self):
        data = {"as_of_utc":"2026-11-07T12:00:00Z", "archives_processed":2,
                "forecast_records":2, "unique_candidate_records":2,
                "duplicate_snapshots_suppressed":0, "summary":[
                    {"variant":"A","market":"all","settled":0,"hits":0,
                     "unique_fixtures":0,"unresolved":2,
                     "hit_rate":None,"brier":None,"log_loss":None}],
                "unresolved_reasons":{"no_verified_result":2}}
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d)/"AUDIT_2026-11-07.pdf"
            build_audit(data, pdf)
            with fitz.open(pdf) as doc:
                text = "\n".join(page.get_text() for page in doc)
                self.assertIn("brak próby", text)
                self.assertIn("Brakujące wyniki", text)
                self.assertIn("no_verified_result", text)
                self.assertNotIn("100,0%", text)

if __name__ == "__main__":
    unittest.main()
