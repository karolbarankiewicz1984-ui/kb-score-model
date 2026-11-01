"""Actual frozen input comparisons plus negative checks of evidence boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from pypdf import PdfReader

from tests.test_multimodel_v2_adapters import (
    ARCHIVE, EXPORT, FREEZE, PITCH, PREDICTION, capture, metadata_captures, sheet_capture,
)
from multimodel_v2.adapters import adapt_api, adapt_pitchapi, adapt_sheet, load_json, read_api_run
from multimodel_v2.report_pdf import generate_three_pdfs, validate_pdf_bundle
from multimodel_v2.shadow import compare_api, three_day_readiness

AS_OF = "2026-11-01T12:21:45Z"


class ActualShadowTests(unittest.TestCase):
    def setUp(self):
        self.source, self.freeze = load_json(EXPORT), load_json(FREEZE)
        self.adapted = adapt_api(self.source, freeze_capture=self.freeze)

    def compare(self):
        return compare_api(self.source, self.adapted, freeze_capture=self.freeze, as_of=AS_OF)

    def test_same_frozen_seven_rows_match_ids_markets_quotes_top_and_statuses(self):
        result = self.compare()
        self.assertTrue(result["field_comparison_passed"])
        self.assertEqual(result["field_differences"], [])
        self.assertEqual(result["source_consistency_differences"], [])
        self.assertTrue(result["original_top_order_preserved"])
        self.assertEqual(result["fixture_ids"], ["1550169", "1550170"])
        self.assertEqual(result["native_status_counts"], result["adapter_status_counts"])
        self.assertEqual(result["exact_market_and_quote_digest_native"], result["exact_market_and_quote_digest_adapter"])

    def test_field_equality_does_not_masquerade_as_complete_shadow_pass(self):
        result = self.compare()
        self.assertFalse(result["full_shadow_passed"])
        self.assertEqual(result["original_top_rows"], 7)
        self.assertIsNone(result["strict_v2_audits"]["original_top"]["positions"])
        self.assertTrue(result["source_gate_differences"])
        self.assertIsNone(result["native_roi_pct"])
        self.assertIsNone(result["native_fixture_equal_roi_pct"])
        for summary in result["strict_v2_audits"].values():
            self.assertIsNone(summary["roi_pct"])

    def test_full_native_222_row_freeze_compared_separately_not_to_seven_row_export(self):
        source = load_json(PREDICTION)
        adapted = adapt_api(source)
        result = compare_api(source, adapted, as_of=AS_OF)
        self.assertEqual((result["native_rows"], result["adapter_rows"], result["original_top_rows"]), (222, 222, 51))
        self.assertEqual(result["field_differences"], [])
        self.assertTrue(result["original_top_order_preserved"])
        self.assertFalse(result["full_shadow_passed"])

    def test_comparing_different_input_lineages_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "input_hash_mismatch"):
            compare_api(load_json(PREDICTION), self.adapted, as_of=AS_OF)

    def test_price_line_fixture_status_score_and_top_changes_are_detected(self):
        mutations = [
            (lambda b: b["rows"][0].update(fixture_id="999"), "fixture_id"),
            (lambda b: b["rows"][0]["market_identity"].update(line="5.50000001"), "market"),
            (lambda b: b["rows"][0]["quotes"][0].update(selected_odd="9.99"), "quotes"),
            (lambda b: b["rows"][0].update(status="PLAY"), "status"),
            (lambda b: b["rows"][0].update(score=99), "score"),
            (lambda b: b["top_order"].reverse(), "original_top_order_or_content"),
        ]
        original = deepcopy(self.adapted)
        for mutate, field in mutations:
            with self.subTest(field=field):
                self.adapted = deepcopy(original)
                mutate(self.adapted)
                result = self.compare()
                self.assertIn(field, [d["field"] for d in result["field_differences"]])
                self.assertFalse(result["full_shadow_passed"])

    def test_top_contents_checked_against_original_file_not_adapter_itself(self):
        self.adapted["native_top"][0]["best_quote"]["odd"] = 999
        self.assertFalse(self.compare()["original_top_order_preserved"])

    def test_changed_original_payload_or_different_freeze_capture_rejected(self):
        self.adapted["original_payload"]["positions"][0]["line"] = 999
        with self.assertRaisesRegex(ValueError, "original_payload_mismatch"):
            self.compare()
        self.adapted = adapt_api(self.source, freeze_capture=self.freeze)
        self.freeze["capture_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "freeze_hash_mismatch"):
            self.compare()

    def test_source_freeze_quote_disagreement_detected_even_if_adapter_copies_export(self):
        payload = deepcopy(self.freeze["payload"])
        payload["picks"][0]["best_quote"]["odd"] = 999
        self.freeze = capture(payload)
        self.adapted = adapt_api(self.source, freeze_capture=self.freeze)
        result = self.compare()
        self.assertTrue(result["field_comparison_passed"])
        self.assertEqual(result["source_consistency_differences"][0]["field"], "frozen_quote")
        self.assertFalse(result["full_shadow_passed"])

    def test_reordering_identity_dictionary_does_not_create_false_market_difference(self):
        row = self.adapted["rows"][0]
        row["market_identity"] = dict(reversed(list(row["market_identity"].items())))
        self.assertTrue(self.compare()["field_comparison_passed"])

    def test_readiness_lists_each_missing_source_on_each_of_three_local_dates(self):
        run, artifacts = metadata_captures()
        api = read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)
        bundles = api["bundles"] + [adapt_sheet(sheet_capture("kb21"), "kb21"),
            adapt_sheet(sheet_capture("consensus"), "consensus"), adapt_pitchapi(load_json(PITCH))]
        ready = three_day_readiness("2026-11-01", bundles, api["evidence"], as_of=AS_OF)
        self.assertFalse(ready["can_complete_three_real_data_reports"])
        self.assertTrue(ready["can_generate_three_pdf_files"])
        for day in ready["days"]:
            self.assertEqual({b["system"] for b in day["blockers"]},
                             {"api_market", "kb21", "consensus", "pitchapi", "original_top"})
            self.assertFalse(day["complete_on_real_data"])

    def test_real_source_inventory_is_visible_in_three_valid_pdfs_without_fake_picks(self):
        run, artifacts = metadata_captures()
        api = read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)
        bundles = api["bundles"] + [adapt_sheet(sheet_capture("kb21"), "kb21"),
            adapt_sheet(sheet_capture("consensus"), "consensus"), adapt_pitchapi(load_json(PITCH))]
        before = deepcopy(bundles)
        with tempfile.TemporaryDirectory() as temporary:
            paths = generate_three_pdfs("2026-11-01", api["evidence"]["runs"], [], [], as_of=AS_OF,
                                         output_dir=Path(temporary)/"pdfs", source_bundles=bundles)
            self.assertEqual(len(validate_pdf_bundle(paths[0].parent, "2026-11-01")), 3)
            for path in paths:
                text = "\n".join(p.extract_text() for p in PdfReader(path).pages)
                self.assertIn("Odczyt rzeczywistych źródeł", text)
                self.assertIn("rejestr historyczny odczytano", text)
                self.assertNotIn("brak eksportu źródłowego", text)
                self.assertIn("BRAK ZWERYFIKOWANYCH KANDYDATUR", text)
                self.assertIn("brak pełnego tła kandydatur", " ".join(text.lower().split()))
                self.assertNotIn("Fiorentina — Atalanta", text)
                self.assertNotIn("TEST EVENT", text)
            self.assertEqual(bundles, before)

    def test_shadow_comparison_is_repeatable_and_never_changes_source(self):
        before = deepcopy((self.source, self.freeze, self.adapted))
        first, second = self.compare(), self.compare()
        self.assertEqual(first, second)
        self.assertEqual((self.source, self.freeze, self.adapted), before)
        json.dumps(first, allow_nan=False)

    def test_cli_replays_real_archives_and_emits_honest_blocked_json(self):
        run, artifacts = metadata_captures()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, payload in (("run", run["payload"]), ("artifacts", artifacts["payload"]),
                                  ("kb", sheet_capture("kb21")["payload"]),
                                  ("consensus", sheet_capture("consensus")["payload"])):
                (root / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
            process = subprocess.run([sys.executable, "-B", "-m", "multimodel_v2.shadow",
                "--archive-root", str(ARCHIVE), "--run-metadata", str(root/"run.json"),
                "--artifacts", str(root/"artifacts.json"), "--kb", str(root/"kb.json"),
                "--consensus", str(root/"consensus.json"), "--pitchapi", str(PITCH),
                "--api-prediction", str(PREDICTION), "--start", "2026-11-01", "--as-of", AS_OF],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
            result = json.loads(process.stdout)
            self.assertEqual([c["native_rows"] for c in result["comparisons"]], [7, 22, 222])
            self.assertTrue(all(c["field_comparison_passed"] for c in result["comparisons"]))
            self.assertFalse(result["full_parallel_1_to_1_complete"])
            self.assertFalse(result["readiness"]["can_complete_three_real_data_reports"])
            self.assertEqual(result["api_scans_started"], 0)


if __name__ == "__main__":
    unittest.main()
