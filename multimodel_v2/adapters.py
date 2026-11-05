"""Read existing source files/captures without guessing missing evidence.

No network, model calls, writes, archive repair, text-market parsing or inferred
freeze timestamps. Native fields and technical capture hashes remain separate
from independently verified market/quote evidence.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import unicodedata

from .source_manifest import WARSAW, _identity_json, identifier, instant, local_day, market_identity, number


def load_json(path):
    path = Path(path)
    content = path.read_bytes()
    return {"locator": str(path), "capture_sha256": hashlib.sha256(content).hexdigest(),
            "payload": json.loads(content)}


def _bundle(system, capture):
    return {"system": system, "source": {k: capture[k] for k in ("locator", "capture_sha256")},
            "availability": "readable", "rows": [], "blockers": [], "dates": []}


def _date(value):
    if type(value) in (int, float):
        serial = number(value)
        if serial != int(serial) or not 1 <= serial <= 100000:
            raise ValueError("invalid_sheet_date")
        return (date(1899, 12, 30) + timedelta(days=int(serial))).isoformat()
    return local_day(value).isoformat()


def _finish(bundle):
    dates = sorted({r["date"] for r in bundle["rows"] if r.get("date")})
    bundle["dates"] = dates
    bundle["latest_date"] = dates[-1] if dates else None
    bundle["verified_rows"] = sum(r["verified_prematch"] for r in bundle["rows"])
    bundle["blockers"] = sorted(set(bundle["blockers"]))
    return bundle


def _quote(quote, identity, *, export=False):
    if not isinstance(quote, dict):
        return None
    selected = quote.get("odd" if export else "selected_odd")
    try:
        price = str(number(selected))
    except ValueError:
        price = None
    return {"bookmaker": quote.get("bookmaker"), "selected_odd": price,
            "provider_updated_at": quote.get("provider_updated_at"),
            # Deliberately do NOT bind a quote to the candidate's identity.
            "market_identity": deepcopy(quote.get("market_identity")),
            "original": deepcopy(quote)}


def adapt_api(capture, *, freeze_capture=None):
    payload = capture["payload"]
    if not isinstance(payload, dict):
        raise ValueError("invalid_api_source")
    schema = payload.get("schema")
    full = schema == "api-market-scan-v3"
    if not full and schema != "api-market-playable-export-v2":
        raise ValueError("unsupported_api_schema")
    rows = payload.get("background_candidates" if full else "positions")
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("missing_api_rows")
    day = local_day(payload.get("date")).isoformat()
    bundle = _bundle("api_market", capture)
    bundle.update(native_schema=schema, declared_candidates=payload.get("candidate_count", len(rows)),
                  background_complete=full, native_top=deepcopy(payload.get("top_positions") if full else None),
                  generated_at=payload.get("generated_at_utc"), original_payload=deepcopy(payload))
    publication = payload.get("publication") if full else None
    freeze = freeze_capture["payload"] if freeze_capture else None
    if freeze is not None and (not isinstance(freeze, dict) or freeze.get("schema") != "api-market-audit-input-v1" or freeze.get("date") != day):
        raise ValueError("freeze_source_date_or_schema_mismatch")
    captured = publication.get("captured_at_utc") if isinstance(publication, dict) else (
        freeze.get("frozen_at_utc") if isinstance(freeze, dict) else None)
    freeze_id = publication.get("id") if isinstance(publication, dict) else None
    bundle["freeze"] = {"id": freeze_id, "captured_at_utc": captured,
                        "provenance": publication.get("provenance") if isinstance(publication, dict) else None}
    if freeze_capture:
        bundle["freeze_source"] = {k: freeze_capture[k] for k in ("locator", "capture_sha256")}
    if not full:
        bundle["blockers"].append("full_background_not_archived")
    if not freeze_id:
        bundle["blockers"].append("original_publication_id_missing")
    for index, raw in enumerate(rows):
        gaps = []
        canonical = deepcopy(raw)
        # Native match totals retain a technical history-team anchor. The
        # declared match scope makes team inapplicable, without changing raw.
        if canonical.get("market_scope") == "match":
            canonical["team_id"] = None
        try:
            identity = _identity_json(market_identity(canonical))
        except ValueError:
            identity = None
            gaps.append("exact_market_identity_missing")
        market_data = raw.get("market_data")
        native_quotes = (market_data.get("quotes") or []) if full and isinstance(market_data, dict) else (
            [] if full else [raw.get("best_quote")])
        if not isinstance(native_quotes, list):
            raise ValueError("invalid_api_quotes")
        quotes = [_quote(q, identity, export=not full) for q in native_quotes]
        quotes = [q for q in quotes if q is not None]
        if not quotes:
            gaps.append("missing_quote")
        independent = []
        for quote in quotes:
            try:
                if not isinstance(quote["market_identity"], dict):
                    raise ValueError("independent_quote_identity_missing")
                if identity is None or market_identity(quote["market_identity"]) != market_identity(identity):
                    raise ValueError("independent_quote_identity_missing")
                if not isinstance(quote["bookmaker"], str) or not quote["bookmaker"].strip():
                    raise ValueError("missing_bookmaker")
                if number(quote["selected_odd"]) <= 1:
                    raise ValueError("invalid_odds")
                if not instant(quote["provider_updated_at"]) <= instant(captured) < instant(raw.get("kickoff")):
                    raise ValueError("quote_or_freeze_lookahead")
                independent.append(quote)
            except ValueError as exc:
                gaps.append(str(exc))
        try:
            if instant(raw.get("kickoff")).astimezone(WARSAW).date().isoformat() != day:
                gaps.append("kickoff_date_mismatch")
            if not instant(payload.get("generated_at_utc")) <= instant(captured) < instant(raw.get("kickoff")):
                gaps.append("freeze_not_prematch")
        except ValueError:
            gaps.append("kickoff_or_freeze_timestamp_missing")
        if not freeze_id or not isinstance(publication, dict) or publication.get("provenance") != "live_pre_match":
            gaps.append("original_publication_id_missing")
        if not independent:
            gaps.append("no_independently_verified_quote")
        bundle["rows"].append({"native_index": index, "date": day,
            "fixture_id": str(raw["fixture_id"]) if raw.get("fixture_id") is not None else None,
            "home": raw.get("home"), "away": raw.get("away"), "competition": raw.get("competition"),
            "kickoff": raw.get("kickoff"), "market_identity": identity,
            "selection": raw.get("selection"), "score": raw.get("final_assessment_pct"),
            "status": raw.get("final_status"), "quotes": quotes, "top_rank": None,
            "verified_prematch": not gaps, "blockers": sorted(set(gaps)), "original": deepcopy(raw)})

    tops = payload.get("top_positions") if full else freeze.get("picks") if isinstance(freeze, dict) else None
    bundle["native_top"] = deepcopy(tops)
    bundle["top_order"] = []
    if not isinstance(tops, list):
        bundle["blockers"].append("original_top_missing")
    else:
        for rank, raw in enumerate(tops, 1):
            # An audit-input pick lacks settlement_period. Match only explicit
            # fields, require uniqueness, and retain that missing fact as a gap.
            fields = ("fixture_id", "team_id", "market", "market_scope", "direction", "line")
            matches = [r for r in bundle["rows"] if all(r["original"].get(k) == raw.get(k) for k in fields)]
            if len(matches) != 1 or matches[0]["top_rank"] is not None:
                bundle["blockers"].append("ambiguous_original_top")
                continue
            matches[0]["top_rank"] = rank
            bundle["top_order"].append(matches[0]["native_index"])
            if not full:
                for field in ("kickoff", "home", "away", "selection", "final_assessment_pct"):
                    if field in raw and raw[field] != matches[0]["original"].get(field):
                        bundle["blockers"].append("freeze_export_field_mismatch")
                frozen_quote = raw.get("best_quote")
                if not isinstance(frozen_quote, dict):
                    bundle["blockers"].append("freeze_quote_missing")
                else:
                    try:
                        if not any(q["bookmaker"] == frozen_quote.get("bookmaker") and
                                   number(q["selected_odd"]) == number(frozen_quote.get("odd"))
                                   for q in matches[0]["quotes"]):
                            bundle["blockers"].append("freeze_quote_mismatch")
                    except ValueError:
                        bundle["blockers"].append("freeze_quote_missing")
                if "settlement_period" not in raw:
                    bundle["blockers"].append("frozen_top_period_missing")
    bundle["blockers"].extend(gap for row in bundle["rows"] for gap in row["blockers"])
    return _finish(bundle)


def adapt_api_overlay(capture):
    """Read a raw probability overlay without promoting it to a v3 freeze.

    These files do not retain bookmaker prices or original scored TOP. Even
    when readable for today's date, they cannot fill the native audit inputs.
    """
    payload = capture["payload"]
    if (not isinstance(payload, dict) or payload.get("schema") != "api-market-snapshot-v1"
            or not isinstance(payload.get("items"), list)
            or any(not isinstance(row, dict) for row in payload["items"])):
        raise ValueError("unsupported_api_overlay_schema")
    day = local_day(payload.get("date")).isoformat()
    instant(payload.get("captured_at_utc"))
    bundle = _bundle("api_market_overlay", capture)
    gaps = ["overlay_not_scored_native_publication", "original_top_missing",
            "independent_quote_identity_missing", "bookmaker_price_missing",
            "kickoff_missing", "prematch_freeze_timestamp_missing"]
    bundle.update(native_schema=payload["schema"], snapshot_at=payload["captured_at_utc"],
                  original_payload=deepcopy(payload), background_complete=False, native_top=None,
                  blockers=gaps.copy())
    for index, row in enumerate(payload["items"]):
        bundle["rows"].append({"native_index": index, "date": day,
            "fixture_id": str(row["fixture_id"]) if row.get("fixture_id") is not None else None,
            "market_probability_original": row.get("market_probability_pct"),
            "score": None, "status": None, "odds_original": None,
            "verified_prematch": False, "blockers": gaps.copy(), "original": deepcopy(row)})
    return _finish(bundle)


def read_api_run(root, *, run_capture, artifacts_capture):
    """Read an existing immutable artifact mirror; never create/repair it."""
    root = Path(root)
    archived = load_json(root / "run_metadata.json")
    run = deepcopy(run_capture["payload"])
    for key in ("id", "head_sha", "conclusion", "status", "run_started_at", "updated_at"):
        if archived["payload"].get(key) != run.get(key):
            raise ValueError("run_metadata_mismatch")
    artifacts = artifacts_capture["payload"].get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("missing_artifact_metadata")
    matches = [a for a in artifacts if a.get("name") == "api-market-multiday-experiment" and a.get("expired") is False]
    if len(matches) != 1:
        raise ValueError("missing_or_ambiguous_source_artifact")
    artifact = matches[0]
    if (artifact.get("workflow_run", {}).get("id") != run.get("id")
            or artifact["workflow_run"].get("head_sha") != run.get("head_sha")):
        raise ValueError("artifact_run_mismatch")
    run["artifacts"] = deepcopy(artifacts)
    run["date_statuses"] = []
    bundles = []
    snapshots = []
    for path in sorted((root / "v2").glob("API_MARKET_SCAN_PLAYABLE_*.json")):
        capture = load_json(path)
        day = local_day(capture["payload"].get("date")).isoformat()
        status_capture = load_json(root / "multiday_status" / f"{day}.json")
        status = status_capture["payload"]
        if status.get("date") != day:
            raise ValueError("status_date_mismatch")
        run["date_statuses"].append(dict(status, artifact_name=artifact["name"]))
        freeze_path = root / "audit_input" / f"{day}.json"
        bundle = adapt_api(capture, freeze_capture=load_json(freeze_path) if freeze_path.is_file() else None)
        bundle.update(run_id=str(run["id"]), run_head_sha=run["head_sha"],
                      run_conclusion=run["conclusion"], artifact_name=artifact["name"],
                      run_updated_at=run["updated_at"], artifact_digest=artifact.get("digest"),
                      artifact_bytes_digest_verified=False, date_status=status.get("status"))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            bundle["blockers"].append("run_not_successful")
        # Published-only data never masquerades as the full background, and a
        # technical file hash is never promoted to an original publication ID.
        bundles.append(bundle)
    return {"bundles": bundles, "evidence": {"runs": [run], "snapshots": snapshots, "settlements": []},
            "metadata_sources": [archived["capture_sha256"], run_capture["capture_sha256"], artifacts_capture["capture_sha256"]]}


def adapt_sheet(capture, system):
    if system not in ("kb21", "consensus"):
        raise ValueError("unknown_sheet_system")
    payload = capture["payload"]
    metadata, data = payload.get("metadata"), payload.get("range")
    if not isinstance(metadata, dict) or not isinstance(data, dict) or not isinstance(data.get("values"), list):
        raise ValueError("invalid_sheet_capture")
    values = data["values"]
    if not values or not all(isinstance(v, str) for v in values[0]):
        raise ValueError("missing_sheet_headers")
    headers = values[0]
    if len(headers) != len(set(headers)):
        raise ValueError("duplicate_sheet_headers")
    expected_tab = "Rejestr" if system == "kb21" else "Selections"
    if not data.get("range", "").startswith(expected_tab + "!"):
        raise ValueError("wrong_source_tab")
    titles = {s.get("properties", {}).get("title") for s in metadata.get("sheets", [])}
    if expected_tab not in titles:
        raise ValueError("sheet_not_in_metadata")
    required = ("ID", "Data wydarzenia", "Wydarzenie", "Rynek", "Typ", "Decyzja") if system == "kb21" else (
        "Date", "Analysis Time", "Event", "Market", "Pick", "Category")
    if any(h not in headers for h in required):
        raise ValueError("unsupported_sheet_headers")
    bundle = _bundle(system, capture)
    bundle.update(spreadsheet_url=metadata.get("spreadsheetUrl"), sheet=expected_tab,
                  spreadsheet_timezone=metadata.get("properties", {}).get("timeZone"),
                  read_range=data["range"], retrieved_at=payload.get("retrieved_at"), headers=deepcopy(headers))
    # Native registers contain descriptive markets, dates and analysis times,
    # not independent exact-market/kickoff/freeze/quote identities. Preserve
    # these fields rather than parsing narratives into new predictions.
    gaps = ["fixture_id_missing", "kickoff_missing", "exact_market_identity_missing",
            "prematch_freeze_timestamp_missing", "bookmaker_missing", "quote_timestamp_missing"]
    if system == "consensus":
        gaps.append("source_date_and_analysis_time_not_verified_event_kickoff")
    bundle["blockers"] = gaps.copy()
    for row_number, cells in enumerate(values[1:], 2):
        if not isinstance(cells, list):
            raise ValueError("invalid_sheet_row")
        if not any(value not in (None, "") for value in cells):
            continue
        row = {header: cells[i] if i < len(cells) else None for i, header in enumerate(headers)}
        date_value = row.get("Data wydarzenia" if system == "kb21" else "Date")
        try:
            day = _date(date_value)
        except (ValueError, OverflowError):
            day = None
        bundle["rows"].append({"native_row": row_number, "date": day,
            "has_recorded_selection": all(row.get(k) not in (None, "") for k in (
                ("Data wydarzenia", "Wydarzenie", "Typ") if system == "kb21" else ("Date", "Event", "Pick"))),
            "native_record_id": row.get("ID") if system == "kb21" else None,
            "fixture_id": None, "kickoff": None, "market_identity": None,
            "event": row.get("Wydarzenie" if system == "kb21" else "Event"),
            "selection": row.get("Typ" if system == "kb21" else "Pick"),
            "status": row.get("Decyzja" if system == "kb21" else "Category"),
            "score": row.get("KB Score") if system == "kb21" else None,
            "probability_original": row.get("P(model)" if system == "kb21" else "P(HIT)"),
            "odds_original": row.get("Kurs" if system == "kb21" else "Odds 11:30"),
            "verified_prematch": False, "blockers": gaps.copy(), "original": deepcopy(row),
            "original_cells": deepcopy(cells)})
    bundle["recorded_selection_rows"] = sum(r["has_recorded_selection"] for r in bundle["rows"])
    bundle["non_selection_rows"] = len(bundle["rows"]) - bundle["recorded_selection_rows"]
    return _finish(bundle)


def adapt_pitchapi(capture):
    payload = capture["payload"]
    if payload.get("schema") != "pitchapi-prematch-context-v1" or not isinstance(payload.get("fixtures"), list):
        raise ValueError("unsupported_pitchapi_schema")
    day = local_day(payload.get("target_date")).isoformat()
    captured = instant(payload.get("snapshot_utc"))
    bundle = _bundle("pitchapi", capture)
    bundle.update(snapshot_at=payload["snapshot_utc"], original_payload=deepcopy(payload))
    if any(not isinstance(row, dict) for row in payload["fixtures"]):
        raise ValueError("invalid_pitchapi_fixture")
    seen = Counter(str(r.get("pitch_match_id")) for r in payload["fixtures"])
    for raw in payload["fixtures"]:
        gaps = []
        try:
            identifier(raw.get("pitch_match_id"))
            if not all(isinstance(raw.get(k), str) and raw[k].strip() for k in ("home", "away", "league")):
                gaps.append("missing_fixture_facts")
            kickoff = instant(raw.get("kickoff_utc"))
            if captured >= kickoff or kickoff.astimezone(WARSAW).date().isoformat() != day:
                gaps.append("pitchapi_capture_or_date_invalid")
            if seen[str(raw["pitch_match_id"])] != 1:
                gaps.append("duplicate_pitchapi_fixture")
            if raw.get("both_sides_sufficient") is not True:
                gaps.append("insufficient_historical_context")
            for side in ("home_recent", "away_recent"):
                sample = raw.get(side) or {}
                history = sample.get("samples")
                if not isinstance(history, list) or not history or sample.get("complete_samples") != len(history):
                    raise ValueError("missing_pitchapi_history")
                for entry in history:
                    if not isinstance(entry, dict):
                        raise ValueError("invalid_pitchapi_history")
                    if instant(entry.get("kickoff_utc")) >= captured:
                        gaps.append("pitchapi_history_lookahead")
                    if number(entry.get("xg_for")) < 0 or number(entry.get("xg_against")) < 0:
                        gaps.append("invalid_pitchapi_history")
                if number(sample.get("mean_xg_for")) < 0 or number(sample.get("mean_xg_against")) < 0:
                    gaps.append("invalid_pitchapi_mean")
        except ValueError as exc:
            gaps.append(str(exc))
        bundle["rows"].append({"date": day, "native_fixture_id": raw.get("pitch_match_id"),
            "fixture_id": None, "home": raw.get("home"), "away": raw.get("away"),
            "competition": raw.get("league"), "kickoff": raw.get("kickoff_utc"),
            "market_identity": None, "status": "historical_context_only",
            "verified_prematch": not gaps, "blockers": sorted(set(gaps)), "original": deepcopy(raw)})
    bundle["blockers"] = [gap for row in bundle["rows"] for gap in row["blockers"]]
    return _finish(bundle)


def match_pitchapi(api_row, pitch_bundles, *, as_of=None):
    """Exact identities; optional cutoff binds context to an original freeze.

    A later prematch context may be a current association but cannot become an
    input to a replay at an earlier API freeze.
    """
    def name(value):
        return unicodedata.normalize("NFC", value).strip().casefold() if isinstance(value, str) else None
    def key(row):
        names = tuple(name(row.get(k)) for k in ("home", "away", "competition"))
        if not all(names):
            raise ValueError("missing_fixture_facts")
        return (*names, instant(row.get("kickoff")))
    try:
        target = key(api_row)
        cutoff = instant(as_of) if as_of is not None else None
        matches = [row for bundle in pitch_bundles for row in bundle["rows"]
                   if (cutoff is None or instant(bundle.get("snapshot_at")) <= cutoff)
                   if row["verified_prematch"] and key(row) == target]
    except ValueError:
        return None
    return deepcopy(matches[0]) if len(matches) == 1 else None


def source_summary(bundle, day, *, as_of=None):
    local_day(day)
    rows = [r for r in bundle["rows"] if r.get("date") == day]
    verified = [r for r in rows if r.get("verified_prematch")]
    blockers = set(bundle["blockers"])
    available = True
    if as_of is not None:
        stamp = (bundle.get("snapshot_at") if bundle["system"] in ("pitchapi", "api_market_overlay") else bundle.get("retrieved_at")
                 if bundle["system"] in ("kb21", "consensus") else bundle.get("run_updated_at"))
        try:
            available = instant(stamp) <= instant(as_of)
        except ValueError:
            available = False
        if not available:
            blockers.add("source_not_verified_available_at_cutoff")
            verified = []
    if not rows:
        blockers.add("no_source_rows_for_date")
    return {"system": bundle["system"], "availability": bundle["availability"],
            "rows_for_date": len(rows), "verified_rows_for_date": len(verified),
            "latest_date": bundle.get("latest_date"), "blockers": sorted(blockers),
            "available_as_of": available,
            "complete_for_date": bool(rows) and len(verified) == len(rows) and not blockers}


def api_evidence(bundle, run, *, git_receipt=None):
    """Copy a full original freeze into v2's input, without manufacturing gaps.

    Published-only exports return no snapshot. In a full native publication,
    missing independent quote identities remain missing and v2 rejects them.
    """
    evidence = {"runs": [deepcopy(run)], "snapshots": [], "settlements": []}
    if not bundle.get("background_complete"):
        return evidence
    if git_receipt is not None:
        from .git_publication import normalized_payload, payload_digest, validate_receipt
        if (bundle["source"]["capture_sha256"] != git_receipt.get("capture_sha256")
                or payload_digest(bundle["original_payload"]) != git_receipt.get("native_payload_sha256")):
            raise ValueError("git_bundle_capture_mismatch")
        snapshot = normalized_payload(bundle["original_payload"])
        validate_receipt(git_receipt, run, payload=snapshot)
        evidence["runs"][0].update(source_kind="git_publication", git_publications=[deepcopy(git_receipt)])
        snapshot.update(run_id=run["id"], head_sha=run["head_sha"], source_kind="git_publication",
                        source_ref=git_receipt["source_ref"])
        evidence["snapshots"].append(snapshot)
        return evidence
    if not bundle.get("run_id") or not bundle.get("run_head_sha") or not bundle.get("artifact_name"):
        raise ValueError("run_binding_missing")
    if str(bundle["run_id"]) != str(run.get("id")) or bundle["run_head_sha"] != run.get("head_sha"):
        raise ValueError("run_binding_mismatch")
    snapshot = deepcopy(bundle["original_payload"])
    if not isinstance(snapshot.get("publication"), dict) or not snapshot["publication"].get("id"):
        return evidence
    if snapshot["publication"].get("code_revision") not in (None, run["head_sha"]):
        raise ValueError("publication_run_sha_mismatch")
    snapshot.update(run_id=run["id"], head_sha=run["head_sha"], artifact_name=bundle["artifact_name"])
    for field in ("background_candidates", "top_positions"):
        for row in snapshot.get(field, []):
            if row.get("market_scope") == "match":
                row["team_id"] = None
    evidence["snapshots"].append(snapshot)
    return evidence
