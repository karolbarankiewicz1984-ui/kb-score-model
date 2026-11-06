"""Report tests use labelled synthetic fixtures, never repository forecasts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import pymupdf
from pypdf import PdfReader

from github_models.research_pdf import build


def inputs(count=1):
    queue = {"dates": ["2035-05-01"], "fixtures": []}
    forecasts, markets = [], []
    for i in range(count):
        fid = "pdf-test-" + str(i)
        queue["fixtures"].append({"fixture_id": fid, "league": "Liga testowa",
            "home": "Żółta drużyna testowa " + str(i), "away": "Goście <test> & " + str(i),
            "kickoff_utc": "2035-05-01T18:00:00Z"})
        for model, values in (("test-elo", (.6, .25, .15)), ("test-dixon", (.55, .30, .15))):
            forecasts.append(dict(fixture_id=fid, model_id=model, p_home=values[0],
                p_draw=values[1], p_away=values[2], probability_status="uncalibrated_research",
                training_matches=100))
        for market, lines in (("goals", (1.5, 2.5, 3.5)), ("corners", (7.5, 8.5, 9.5)),
                              ("cards", (2.5, 3.5, 4.5)), ("fouls", (19.5, 22.5, 25.5))):
            for line in lines:
                for selection, probability in (("over", .65), ("under", .35)):
                    markets.append(dict(fixture_id=fid, model_id="test-poisson", market=market,
                        selection=selection, line=line, probability=probability,
                        league_n=100, home_n=12, away_n=10))
    return ({"generated_at_utc": "2035-05-01T08:00:00Z", "predictions": forecasts,
             "blockers": [{"fixture_id": "blocked", "reason": "unsupported_competition"}]},
            queue, {"markets": markets})


class ResearchPdfTests(unittest.TestCase):
    def test_polish_sections_explanations_and_all_market_values(self):
        forecasts, queue, events = inputs()
        coverage = {"per_league": [{"league": "Liga testowa", "total": 3,
                     "before_mapped": 1, "after_mapped": 2}]}
        original = deepcopy((forecasts, queue, events, coverage))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.pdf"
            build(forecasts, queue, {"reports": []}, path, events, coverage)
            text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
            for required in ("1. Jak czytać prognozy", "2. Pokrycie", "3. Wybrane obserwacje",
                             "4. Wszystkie prognozy", "5. Bramki", "6. Rozliczenia",
                             "niekalibrowane", "Nie są potwierdzonymi okazjami", "Zgodność kierunku",
                             "55.0–60.0%", "Żółte kartki", "Faule", "Rożne", "100 / 12 / 10",
                             "Dopasowane przed", "Dopasowane po", "Goście <test> & 0",
                             "unsupported_competition"):
                self.assertIn(required, text)
            self.assertGreater(path.stat().st_size, 1000)
        self.assertEqual((forecasts, queue, events, coverage), original)

    def test_pagination_fonts_and_content_within_page(self):
        forecasts, queue, events = inputs(5)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "long.pdf"
            build(forecasts, queue, {}, path, events)
            with pymupdf.open(path) as document:
                self.assertGreater(len(document), 2)
                self.assertEqual(len(document), len(PdfReader(path).pages))
                for index, page in enumerate(document, 1):
                    self.assertIn("Strona " + str(index), page.get_text())
                    self.assertEqual(page.get_links(), [])
                    for block in page.get_text("dict")["blocks"]:
                        for line in block.get("lines", []):
                            for span in line["spans"]:
                                self.assertGreaterEqual(span["size"], 8)
                                x0, y0, x1, y1 = span["bbox"]
                                self.assertGreaterEqual(x0, -0.1)
                                self.assertGreaterEqual(y0, -0.1)
                                self.assertLessEqual(x1, page.rect.width + .1)
                                self.assertLessEqual(y1, page.rect.height + .1)

    def test_empty_report_does_not_create_proposals(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "empty.pdf"
            build({"predictions": [], "generated_at_utc": "2035-05-01T08:00:00Z"},
                  {"fixtures": [], "missing_dates": ["2035-05-01"]}, {}, path)
            text = " ".join(page.extract_text() for page in PdfReader(path).pages)
            self.assertIn("Nie utworzono zastępczych propozycji", text)
            self.assertIn("Niepełne źródła", text)
            self.assertIn("Nie przekazano porównania pokrycia", text)

    def test_invalid_probability_never_renders(self):
        for value in (float("nan"), float("inf"), True, -0.1, 1.1, "0.6"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as td:
                forecasts, queue, events = inputs()
                forecasts["predictions"][0]["p_home"] = value
                path = Path(td) / "invalid.pdf"
                with self.assertRaisesRegex(ValueError, "pdf_invalid_probability"):
                    build(forecasts, queue, {}, path, events)
                self.assertFalse(path.exists())

    def test_non_normalized_1x2_rejected(self):
        forecasts, queue, _ = inputs()
        forecasts["predictions"][0]["p_home"] = .4
        with self.assertRaisesRegex(ValueError, "pdf_probability_sum_invalid"):
            build(forecasts, queue, {}, "/tmp/never-pdf-test.pdf")

    def test_event_complements_and_half_lines_checked(self):
        for field, value, message in (("probability", .9, "pdf_probability_sum_invalid"),
                                      ("line", 2, "pdf_non_binary_market_line")):
            with self.subTest(field=field):
                forecasts, queue, events = inputs()
                events["markets"][0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    build(forecasts, queue, {}, "/tmp/never-pdf-test.pdf", events)

    def test_unknown_fixture_and_duplicate_forecast_rejected(self):
        forecasts, queue, _ = inputs()
        with self.assertRaisesRegex(ValueError, "pdf_forecast_fixture_missing"):
            build(forecasts, {"fixtures": []}, {}, "/tmp/never-pdf-test.pdf")
        forecasts["predictions"].append(deepcopy(forecasts["predictions"][0]))
        with self.assertRaisesRegex(ValueError, "pdf_duplicate_forecast"):
            build(forecasts, queue, {}, "/tmp/never-pdf-test.pdf")

    def test_equal_highest_values_not_claimed_unique_direction(self):
        forecasts, queue, _ = inputs()
        for row in forecasts["predictions"]:
            row.update(p_home=.4, p_draw=.4, p_away=.2)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ties.pdf"
            build(forecasts, queue, {}, path)
            text = " ".join(page.extract_text() for page in PdfReader(path).pages)
            self.assertIn("najwyższe wartości są równe", text)
            self.assertNotIn("Zgodność kierunku", text)


if __name__ == "__main__":
    unittest.main()
