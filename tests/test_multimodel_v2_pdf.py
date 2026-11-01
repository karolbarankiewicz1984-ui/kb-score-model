"""Real PDF parser/geometry checks; populated examples are TEST DATA only."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import fitz
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, A5
from reportlab.pdfgen import canvas

from tests.test_multimodel_v2_audit import frozen_evidence, make_row
from tests.test_multimodel_v2_provenance import CUTOFF, DAY
from multimodel_v2 import report_pdf
from multimodel_v2.report_pdf import (
    build_daily_report, generate_three_pdfs, report_dates, validate_pdf, validate_pdf_bundle,
)


class ThreePdfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.output = self.root / "three-pdfs"

    def tearDown(self):
        self.temporary.cleanup()

    def generate(self, runs=None, snapshots=None, results=None, **kwargs):
        return generate_three_pdfs(DAY, runs or [], snapshots or [], results or [],
                                   as_of=CUTOFF, output_dir=self.output, **kwargs)

    def test_exactly_three_existing_separate_a5_pdfs_with_missing_sources(self):
        paths = self.generate()
        self.assertEqual([p.name for p in paths], [f"MULTIMODEL_{d}.pdf" for d in report_dates(DAY)])
        self.assertEqual(set(self.output.iterdir()), set(paths))
        for path, day in zip(paths, report_dates(DAY)):
            with self.subTest(day=day):
                self.assertGreater(path.stat().st_size, 10000)
                reader = PdfReader(path, strict=True)  # independent parser
                self.assertEqual(len(reader.pages), 2)
                self.assertAlmostEqual(float(reader.pages[0].mediabox.width), A5[0], places=2)
                self.assertAlmostEqual(float(reader.pages[0].mediabox.height), A5[1], places=2)
                text = "\n".join(page.extract_text() for page in reader.pages)
                self.assertIn("BRAK ZWERYFIKOWANYCH KANDYDATUR", text)
                self.assertIn("BRAK ŹRÓDŁA", text)
                self.assertIn("KB Score: brak aktualnej prognozy", text)
                self.assertIn("Konsensus: brak aktualnej prognozy", text)
                self.assertIn("PitchAPI: brak zweryfikowanego kontekstu", text)
                self.assertIn("ROI: niedostępne", text)
                self.assertNotIn("ROI: 0", text)
                self.assertTrue(validate_pdf(path, day)["validated"])

    def test_first_page_has_fouls_under_and_unicode_in_both_parsers(self):
        runs, snapshots = frozen_evidence()
        snapshots[0]["background_candidates"][0]["final_assessment_pct"] = 55
        snapshots[0]["top_positions"] = deepcopy(snapshots[0]["background_candidates"])
        path = self.generate(runs, snapshots)[0]
        text = PdfReader(path).pages[0].extract_text()
        self.assertIn("FAULE UNDER", text)
        self.assertIn("EKSPERYMENT/POZA PROGIEM/NIE PLAY", text)
        self.assertIn("Gospodarze", text)
        self.assertIn("Goście", text)
        self.assertIn("UNDER 13.5", text)
        self.assertIn("RecordedBook", text)
        self.assertIn("1.75", text)
        self.assertNotIn("\ufffd", text)

    def test_fixture_events_are_strictly_separated_between_local_dates(self):
        runs, original = frozen_evidence()
        snapshots = []
        for index, day in enumerate(report_dates(DAY)):
            snapshot = deepcopy(original[0])
            snapshot["date"] = day
            snapshot["publication"]["id"] = f"test-only-freeze-{index}"
            row = snapshot["background_candidates"][0]
            row.update(home=f"SENTINEL_DAY_{index}", kickoff=f"{day}T20:00:00Z")
            snapshot["top_positions"] = [deepcopy(row)]
            snapshots.append(snapshot)
            if index:
                runs[0]["date_statuses"].append({"date": day, "status": "ok", "artifact_name": snapshot["artifact_name"]})
        paths = self.generate(runs, snapshots)
        for index, path in enumerate(paths):
            text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
            self.assertIn(f"SENTINEL_DAY_{index}", text)
            for other in set(range(3)) - {index}:
                self.assertNotIn(f"SENTINEL_DAY_{other}", text)

    def test_multiday_two_day_source_does_not_fabricate_third_day(self):
        runs, snapshots = frozen_evidence()
        second = deepcopy(snapshots[0])
        second["date"] = "2026-11-02"
        second["background_candidates"][0]["kickoff"] = "2026-11-02T20:00:00Z"
        second["top_positions"] = deepcopy(second["background_candidates"])
        snapshots.append(second)
        runs[0]["date_statuses"].append({"date": "2026-11-02", "status": "ok", "artifact_name": second["artifact_name"]})
        paths = self.generate(runs, snapshots)
        text = "\n".join(page.extract_text() for page in PdfReader(paths[2]).pages)
        self.assertIn("BRAK ZWERYFIKOWANYCH KANDYDATUR", text)
        self.assertNotIn("RecordedBook", text)

    def test_many_positions_paginate_without_losing_last_market_or_original_rank(self):
        runs, snapshots = frozen_evidence()
        rows = [make_row(snapshots[0], fid=1, line=f"{10 + i}.5", score=70 + i) for i in range(14)]
        snapshots[0]["background_candidates"] = rows
        snapshots[0]["top_positions"] = deepcopy(rows)
        path = self.generate(runs, snapshots)[0]
        with fitz.open(path) as doc:
            self.assertGreater(len(doc), 6)
            for index, page in enumerate(doc):
                self.assertIn(f"Strona {index + 1} / {len(doc)}", page.get_text())
            text = "\n".join(p.get_text() for p in doc)
        self.assertIn("UNDER 23.5", text)
        self.assertIn("14.", text)
        self.assertIn("Aneks · pozostałe pozycje oryginalnego TOP", text)
        self.assertTrue(validate_pdf(path, DAY)["validated"])

    def test_fonts_embedded_and_all_visible_text_at_least_six_points(self):
        path = self.generate()[0]
        with fitz.open(path) as doc:
            for page in doc:
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            self.assertGreaterEqual(span["size"], 6)
                            self.assertTrue(span["font"].startswith("DejaVuSans"))
                for font in page.get_fonts():
                    if "DejaVuSans" in font[3]:
                        self.assertTrue(doc.extract_font(font[0])[3])

    def test_untrusted_strings_are_text_and_cannot_create_false_links(self):
        runs, snapshots = frozen_evidence()
        row = snapshots[0]["background_candidates"][0]
        row["home"] = '<link href="https://invalid.example/fake.pdf">Żółć & źródło</link>'
        snapshots[0]["top_positions"] = [deepcopy(row)]
        path = self.generate(runs, snapshots)[0]
        with fitz.open(path) as doc:
            for page in doc:
                self.assertEqual(page.get_links(), [])
        for page in PdfReader(path).pages:
            self.assertFalse(page.get("/Annots"))

    def test_no_active_candidates_or_retroactive_forecasts_after_kickoff(self):
        runs, snapshots = frozen_evidence()
        report = build_daily_report(DAY, runs, snapshots, [], as_of="2026-11-01T23:00:00Z")
        self.assertEqual(report["watchlist"]["candidates"], [])
        self.assertEqual(report["upcoming_api"], [])
        self.assertEqual(report["audits"]["cohorts"]["original_top"]["metrics"]["positions"], 1)
        paths = generate_three_pdfs(DAY, runs, snapshots, [], as_of="2026-11-01T23:00:00Z", output_dir=self.output)
        text = "\n".join(page.extract_text() for page in PdfReader(paths[0]).pages)
        self.assertIn("Aneks audytu historycznego", text)
        self.assertIn("nierozliczone", text)
        self.assertNotIn("Oryginalny TOP · przed meczem", text)

    def test_wrong_local_kickoff_day_never_appears_as_candidate(self):
        runs, snapshots = frozen_evidence()
        row = snapshots[0]["background_candidates"][0]
        row.update(home="FORBIDDEN_WRONG_DAY_FIXTURE", kickoff="2026-11-01T23:30:00Z")
        snapshots[0]["top_positions"] = [deepcopy(row)]
        paths = self.generate(runs, snapshots)
        text = "\n".join(page.extract_text() for page in PdfReader(paths[0]).pages)
        self.assertNotIn("FORBIDDEN_WRONG_DAY_FIXTURE", text)
        self.assertIn("data meczu w Warszawie nie odpowiada dacie raportu", text)

    def test_local_date_planner_works_across_dst_month_and_year_boundaries(self):
        for start, expected in (
            ("2026-03-28", ["2026-03-28", "2026-03-29", "2026-03-30"]),
            ("2026-10-24", ["2026-10-24", "2026-10-25", "2026-10-26"]),
            ("2026-12-31", ["2026-12-31", "2027-01-01", "2027-01-02"]),
        ):
            with self.subTest(start=start):
                self.assertEqual(report_dates(start), expected)

    def test_bundle_validator_rejects_missing_extra_or_misnamed_files(self):
        paths = self.generate()
        paths[2].rename(self.output / "wrong.pdf")
        with self.assertRaisesRegex(ValueError, "exactly_three"):
            validate_pdf_bundle(self.output, DAY)
        (self.output / "wrong.pdf").rename(paths[2])
        (self.output / "fourth.pdf").write_bytes(paths[0].read_bytes())
        with self.assertRaisesRegex(ValueError, "exactly_three"):
            validate_pdf_bundle(self.output, DAY)

    def test_pdf_validator_rejects_missing_corrupt_and_wrong_date_files(self):
        with self.assertRaisesRegex(ValueError, "missing_or_invalid_pdf"):
            validate_pdf(self.output / "absent.pdf", DAY)
        bad = self.root / "bad.pdf"
        bad.write_bytes(b"%PDF-not-a-real-document")
        with self.assertRaises(ValueError):
            validate_pdf(bad, DAY)
        path = self.generate()[0]
        with self.assertRaisesRegex(ValueError, "date_or_pagination"):
            validate_pdf(path, "2026-11-02")

    def test_validator_rejects_a4_and_too_small_font(self):
        a4 = self.root / "a4.pdf"
        document = canvas.Canvas(str(a4), pagesize=A4)
        for _ in range(2):
            document.drawString(40, 700, "Not A5")
            document.showPage()
        document.save()
        with self.assertRaisesRegex(ValueError, "pdf_not_a5"):
            validate_pdf(a4, DAY)
        styles = report_pdf._styles()
        styles["small"].fontSize = 5
        with patch.object(report_pdf, "_styles", return_value=styles), self.assertRaisesRegex(ValueError, "font_invalid"):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_missing_dejavu_is_error_not_silent_font_fallback(self):
        with self.assertRaisesRegex(ValueError, "Missing DejaVu"):
            self.generate(font_dir=self.root / "missing-fonts")
        self.assertFalse(self.output.exists())

    def test_no_existing_files_are_overwritten_and_production_paths_are_blocked(self):
        self.output.mkdir()
        original = self.output / "original.pdf"
        original.write_bytes(b"immutable sentinel")
        with self.assertRaisesRegex(ValueError, "must_be_empty"):
            self.generate()
        self.assertEqual(original.read_bytes(), b"immutable sentinel")
        protected = Path(report_pdf.__file__).resolve().parents[1] / "archive" / "never-created-test-output"
        with self.assertRaisesRegex(ValueError, "protected_production"):
            generate_three_pdfs(DAY, [], [], [], as_of=CUTOFF, output_dir=protected)
        self.assertFalse(protected.exists())

    def test_empty_existing_output_directory_is_supported(self):
        self.output.mkdir()
        self.assertEqual(len(self.generate()), 3)

    def test_second_pdf_failure_publishes_no_partial_bundle_or_false_paths(self):
        render = report_pdf._render_pdf
        calls = []
        def fail_second(report, path, **kwargs):
            calls.append(path)
            if len(calls) == 2:
                raise RuntimeError("test rendering failure")
            return render(report, path, **kwargs)
        with patch.object(report_pdf, "_render_pdf", side_effect=fail_second), self.assertRaises(RuntimeError):
            self.generate()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_input_runs_sources_freezes_and_n_remain_unchanged(self):
        runs, snapshots = frozen_evidence()
        snapshots[0]["N"] = 678
        before = deepcopy((runs, snapshots))
        self.generate(runs, snapshots)
        self.assertEqual((runs, snapshots), before)

    def test_cli_returns_only_valid_existing_files(self):
        process = subprocess.run([sys.executable, "-B", "-m", "multimodel_v2.report_pdf",
            "--start", DAY, "--as-of", CUTOFF, "--output", str(self.output)],
            capture_output=True, text=True, check=True, cwd=Path(__file__).resolve().parents[1])
        result = json.loads(process.stdout)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(Path(item["path"]).is_file() and item["validated"] for item in result))


if __name__ == "__main__":
    unittest.main()
