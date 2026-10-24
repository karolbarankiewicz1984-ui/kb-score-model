"""Read-only reconstruction of original KB Score 2.1 LIVE from Google Sheet revisions.

Accepts *exported snapshot text* (connector revision "text/plain" gives CSV-like
sheets joined with form-feed), supplied as local files with attested revision
timestamps. Extracts earliest OBSERVED row per sheet ID; not necessarily the
earliest real revision. Historical PLAY labels are evidence, never new picks.

No Google/football API calls, no Sheet mutations, no historical N writes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, date
from io import StringIO
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

SCHEMA = "kb21-google-live-historical-recovery-v1"
WARSAW = ZoneInfo("Europe/Warsaw")
FIELDS = ("ID", "Data analizy", "Data wydarzenia", "Wydarzenie",
          "Rynek", "Typ", "Kurs", "P(model)", "KB Score", "Confidence",
          "Decyzja", "Uwagi", "Źródła")
LABELS = {"KB PLAY", "KB LEARN", "KB CONTROL"}
TRIPLET = re.compile(
    r"STR\s*(\d{1,2})\s*/\s*35\s*\|\s*"
    r"QUAL\s*(\d{1,2})\s*/\s*35\s*\|\s*"
    r"MATCH\s*(\d{1,2})\s*/\s*30", re.I)
COMPACT = re.compile(
    r"35\s*/\s*35\s*/\s*30\s*=\s*"
    r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", re.I)


def _number(x):
    if not isinstance(x, str) or not x.strip():
        return None
    try:
        val = float(x.strip().replace(",", "."))
    except ValueError:
        return None
    return val if math.isfinite(val) else None


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("revision timestamp must be an ISO string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid revision timestamp") from exc
    if dt.utcoffset() is None:
        raise ValueError("revision timestamp requires timezone")
    return dt


def parse_revision_content(content):
    """Connector export: numbered CSV tables separated by a form-feed header."""
    if not isinstance(content, str) or not content:
        raise ValueError("snapshot text missing")
    rows = csv.reader(StringIO(content, newline=""))
    headings = None
    items = []
    for row in rows:
        if row and row[0].startswith("\f"):
            headings = None
        if "Data analizy" in row and "P(model)" in row and "KB Score" in row:
            if not all(name in row for name in FIELDS):
                raise ValueError("Rejestr lacks required original fields")
            headings = row
            continue
        if headings is None or not row or not row[0].strip():
            continue
        data = dict(zip(headings, row))
        if not data.get("ID", "").isdigit():
            continue
        if not (data.get("Data analizy", "") >= "2026-08-22"
                and data.get("Data wydarzenia") and data.get("Wydarzenie")
                and data.get("Typ") and data.get("P(model)")
                and data.get("KB Score") and data.get("Decyzja") in LABELS):
            continue
        # Preserve only the source fields needed to reproduce a model audit;
        # the sheet remains the canonical source for full free-text notes.
        items.append({k: data.get(k, "") for k in FIELDS})
    if headings is None and not items:
        # There may be another sheet after "Rejestr"; this checks that an
        # actual register header was found, not a text file of invented rows.
        if not any("Rejestr" in line for line in content.splitlines()[:50]):
            raise ValueError("no valid Google Sheet Rejestr rows found")
    return items


def _original_block(note, score):
    matches = [m for m in (TRIPLET.search(note), COMPACT.search(note)) if m]
    if not matches:
        return {"blocks": None, "block_status": "UNRECORDED"}
    parts = [int(x) for x in matches[0].groups()]
    if (parts[0] > 35 or parts[1] > 35 or parts[2] > 30):
        return {"blocks": parts, "block_status": "INVALID_BLOCK_RANGE"}
    if abs(sum(parts) - score) > 1e-8:
        return {"blocks": parts, "block_status": "SCORE_SUM_MISMATCH"}
    return {"blocks": parts, "block_status": "MATCH"}


def _event_date_state(modified, event_date):
    try:
        d = date.fromisoformat(event_date)
    except (TypeError, ValueError):
        return "INVALID_EVENT_DATE"
    capture_date = modified.astimezone(WARSAW).date()
    if capture_date < d:
        return "OBSERVED_BEFORE_EVENT_DATE"
    if capture_date == d:
        return "SAME_EVENT_DATE_KICKOFF_UNKNOWN"
    return "FIRST_OBSERVED_AFTER_EVENT_DATE"


def rebuild(revisions):
    """revisions: iterable of {"revision_id", "modified_at", "content"}."""
    revisions = list(revisions)
    if not revisions:
        raise ValueError("At least one historical Google revision is required")
    snapshots = []
    seen_revisions = set()
    for r in revisions:
        if not isinstance(r, dict):
            raise ValueError("revision metadata must be an object")
        revision_id = str(r.get("revision_id", ""))
        if not revision_id.isdigit() or revision_id in seen_revisions:
            raise ValueError("Revision ID missing or duplicated")
        seen_revisions.add(revision_id)
        captured = _timestamp(r.get("modified_at"))
        items = parse_revision_content(r.get("content"))
        ids = [x["ID"] for x in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate Rejestr IDs in same revision")
        snapshots.append((captured, revision_id, items))
    snapshots.sort(key=lambda r: (r[0], int(r[1])))

    earliest, drift = {}, []
    for captured, revision_id, items in snapshots:
        for item in items:
            ident = item["ID"]
            if ident not in earliest:
                earliest[ident] = (captured, revision_id, item)
            else:
                original = earliest[ident][2]
                changes = [
                    k for k in ("Data analizy", "Data wydarzenia", "Wydarzenie",
                                "Rynek", "Typ", "Kurs", "P(model)",
                                "KB Score", "Confidence", "Decyzja")
                    if original.get(k) != item.get(k)
                ]
                if changes:
                    drift.append({"id": ident, "compared_revision": revision_id,
                                  "earliest_revision": earliest[ident][1],
                                  "changed_fields": changes})
    output = []
    for ident, (captured, rev, item) in sorted(
        earliest.items(), key=lambda p: int(p[0])):
        score = _number(item["KB Score"])
        p = _number(item["P(model)"])
        odds = _number(item.get("Kurs", ""))
        confidence = _number(item.get("Confidence", ""))
        issues = []
        if not (score is not None and 0 <= score <= 100):
            issues.append("SCORE_INVALID")
        if not (p is not None and 0 < p < 1):
            issues.append("P_MODEL_INVALID")
        if confidence is None or not 0 <= confidence <= 10:
            issues.append("CONFIDENCE_INVALID")
        if odds is None or odds <= 1:
            issues.append("ODDS_INVALID")
        version_note = item["Uwagi"]
        blocks = _original_block(version_note, score) if score is not None else {
            "blocks": None, "block_status": "SCORE_INVALID"}
        if blocks["block_status"] in ("INVALID_BLOCK_RANGE", "SCORE_SUM_MISMATCH"):
            issues.append(blocks["block_status"])
        ev = round(p * odds - 1, 8) if (
            p is not None and 0 < p < 1 and odds is not None and odds > 1) else None
        date_status = _event_date_state(captured, item["Data wydarzenia"])
        if date_status == "INVALID_EVENT_DATE":
            issues.append(date_status)
        output.append({
            "historical_sheet_id": ident,
            "analysis_date": item["Data analizy"],
            "event_date": item["Data wydarzenia"],
            "fixture": item["Wydarzenie"],
            "market": item["Rynek"],
            "selection": item["Typ"],
            "original_p_model": p,
            "original_sport_score": score,
            "original_blocks": blocks["blocks"],
            "block_status": blocks["block_status"],
            "original_confidence": confidence,
            "original_odds": odds,
            "recalculated_ev": ev,
            "historical_label_not_a_new_recommendation": item["Decyzja"],
            "first_observed_revision_among_sample": rev,
            "first_observed_at_utc": captured.isoformat(),
            "capture_vs_event_date": date_status,
            "human_preprice_p_model_method_recovered": False,
            "original_source_evidence_kept_in_google_sheet": True,
            "validated_before_kickoff": False,
            "validated_before_price_capture": False,
            "eligible_for_new_live_n": False,
            "new_publication": "ARCHIVAL ONLY / NO PLAY",
            "issues": issues,
        })
    counts = {}
    for row in output:
        name = row["capture_vs_event_date"]
        counts[name] = counts.get(name, 0) + 1
    return {
        "schema": SCHEMA, "source": "Google Drive original KB Score — Rejestr i Backtest",
        "revision_ids_examined": [x[1] for x in snapshots],
        "earliest_revision_utc": snapshots[0][0].isoformat(),
        "latest_revision_utc": snapshots[-1][0].isoformat(),
        "records_reconstructed": len(output), "capture_date_classes": counts,
        "changed_model_fields_in_later_samples": drift,
        "same_day_kickoff_times_proven": False,
        "all_revision_history_examined": False,
        "historical_n_updated": False, "no_automatic_play": True,
        "original_p_model_formula_recovered": False,
        "records": output,
    }


def main():
    p = argparse.ArgumentParser(description="Restore original Google workbook chronology")
    p.add_argument("manifest", help="JSON: revisions[{revision_id,modified_at,path}]")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    manifest_path = Path(args.manifest)
    spec = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not isinstance(spec.get("revisions"), list):
        raise ValueError("manifest must contain revisions array")
    items = [
        {"revision_id": row["revision_id"],
         "modified_at": row["modified_at"],
         "content": (manifest_path.parent / row["path"]).read_text(encoding="utf-8")}
        for row in spec["revisions"]
    ]
    output = rebuild(items)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"Recovered {output['records_reconstructed']} historical records; "
          "never modifies Google, N or PLAY")


if __name__ == "__main__":
    main()
