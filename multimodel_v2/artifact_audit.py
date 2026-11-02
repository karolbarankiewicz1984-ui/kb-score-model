"""Inspect existing downloaded source ZIPs without extracting into archives.

The artifact digest authenticates captured bytes against supplied GitHub
metadata. It does not create native publication IDs or independent quotes.
"""
from collections import Counter
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from .adapters import adapt_api, adapt_pitchapi, adapt_sheet, load_json, match_pitchapi
from .report_pdf import generate_three_pdfs, report_dates, validate_pdf_bundle
from .shadow import compare_api, three_day_readiness
from .source_manifest import WARSAW, instant, number


def read_artifact(path, run, artifact):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    origin = artifact.get("workflow_run") or {}
    if (str(origin.get("id")) != str(run.get("id")) or origin.get("head_sha") != run.get("head_sha")
            or artifact.get("expired") is not False):
        raise ValueError("artifact_run_mismatch_or_expired")
    if (artifact.get("digest") != "sha256:" + digest
            or artifact.get("size_in_bytes") != len(raw)):
        raise ValueError("artifact_bytes_mismatch")
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("artifact_too_large")
    files = {}
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(i.file_size for i in infos) > 64 * 1024 * 1024:
            raise ValueError("artifact_expansion_limit")
        seen = set()
        for info in infos:
            name = info.filename
            posix = PurePosixPath(name)
            if (not name or posix.is_absolute() or ".." in posix.parts or "\\" in name
                    or str(posix) != name.rstrip("/") or name in seen
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError("unsafe_or_duplicate_artifact_member")
            seen.add(name)
            if not info.is_dir():
                files[name] = archive.read(info)
    return {"run": deepcopy(run), "artifact": deepcopy(artifact), "files": files,
            "manifest": {"artifact_id": artifact["id"], "run_id": run["id"],
                         "zip_sha256": digest, "zip_size": len(raw), "digest_verified": True,
                         "entries": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                                     for name, data in sorted(files.items())]}}


def _capture(archive, member):
    raw = archive["files"][member]
    return {"locator": f"github-artifact:{archive['manifest']['artifact_id']}:{member}",
            "capture_sha256": hashlib.sha256(raw).hexdigest(), "payload": json.loads(raw)}


def _pdf_info(raw):
    import pymupdf
    from pypdf import PdfReader
    with pymupdf.open(stream=raw, filetype="pdf") as doc:
        sizes = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc]
        fonts = [span["size"] for p in doc for block in p.get_text("dict")["blocks"]
                 for line in block.get("lines", []) for span in line.get("spans", []) if span.get("text", "").strip()]
        return {"pages": len(doc), "second_parser_pages": len(PdfReader(BytesIO(raw)).pages),
                "page_sizes_pt": sizes,
                "a5": all(abs(w - 419.5276) < 1 and abs(h - 595.2756) < 1 for w, h in sizes),
                "minimum_font_pt": min(fonts) if fonts else None,
                "active_links": sum(len(p.get_links()) for p in doc)}


