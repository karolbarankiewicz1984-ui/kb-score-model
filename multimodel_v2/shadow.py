"""Independent native-to-adapter comparisons and real-source PDF readiness."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .adapters import (
    adapt_api, adapt_pitchapi, adapt_sheet, load_json, match_pitchapi,
    read_api_run, source_summary,
)
from .audit import build_audits
from .report_pdf import generate_three_pdfs, report_dates, validate_pdf_bundle
from .source_manifest import instant, number


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def _native_projection(payload):
    """Read source fields directly, independently of adapter output logic."""
    full = payload.get("schema") == "api-market-scan-v3"
    rows = payload["background_candidates"] if full else payload["positions"]
    projection = []
    for row in rows:
        quotes = row.get("market_data", {}).get("quotes", []) if full else [row["best_quote"]]
        projection.append({
            "fixture_id": str(row["fixture_id"]),
            "market": [str(row["fixture_id"]), row["market"], row["market_scope"],
                       str(row["team_id"]) if row["market_scope"] == "team" else None,
                       row["direction"], str(number(row["line"])), row["settlement_period"]],
            "quotes": [{"bookmaker": q.get("bookmaker"),
                        "odd": str(number(q["selected_odd" if full else "odd"])),
                        "timestamp": q.get("provider_updated_at")} for q in quotes],
            "status": row.get("final_status"), "score": row.get("final_assessment_pct"),
            "original": deepcopy(row),
        })
    return projection


def _native_audit_populations(payload, top_count):
    """Reference counts from source fields, not independently verified picks."""
    result = {"original_top": top_count, "qualifying_api": None, "fouls_under": None}
    if payload.get("schema") != "api-market-scan-v3":
        return result
    api, fouls = 0, 0
    captured = instant(payload["publication"]["captured_at_utc"])
    for row in payload["background_candidates"]:
        try:
            score = number(row.get("final_assessment_pct"))
            kickoff = instant(row.get("kickoff"))
            if captured >= kickoff:
                continue
            odds = [number(q.get("selected_odd")) for q in row.get("market_data", {}).get("quotes", [])
                    if instant(q.get("provider_updated_at")) <= captured]
            if score >= 67 and any(odd >= number("1.20") for odd in odds):
                api += 1
            if (row.get("market"), row.get("direction"), row.get("settlement_period")) == (
                    "fouls", "under", "regulation_time") and 0 <= score <= 100 and any(
                    number("1.50") <= odd <= number("2.00") for odd in odds):
                fouls += 1
        except ValueError:
            return result  # Unknown universe, never a complete-case subset.
    return dict(result, qualifying_api=api, fouls_under=fouls)


def compare_api(capture, adapted, *, freeze_capture=None, evidence=None, as_of):
    """Never compare two different runs/freezes and call that a model delta."""
    if adapted.get("source", {}).get("capture_sha256") != capture["capture_sha256"]:
        raise ValueError("shadow_input_hash_mismatch")
    if adapted.get("original_payload") != capture["payload"]:
        raise ValueError("shadow_original_payload_mismatch")
    native = _native_projection(capture["payload"])
    output = []
    for row in adapted["rows"]:
        identity = row["market_identity"]
        output.append({"fixture_id": row["fixture_id"],
            "market": [identity[k] for k in ("fixture_id", "market", "market_scope", "team_id", "direction", "line", "settlement_period")]
                       if identity else None,
            "quotes": [{"bookmaker": q["bookmaker"], "odd": q["selected_odd"],
                        "timestamp": q["provider_updated_at"]} for q in row["quotes"]],
            "status": row["status"], "score": row["score"], "original": deepcopy(row["original"])})
    differences = []
    for index in range(max(len(native), len(output))):
        if index >= len(native) or index >= len(output):
            differences.append({"index": index, "field": "row_count", "native_present": index < len(native),
                                "adapter_present": index < len(output)})
            continue
        for field in ("fixture_id", "market", "quotes", "status", "score", "original"):
            if native[index][field] != output[index][field]:
                differences.append({"index": index, "field": field,
                                    "native": native[index][field], "adapter": output[index][field]})
    full = adapted["background_complete"]
    if not full and freeze_capture is None and adapted.get("freeze_source"):
        freeze_capture = load_json(adapted["freeze_source"]["locator"])
    if freeze_capture and freeze_capture["capture_sha256"] != adapted.get("freeze_source", {}).get("capture_sha256"):
        raise ValueError("shadow_freeze_hash_mismatch")
    native_top = capture["payload"].get("top_positions") if full else (
        freeze_capture["payload"].get("picks") if freeze_capture else None)
    top_preserved = native_top == adapted["native_top"]
    source_differences = []
    if isinstance(native_top, list):
        expected_order = []
        for top in native_top:
            matches = [i for i, row in enumerate(native) if all(row["original"].get(k) == top.get(k)
                       for k in ("fixture_id", "team_id", "market", "market_scope", "direction", "line"))]
            expected_order.extend(matches if len(matches) == 1 else [])
            if len(matches) == 1 and not full:
                source_row = native[matches[0]]
                for field in ("kickoff", "home", "away", "selection", "final_assessment_pct"):
                    if field in top and top[field] != source_row["original"].get(field):
                        source_differences.append({"top_index": len(expected_order) - 1, "field": field})
                locked = top.get("best_quote") or {}
                try:
                    matching_quotes = [q for q in source_row["quotes"] if q["bookmaker"] == locked.get("bookmaker")
                                       and number(q["odd"]) == number(locked.get("odd"))]
                except ValueError:
                    matching_quotes = []
                if not matching_quotes:
                    source_differences.append({"top_index": len(expected_order) - 1, "field": "frozen_quote"})
        top_preserved = top_preserved and expected_order == adapted["top_order"]
    if not top_preserved:
        differences.append({"field": "original_top_order_or_content"})

    e = evidence or {"runs": [], "snapshots": [], "settlements": []}
    audits = build_audits(adapted["dates"][0], e["runs"], e["snapshots"], e["settlements"], as_of=as_of)
    summaries = {name: {"status": cohort["status"], **cohort["metrics"]}
                 for name, cohort in audits["cohorts"].items()}
    source_count = len(native_top) if isinstance(native_top, list) else None
    populations = _native_audit_populations(capture["payload"], source_count)
    return {
        "mode": "historical_frozen_input_replay", "source": deepcopy(adapted["source"]),
        "freeze": deepcopy(adapted["freeze"]), "native_schema": adapted["native_schema"],
        "native_rows": len(native), "adapter_rows": len(output),
        "fixture_ids": sorted({r["fixture_id"] for r in native}),
        "native_status_counts": dict(Counter(r["status"] for r in native)),
        "adapter_status_counts": dict(Counter(r["status"] for r in output)),
        "exact_market_and_quote_digest_native": _digest(native),
        "exact_market_and_quote_digest_adapter": _digest(output),
        "field_differences": differences, "field_comparison_passed": not differences,
        "source_consistency_differences": source_differences,
        "original_top_rows": source_count, "original_top_order_preserved": top_preserved,
        "declared_candidates": adapted["declared_candidates"], "background_complete": full,
        "strict_v2_verified_rows": adapted["verified_rows"],
        "strict_v2_audits": summaries,
        "native_audit_field_populations_unverified": populations,
        "native_roi_pct": None, "native_fixture_equal_roi_pct": None,
        "settlement_inputs": "not_supplied_for_this_freeze",
        "source_gate_differences": [{"field": name + ".positions", "native_field_count": count,
                                     "strict_v2": summaries[name]["positions"],
                                     "reason": "missing_verified_full_source_or_provenance"}
                                    for name, count in populations.items() if count != summaries[name]["positions"]],
        "blockers": deepcopy(adapted["blockers"]),
        "full_shadow_passed": not differences and not source_differences and not adapted["blockers"]
            and full and all(c["status"] == "complete" for c in audits["cohorts"].values()),
    }


def three_day_readiness(start_date, bundles, evidence, *, as_of):
    instant(as_of)
    days = []
    for day in report_dates(start_date):
        systems = {}
        blockers = []
        for system in ("api_market", "kb21", "consensus", "pitchapi"):
            captures = [b for b in bundles if b["system"] == system]
            summaries = [source_summary(b, day, as_of=as_of) for b in captures]
            rows = [r for b in captures for r in b["rows"] if r.get("date") == day]
            complete = any(s["complete_for_date"] for s in summaries)
            latest = max((b.get("latest_date") for b in captures if b.get("latest_date")), default=None)
            reasons = sorted({g for s in summaries for g in s["blockers"]})
            if not captures:
                reasons.append("source_unavailable")
            if not rows:
                reasons.append("no_source_rows_for_date")
            if system == "api_market":
                complete = complete and any(b.get("background_complete") and b.get("date_status") == "ok"
                                           and b.get("run_conclusion") == "success" for b in captures)
            systems[system] = {"readable_captures": len(captures), "rows_for_date": len(rows),
                               "latest_date": latest, "complete": complete, "blockers": sorted(set(reasons))}
            if not complete:
                blockers.append({"system": system, "reasons": sorted(set(reasons))})
        audits = build_audits(day, evidence["runs"], evidence["snapshots"], evidence["settlements"], as_of=as_of)
        if audits["cohorts"]["original_top"]["status"] != "complete":
            blockers.append({"system": "original_top", "reasons": ["no_verified_original_freeze_for_date"]})
        days.append({"date": day, "complete_on_real_data": not blockers,
                     "sources": systems, "blockers": blockers})
    return {"schema": "multimodel-v2-real-source-readiness-v1", "as_of": as_of,
            "can_generate_three_pdf_files": True,
            "can_complete_three_real_data_reports": all(d["complete_on_real_data"] for d in days), "days": days}


def run_shadow(archive_root, run_file, artifacts_file, kb_file, consensus_file, pitch_files, *, start_date, as_of, api_predictions=()):
    archive = read_api_run(archive_root, run_capture=load_json(run_file), artifacts_capture=load_json(artifacts_file))
    kb = adapt_sheet(load_json(kb_file), "kb21")
    consensus = adapt_sheet(load_json(consensus_file), "consensus")
    pitch = [adapt_pitchapi(load_json(path)) for path in pitch_files]
    bundles = archive["bundles"] + [kb, consensus] + pitch
    comparisons = []
    for api in archive["bundles"]:
        capture = load_json(api["source"]["locator"])
        # Replay at the original completed run's cutoff. This is an audit,
        # never a newly issued historical pre-match prediction.
        comparisons.append(compare_api(capture, api, evidence=archive["evidence"],
                                       as_of=archive["evidence"]["runs"][0]["updated_at"]))
    for path in api_predictions:
        capture = load_json(path)
        api = adapt_api(capture)
        api["blockers"].append("run_binding_missing")
        bundles.append(api)
        # This is a separate input lineage, NOT the multiday artifact's run.
        comparisons.append(compare_api(capture, api, as_of=as_of))
    pitch_matches = {}
    for api in archive["bundles"]:
        for row in api["rows"]:
            match = match_pitchapi(row, pitch)
            pitch_matches[f"{row['date']}:{row['fixture_id']}"] = match["native_fixture_id"] if match else None
    readiness = three_day_readiness(start_date, bundles, archive["evidence"], as_of=as_of)
    report = {"schema": "multimodel-v2-real-shadow-v1", "as_of": as_of,
              "comparisons": comparisons, "readiness": readiness,
              "pitchapi_exact_matches": pitch_matches,
              "source_inventory": [{"system": b["system"], "source": b["source"], "rows": len(b["rows"]),
                                    "latest_date": b["latest_date"], "verified_rows": b["verified_rows"],
                                    "spreadsheet_url": b.get("spreadsheet_url"), "read_range": b.get("read_range"),
                                    "spreadsheet_timezone": b.get("spreadsheet_timezone"),
                                    "artifact_digest_from_metadata": b.get("artifact_digest"),
                                    "artifact_bytes_digest_verified": b.get("artifact_bytes_digest_verified"),
                                    "blockers": b["blockers"]} for b in bundles],
              "full_parallel_1_to_1_complete": all(c["full_shadow_passed"] for c in comparisons)
                    and readiness["can_complete_three_real_data_reports"],
              "models_modified": False, "register_writes": False, "api_scans_started": 0}
    return report, bundles, archive["evidence"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument("--run-metadata", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--kb", required=True, type=Path)
    parser.add_argument("--consensus", required=True, type=Path)
    parser.add_argument("--pitchapi", nargs="*", type=Path, default=[])
    parser.add_argument("--api-prediction", nargs="*", type=Path, default=[])
    parser.add_argument("--start", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--pdf-output", type=Path)
    args = parser.parse_args(argv)
    report, bundles, evidence = run_shadow(args.archive_root, args.run_metadata, args.artifacts, args.kb,
                                         args.consensus, args.pitchapi, start_date=args.start, as_of=args.as_of,
                                         api_predictions=args.api_prediction)
    if args.pdf_output:
        paths = generate_three_pdfs(args.start, evidence["runs"], evidence["snapshots"], evidence["settlements"],
                                    as_of=args.as_of, output_dir=args.pdf_output, source_bundles=bundles)
        report["pdf_validation"] = validate_pdf_bundle(paths[0].parent, args.start)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
