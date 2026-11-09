"""Regression tests for the unified GitHub ABC PDF presentation."""
import json
from pathlib import Path
import tempfile
import unittest

import fitz
from github_models.abc_audit_pdf import build as build_audit
from github_models.abc_report import build as build_forecast, label_market, select_overview, report_day
from github_models.abc_chronological_pdf import collapse, select_top, by_day

class ABCPDFTests(unittest.TestCase):
    def test_new_filename_day_and_legacy_filename(self):
        self.assertEqual(report_day("GITHUB_MODELS_V2_ABC_2026-11-09.pdf", {}),
                         "2026-11-09")
        self.assertEqual(report_day("ABC_2026-11-08.pdf", {}), "2026-11-08")
        self.assertEqual(report_day("GITHUB_MODELS_V2_ABC_badname.pdf",
                                    {"date": "2026-11-07"}), "2026-11-07")

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
                self.assertIn("Podsumowanie dnia", text)
                self.assertIn("Najsilniejsze pozycje dnia", text)
                self.assertIn("Pełny harmonogram meczów", text)
                self.assertIn("A/B/C", text)
                self.assertIn("Powyżej 19,5", text)
                self.assertIn("brak", text)
                self.assertIn("17:00", text)

    def test_all_market_lines_and_chronological_order_preserved(self):
        predictions = {"as_of_utc":"2026-11-07T08:00:00+00:00", "predictions":[]}
        rows = []
        for fixture_id, market, line, val in (
            ("one", "goals", 1.5, .84), ("one", "fouls", 19.5, .95),
            ("one", "fouls", 22.5, .83), ("one", "cards", 2.5, .89),
            ("one", "corners", 7.5, .82), ("two", "goals", 3.5, .77)):
            rows += [
                {"fixture_id": fixture_id, "model_id": "test", "market": market,
                 "line": line, "selection": "over", "probability": val},
                {"fixture_id": fixture_id, "model_id": "test", "market": market,
                 "line": line, "selection": "under", "probability": 1-val},
            ]
        queue = {"fixtures":[
            {"fixture_id":"one", "home":"Późniejsi", "away":"Gospodarze",
             "kickoff_utc":"2026-11-08T18:00:00Z"},
            {"fixture_id":"two", "home":"Wcześniejsi", "away":"Goście",
             "kickoff_utc":"2026-11-08T14:00:00Z"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            json_out = Path(directory)/"ABC_2026-11-08.json"
            pdf = Path(directory)/"ABC_2026-11-08.pdf"
            result = build_forecast(predictions, {"markets":rows}, queue, json_out, pdf)
            all_day, missing, outside = by_day(result,
                         {str(f["fixture_id"]): f for f in queue["fixtures"]}, "2026-11-08")
            self.assertEqual((len(missing), outside), (0, 0))
            self.assertEqual(len(collapse(all_day)), 6)
            self.assertEqual(len(json.loads(json_out.read_text())["candidates"]),
                             len(result["candidates"]))
            self.assertEqual(result["counts"], {"A":6,"B":6,"C":5})
            with fitz.open(pdf) as doc:
                content = "\\n".join(page.get_text() for page in doc)
                schedule = content.split("Pełny harmonogram meczów", 1)[1]
                self.assertLess(schedule.index("Wcześniejsi – Goście"),
                                schedule.index("Późniejsi – Gospodarze"))
                for label in ("Bramki: Powyżej 1,5",
                              "Faule: Powyżej 19,5", "Faule: Powyżej 22,5",
                              "Żółte kartki: Powyżej 2,5",
                              "Rożne: Powyżej 7,5", "Bramki: Powyżej 3,5"):
                    self.assertIn(label, content)
                self.assertIn("A/B/C", content)

    def test_day_scoping_does_not_erase_full_json(self):
        predictions = {"predictions":[]}
        events = {"markets":[
          {"fixture_id":f, "model_id":"m", "market":"goals", "line":1.5,
           "selection":s, "probability":.8 if s=="over" else .2}
          for f in ("a","b") for s in ("over","under")]}
        queue = {"fixtures":[
            {"fixture_id":"a","home":"Dzisiaj","away":"Goście",
             "kickoff_utc":"2026-11-08T15:00:00Z"},
            {"fixture_id":"b","home":"Jutro","away":"Goście",
             "kickoff_utc":"2026-11-09T15:00:00Z"}]}
        with tempfile.TemporaryDirectory() as d:
            j, pdf = Path(d)/"ABC_2026-11-08.json", Path(d)/"ABC_2026-11-08.pdf"
            result = build_forecast(predictions, events, queue, j, pdf)
            self.assertEqual(result["counts"]["A"], 2)
            with fitz.open(pdf) as doc:
                content = "\\n".join(page.get_text() for page in doc)
                self.assertIn("Dzisiaj – Goście", content)
                self.assertNotIn("Jutro – Goście", content)
            self.assertEqual(len(json.loads(j.read_text())["candidates"]), 6)

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