def inspect_api_artifact(archive, *, as_of):
    run = deepcopy(archive["run"])
    if (run.get("path") != ".github/workflows/api-market-multiday-experiment.yml"
            or archive["artifact"].get("name") != "api-market-multiday-experiment"):
        raise ValueError("wrong_api_artifact_workflow")
    instant(as_of)
    run.update(artifacts=[deepcopy(archive["artifact"])], date_statuses=[])
    bundles, comparisons, days = [], [], []
    pattern = r"v2/API_MARKET_SCAN_PLAYABLE_(\d{4}-\d{2}-\d{2})\.json"
    for member in sorted(archive["files"]):
        matched = re.fullmatch(pattern, member)
        if not matched:
            continue
        day = matched[1]
        source = _capture(archive, member)
        if source["payload"].get("date") != day:
            raise ValueError("artifact_payload_date_mismatch")
        names = {"status": f"multiday_status/{day}.json", "freeze": f"audit_input/{day}.json",
                 "pdf": f"pdf/API_MARKET_SCAN_{day}.pdf"}
        absent = [name for name in names.values() if name not in archive["files"]]
        status = _capture(archive, names["status"])["payload"] if names["status"] in archive["files"] else None
        freeze = _capture(archive, names["freeze"]) if names["freeze"] in archive["files"] else None
        if status and status.get("date") != day:
            raise ValueError("artifact_status_date_mismatch")
        run["date_statuses"].append({"date": day, "status": status.get("status") if status else "missing",
                                     "artifact_name": archive["artifact"]["name"]})
        bundle = adapt_api(source, freeze_capture=freeze)
        bundle.update(run_id=str(run["id"]), run_head_sha=run["head_sha"], run_conclusion=run["conclusion"],
                      run_updated_at=run["updated_at"], date_status=status.get("status") if status else "missing",
                      artifact_name=archive["artifact"]["name"], artifact_digest=archive["artifact"]["digest"],
                      artifact_bytes_digest_verified=True)
        violations = []
        if not freeze:
            violations.append({"reason": "freeze_missing"})
        else:
            stamp = instant(freeze["payload"].get("frozen_at_utc"))
            if not instant(run["run_started_at"]) <= instant(source["payload"]["generated_at_utc"]) <= stamp <= instant(run["updated_at"]) <= instant(as_of):
                violations.append({"reason": "freeze_outside_run_or_as_of"})
            for index, row in enumerate(source["payload"]["positions"]):
                try:
                    ko = instant(row.get("kickoff"))
                    quote = row.get("best_quote") or {}
                    if not instant(quote.get("provider_updated_at")) <= stamp < ko:
                        raise ValueError("quote_or_freeze_lookahead")
                    if ko.astimezone(WARSAW).date().isoformat() != day or row.get("date") != day:
                        raise ValueError("fixture_date_mismatch")
                    if number(quote.get("odd")) < number("1.20") or number(row.get("final_assessment_pct")) < 67:
                        raise ValueError("published_threshold_mismatch")
                except ValueError as exc:
                    violations.append({"index": index, "reason": str(exc)})
        comparison = compare_api(source, bundle, freeze_capture=freeze, as_of=as_of)
        identities = [json.dumps(row["market_identity"], sort_keys=True) for row in bundle["rows"]]
        counts = Counter(identities)
        original_rows = source["payload"]["positions"]
        expected_order = sorted(original_rows, key=lambda r: (-number(r["final_assessment_pct"]),
            -number(r["api_pure_pct"]), str(r["fixture_id"]), str(r["selection"])))
        days.append({"date": day, "status": status, "missing_members": absent,
                     "candidate_count": bundle["declared_candidates"], "published_count": len(bundle["rows"]),
                     "fixture_count": len({r["fixture_id"] for r in bundle["rows"]}),
                     "rejection_counts": source["payload"].get("rejections"),
                     "declared_counts_reconcile": bundle["declared_candidates"] == len(bundle["rows"]) + sum(source["payload"].get("rejections", {}).values()),
                     "frozen_at_utc": freeze["payload"]["frozen_at_utc"] if freeze else None,
                     "published_time_violations": violations,
                     "duplicate_exact_markets": sum(n - 1 for n in counts.values() if n > 1),
                     "exact_identities_present": all(r["market_identity"] is not None for r in bundle["rows"]),
                     "recorded_export_order_matches_source_rule": original_rows == expected_order,
                     "published_only": True, "full_candidate_history_audit": "BLOCKED_NOT_IN_ARTIFACT",
                     "independent_quote_lineage": "SOURCE_BLOCKED",
                     "original_pdf": _pdf_info(archive["files"][names["pdf"]]) if names["pdf"] in archive["files"] else None})
        bundles.append(bundle)
        comparisons.append(comparison)
    if not days:
        raise ValueError("no_dated_api_export")
    evidence = {"runs": [run], "snapshots": [], "settlements": []}
    return {"manifest": archive["manifest"], "days": days, "bundles": bundles,
            "comparisons": comparisons, "evidence": evidence}


def coverage(start_date, api_days, pitch_bundles):
    days = []
    for day in report_dates(start_date):
        api = [d for d in api_days if d["date"] == day]
        pitch = [b for b in pitch_bundles if day in b["dates"]]
        days.append({"date": day, "api_export_present": bool(api),
                     "api_status_ok": len(api) == 1 and (api[0].get("status") or {}).get("status") == "ok",
                     "pitch_snapshot_present": bool(pitch),
                     "api_complete_source": False,
                     "pitch_strict_rows": sum(b["verified_rows"] for b in pitch)})
    return {"start_date": start_date, "days": days,
            "three_api_exports_present": all(d["api_export_present"] for d in days),
            "full_multimodel_ready": False}


def inspect_pitch_artifact(archive):
    if (archive["run"].get("path") != ".github/workflows/pitchapi-prematch-context.yml"
            or archive["artifact"].get("name") != "pitchapi-prematch-context"):
        raise ValueError("wrong_pitch_artifact_workflow")
    bundles, days = [], []
    start, end = instant(archive["run"]["run_started_at"]), instant(archive["run"]["updated_at"])
    for member in sorted(archive["files"]):
        match = re.fullmatch(r"data/pitchapi/prematch/(\d{4}-\d{2}-\d{2})\.json", member)
        if not match:
            continue
        capture = _capture(archive, member)
        if capture["payload"].get("target_date") != match[1]:
            raise ValueError("pitch_filename_target_mismatch")
        bundle = adapt_pitchapi(capture)
        captured = instant(bundle["snapshot_at"])
        days.append({"date": match[1], "snapshot_at": bundle["snapshot_at"],
                     "captured_in_this_run": start <= captured <= end,
                     "rows": len(bundle["rows"]), "strict_rows": bundle["verified_rows"],
                     "warsaw_kickoff_dates": dict(Counter(instant(r["kickoff"]).astimezone(WARSAW).date().isoformat() for r in bundle["rows"])),
                     "invalid_rows": [{"id": r["native_fixture_id"], "kickoff": r["kickoff"], "reasons": r["blockers"]}
                                      for r in bundle["rows"] if not r["verified_prematch"]],
                     "blockers": bundle["blockers"]})
        bundles.append(bundle)
    return {"manifest": archive["manifest"], "days": days, "bundles": bundles}


