"""Read-only adapter checks, including existing immutable real API/Pitch files."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from multimodel_v2.adapters import (
    adapt_api, adapt_pitchapi, adapt_sheet, api_evidence, load_json,
    match_pitchapi, read_api_run, source_summary,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive/multimodel/api_market/runs/40906734194"
EXPORT = ARCHIVE / "v2/API_MARKET_SCAN_PLAYABLE_2026-10-29.json"
FREEZE = ARCHIVE / "audit_input/2026-10-29.json"
PREDICTION = ROOT / "data/api_football/predictions/2026-10-29/161916070596-866b43bbe577eccc.json"
PITCH = ROOT / "data/pitchapi/prematch/2026-10-29.json"


def capture(payload):
    """In-memory test capture; never written to source archives/registers."""
    return {"locator": "in-memory-test-input", "capture_sha256": hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest(), "payload": deepcopy(payload)}


def metadata_captures():
    run = load_json(ARCHIVE / "run_metadata.json")
    payload = deepcopy(run["payload"])
    # Actual path observed from the GitHub run; archived metadata omits it.
    payload["path"] = ".github/workflows/api-market-multiday-experiment.yml"
    artifacts = {"artifacts": [{"id": 12911681942, "name": "api-market-multiday-experiment",
        "expired": False, "workflow_run": {"id": payload["id"], "head_sha": payload["head_sha"]}}]}
    return capture(payload), capture(artifacts)


def sheet_capture(system):
    # Minimal test rows in the observed native header formats. Not forecasts.
    if system == "kb21":
        headers = ["ID", "Data wydarzenia", "Wydarzenie", "Rynek", "Typ", "Kurs", "P(model)", "KB Score", "Decyzja"]
        values = [1, "2026-08-15", "TEST EVENT", "Gole drużyny gości", "TEST UNDER", 2, 0.57, 80, "KB PLAY"]
        tab, zone = "Rejestr", "Europe/Warsaw"
    else:
        headers = ["Date", "Analysis Time", "Event", "Market", "Pick", "Category", "Odds 11:30", "P(HIT)"]
        values = [46252, "11:30", "TEST EVENT", "Draw No Bet", "TEST DNB", "VALUE", 2.05, None]
        tab, zone = "Selections", "America/Los_Angeles"
    return capture({"metadata": {"spreadsheetId": "test-only-sheet", "properties": {"timeZone": zone},
                    "sheets": [{"properties": {"title": tab}}]},
                    "range": {"range": f"{tab}!A1:Z2", "values": [headers, values]},
                    "retrieved_at": "2026-11-01T12:21:45Z"})


class ApiAdapterTests(unittest.TestCase):
    def test_real_export_retains_seven_rows_top_order_quotes_statuses(self):
        source, frozen = load_json(EXPORT), load_json(FREEZE)
        result = adapt_api(source, freeze_capture=frozen)
        self.assertEqual(len(result["rows"]), 7)
        self.assertEqual(result["top_order"], list(range(7)))
        self.assertEqual(result["native_top"], frozen["payload"]["picks"])
        for old, new in zip(source["payload"]["positions"], result["rows"]):
            self.assertEqual(new["original"], old)
            self.assertEqual(new["status"], old["final_status"])
            self.assertEqual(new["quotes"][0]["selected_odd"], str(old["best_quote"]["odd"]))

    def test_partial_export_never_becomes_complete_222_candidate_background(self):
        bundle = adapt_api(load_json(EXPORT), freeze_capture=load_json(FREEZE))
        self.assertFalse(bundle["background_complete"])
        self.assertEqual(bundle["declared_candidates"], 222)
        self.assertIn("full_background_not_archived", bundle["blockers"])
        self.assertEqual(bundle["verified_rows"], 0)
        self.assertEqual(api_evidence(bundle, {"id": 1})["snapshots"], [])

    def test_no_quote_identity_or_publication_id_is_invented(self):
        bundle = adapt_api(load_json(EXPORT), freeze_capture=load_json(FREEZE))
        self.assertIsNone(bundle["freeze"]["id"])
        self.assertTrue(all(q["market_identity"] is None for r in bundle["rows"] for q in r["quotes"]))
        self.assertIn("independent_quote_identity_missing", bundle["blockers"])

    def test_full_original_freeze_preserves_222_rows_and_51_top_entries(self):
        source = load_json(PREDICTION)
        bundle = adapt_api(source)
        self.assertTrue(bundle["background_complete"])
        self.assertEqual(len(bundle["rows"]), 222)
        self.assertEqual(len(bundle["native_top"]), 51)
        self.assertEqual(bundle["freeze"]["id"], "161916070596-866b43bbe577eccc")
        self.assertEqual(bundle["original_payload"], source["payload"])

    def test_separate_prediction_cannot_be_bound_to_unrelated_archive_run(self):
        bundle = adapt_api(load_json(PREDICTION))
        run, _ = metadata_captures()
        with self.assertRaisesRegex(ValueError, "run_binding_missing"):
            api_evidence(bundle, run["payload"])

    def test_match_scope_canonicalization_preserves_original_team_anchor(self):
        bundle = adapt_api(load_json(PREDICTION))
        rows = [r for r in bundle["rows"] if r["original"]["market_scope"] == "match"]
        self.assertTrue(rows)
        for row in rows:
            self.assertIsNone(row["market_identity"]["team_id"])
            self.assertIsNotNone(row["original"]["team_id"])

    def test_read_run_uses_actual_metadata_and_never_repairs_archive(self):
        run, artifacts = metadata_captures()
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in ARCHIVE.rglob("*") if p.is_file()}
        result = read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)
        self.assertEqual([len(b["rows"]) for b in result["bundles"]], [7, 22])
        self.assertEqual(result["evidence"]["snapshots"], [])
        self.assertEqual(len(result["evidence"]["runs"][0]["date_statuses"]), 2)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_other_run_sha_or_artifact_binding_rejected(self):
        run, artifacts = metadata_captures()
        run["payload"]["head_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "run_metadata_mismatch"):
            read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)
        run, artifacts = metadata_captures()
        artifacts["payload"]["artifacts"][0]["workflow_run"]["id"] = 123
        with self.assertRaisesRegex(ValueError, "artifact_run_mismatch"):
            read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)

    def test_expired_artifact_not_promoted_from_archived_local_copy(self):
        run, artifacts = metadata_captures()
        artifacts["payload"]["artifacts"][0]["expired"] = True
        with self.assertRaisesRegex(ValueError, "missing_or_ambiguous"):
            read_api_run(ARCHIVE, run_capture=run, artifacts_capture=artifacts)

    def test_freeze_of_another_date_rejected(self):
        freeze = load_json(FREEZE)
        freeze["payload"]["date"] = "2026-10-30"
        with self.assertRaisesRegex(ValueError, "freeze_source_date"):
            adapt_api(load_json(EXPORT), freeze_capture=freeze)

    def test_price_mismatch_between_frozen_top_and_export_is_explicit(self):
        frozen = load_json(FREEZE)
        frozen["payload"]["picks"][0]["best_quote"]["odd"] = 9
        bundle = adapt_api(load_json(EXPORT), freeze_capture=frozen)
        self.assertIn("freeze_quote_mismatch", bundle["blockers"])
        self.assertEqual(bundle["rows"][0]["quotes"][0]["selected_odd"], "1.35")

    def test_bad_line_and_missing_price_are_not_completed(self):
        source = load_json(EXPORT)
        source["payload"]["positions"][0]["line"] = None
        source["payload"]["positions"][1]["best_quote"]["odd"] = None
        bundle = adapt_api(source, freeze_capture=load_json(FREEZE))
        self.assertIsNone(bundle["rows"][0]["market_identity"])
        self.assertIsNone(bundle["rows"][1]["quotes"][0]["selected_odd"])


class SheetAdapterTests(unittest.TestCase):
    def test_kb_probabilities_decisions_and_odds_are_copied_not_recomputed(self):
        source = sheet_capture("kb21")
        before = deepcopy(source)
        bundle = adapt_sheet(source, "kb21")
        row = bundle["rows"][0]
        self.assertEqual((row["probability_original"], row["odds_original"], row["status"]), (0.57, 2, "KB PLAY"))
        self.assertFalse(row["verified_prematch"])
        self.assertIsNone(row["fixture_id"])
        self.assertIsNone(row["market_identity"])
        self.assertEqual(source, before)

    def test_consensus_serial_date_and_source_timezone_do_not_create_kickoff(self):
        bundle = adapt_sheet(sheet_capture("consensus"), "consensus")
        row = bundle["rows"][0]
        self.assertEqual(row["date"], "2026-08-18")
        self.assertEqual(bundle["spreadsheet_timezone"], "America/Los_Angeles")
        self.assertIsNone(row["kickoff"])
        self.assertIsNone(row["probability_original"])
        self.assertEqual(row["status"], "VALUE")
        self.assertFalse(row["verified_prematch"])

    def test_closing_odds_and_result_are_not_substitutes_for_frozen_quote(self):
        source = sheet_capture("consensus")
        source["payload"]["range"]["values"][0] += ["Closing Odds", "Result"]
        source["payload"]["range"]["values"][1] += [10, "WIN"]
        row = adapt_sheet(source, "consensus")["rows"][0]
        self.assertEqual(row["odds_original"], 2.05)
        self.assertIn("quote_timestamp_missing", row["blockers"])

    def test_wrong_tab_unknown_headers_and_duplicate_headers_fail(self):
        source = sheet_capture("kb21")
        source["payload"]["range"]["range"] = "Dashboard!A1:Z2"
        with self.assertRaisesRegex(ValueError, "wrong_source_tab"):
            adapt_sheet(source, "kb21")
        source = sheet_capture("kb21")
        source["payload"]["range"]["values"][0].append("ID")
        with self.assertRaisesRegex(ValueError, "duplicate_sheet_headers"):
            adapt_sheet(source, "kb21")

    def test_original_cells_including_extra_columns_are_retained(self):
        source = sheet_capture("kb21")
        source["payload"]["range"]["values"][1].append("unheaded original value")
        bundle = adapt_sheet(source, "kb21")
        self.assertEqual(bundle["rows"][0]["original_cells"], source["payload"]["range"]["values"][1])
        self.assertFalse(source_summary(bundle, "2026-11-01")["complete_for_date"])


class PitchAdapterTests(unittest.TestCase):
    def test_real_historical_context_preserves_ids_and_all_xg_values(self):
        source = load_json(PITCH)
        before = deepcopy(source)
        bundle = adapt_pitchapi(source)
        self.assertEqual(len(bundle["rows"]), 33)
        self.assertEqual(bundle["verified_rows"], 30)
        for original, row in zip(source["payload"]["fixtures"], bundle["rows"]):
            self.assertEqual(row["original"], original)
            self.assertEqual(row["native_fixture_id"], original["pitch_match_id"])
            self.assertIsNone(row["fixture_id"])
            self.assertIsNone(row["market_identity"])
        self.assertEqual(source, before)

    def test_history_at_or_after_snapshot_cannot_validate_context(self):
        source = load_json(PITCH)
        source["payload"]["fixtures"][0]["home_recent"]["samples"][0]["kickoff_utc"] = source["payload"]["snapshot_utc"]
        row = adapt_pitchapi(source)["rows"][0]
        self.assertFalse(row["verified_prematch"])
        self.assertIn("pitchapi_history_lookahead", row["blockers"])

    def test_exact_real_fixture_join_and_no_hour_window_or_fuzzy_alias(self):
        api = adapt_api(load_json(EXPORT), freeze_capture=load_json(FREEZE))["rows"][0]
        pitch = adapt_pitchapi(load_json(PITCH))
        match = match_pitchapi(api, [pitch])
        self.assertIsNotNone(match)
        self.assertEqual(match["native_fixture_id"], "m_0h3uIF")
        api["kickoff"] = "2026-10-29T20:45:01+01:00"
        self.assertIsNone(match_pitchapi(api, [pitch]))
        api["kickoff"] = "2026-10-29T20:45:00+01:00"
        api["home"] = "ACF Fiorentina"
        self.assertIsNone(match_pitchapi(api, [pitch]))

    def test_ambiguous_context_join_is_not_guessed(self):
        api = adapt_api(load_json(EXPORT), freeze_capture=load_json(FREEZE))["rows"][0]
        pitch = adapt_pitchapi(load_json(PITCH))
        self.assertIsNone(match_pitchapi(api, [pitch, deepcopy(pitch)]))

    def test_future_capture_not_available_to_historical_cutoff(self):
        pitch = adapt_pitchapi(load_json(PITCH))
        summary = source_summary(pitch, "2026-10-29", as_of="2026-10-28T20:00:00Z")
        self.assertFalse(summary["available_as_of"])
        self.assertEqual(summary["verified_rows_for_date"], 0)
        self.assertIn("source_not_verified_available_at_cutoff", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