def check_delivery(directory, start_date, expected_hashes):
    """Prove local availability, never claim recipient delivery from existence."""
    root = Path(directory)
    validation = validate_pdf_bundle(root, start_date)
    paths = [root / f"MULTIMODEL_{day}.pdf" for day in report_dates(start_date)]
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if actual != expected_hashes:
        raise ValueError("delivery_file_hash_mismatch")
    return {"status": "FILES_VERIFIED_AVAILABLE", "files": [{"name": p.name, "sha256": actual[p.name],
            "bytes": p.stat().st_size, "pages": v["pages"]} for p, v in zip(paths, validation)],
            "recipient_receipt_confirmed": False, "complete_forecast_delivery": False}


def run_e2e(api_zip, api_run, api_artifacts, pitch_zip, pitch_run, pitch_artifacts,
            kb_capture, consensus_capture, *, start_date, as_of, pdf_output=None):
    def read_zip(path, run_file, artifact_file, name):
        run = load_json(run_file)["payload"]
        matches = [a for a in load_json(artifact_file)["payload"].get("artifacts", []) if a.get("name") == name]
        if len(matches) != 1:
            raise ValueError("missing_or_ambiguous_named_artifact")
        return read_artifact(path, run, matches[0])
    api = inspect_api_artifact(read_zip(api_zip, api_run, api_artifacts, "api-market-multiday-experiment"), as_of=as_of)
    pitch = inspect_pitch_artifact(read_zip(pitch_zip, pitch_run, pitch_artifacts, "pitchapi-prematch-context"))
    sheets = [adapt_sheet(load_json(kb_capture), "kb21"), adapt_sheet(load_json(consensus_capture), "consensus")]
    bundles = api["bundles"] + pitch["bundles"] + sheets
    matches = {}
    for bundle in api["bundles"]:
        for row in bundle["rows"]:
            match = match_pitchapi(row, pitch["bundles"])
            matches[f"{row['date']}:{row['fixture_id']}"] = match["native_fixture_id"] if match else None
    report = {"schema": "multimodel-v2-e2e-artifact-audit-v1", "as_of": as_of,
              "api": {k: api[k] for k in ("manifest", "days", "comparisons")},
              "pitchapi": {k: pitch[k] for k in ("manifest", "days")},
              "sheets": [{"system": b["system"], "source": b["source"], "source_url": b["spreadsheet_url"],
                          "read_range": b["read_range"], "spreadsheet_timezone": b["spreadsheet_timezone"],
                          "read_rows": len(b["rows"]), "recorded_selection_rows": b["recorded_selection_rows"],
                          "non_selection_rows": b["non_selection_rows"], "latest_date": b["latest_date"],
                          "verified_prematch_rows": b["verified_rows"], "blockers": b["blockers"]} for b in sheets],
              "coverage_current_report": coverage(start_date, api["days"], pitch["bundles"]),
              "coverage_api_run_report": coverage(api["days"][0]["date"], api["days"], pitch["bundles"]),
              "pitchapi_exact_matches": matches,
              "readiness": three_day_readiness(start_date, bundles, api["evidence"], as_of=as_of),
              "full_parallel_1_to_1_complete": False, "models_modified": False,
              "register_writes": False, "n_effect": 0, "paid_api_scans_started": 0}
    if pdf_output is not None:
        e = api["evidence"]
        paths = generate_three_pdfs(start_date, e["runs"], e["snapshots"], e["settlements"], as_of=as_of,
                                    output_dir=pdf_output, source_bundles=bundles)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        report["pdf_delivery"] = check_delivery(paths[0].parent, start_date, hashes)
    return report


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("api-zip", "api-run", "api-artifacts", "pitch-zip", "pitch-run", "pitch-artifacts", "kb", "consensus"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--pdf-output", type=Path)
    args = parser.parse_args(argv)
    report = run_e2e(args.api_zip, args.api_run, args.api_artifacts, args.pitch_zip, args.pitch_run,
                     args.pitch_artifacts, args.kb, args.consensus, start_date=args.start,
                     as_of=args.as_of, pdf_output=args.pdf_output)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
