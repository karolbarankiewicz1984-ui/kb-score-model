"""Recover recorded spreadsheet revision values, never a new prematch freeze."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
from io import StringIO
import re

from .source_manifest import WARSAW, instant, local_day, number

HEADERS = {
    "kb21": {"ID", "Data analizy", "Data wydarzenia", "Wydarzenie", "Rynek", "Typ", "P(model)", "KB Score", "Decyzja"},
    "consensus": {"Date", "Analysis Time", "Event", "Market", "Pick", "Category", "Odds 11:30"},
}
NUMERIC = {"Kurs", "P(model)", "KB Score", "Confidence", "Odds 11:30", "Odds 15:00", "Closing Odds", "P(HIT)"}


def _calendar(value):
    # Midnight is the connector's rendering of a calendar cell, not kickoff.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: 00:00:00)?", value):
        return None
    try:
        return local_day(value[:10]).isoformat()
    except ValueError:
        return None


def recover_revision(capture, revision_index, system):
    """Read one original connector CSV-text export, preserving every value.

    revision_index is the observed revisions.list result. No date/P/odds are
    inferred from notes, results, export time or the dataframe's index column.
    """
    if system not in HEADERS:
        raise ValueError("unknown_history_system")
    source = capture["payload"]
    if source.get("fileId") != revision_index.get("fileId"):
        raise ValueError("history_file_mismatch")
    matches = [r for r in revision_index.get("revisions", []) if str(r.get("id")) == str(source.get("revisionId"))]
    if len(matches) != 1 or instant(matches[0].get("modifiedTime")) != instant(source.get("revisionModifiedTime")):
        raise ValueError("revision_not_in_verified_index")
    text = source.get("content")
    if not isinstance(text, str) or not text:
        raise ValueError("missing_revision_content")
    tables, active = [], None
    for row in csv.reader(StringIO(text, newline="")):
        if row and row[0].startswith("\f"):
            active = None
        if HEADERS[system].issubset(row):
            indexed = bool(row and row[0] in ("", "\f"))
            headers = row[1:] if indexed else row[:]
            if len(headers) != len(set(headers)):
                raise ValueError("duplicate_revision_headers")
            active = {"headers": headers, "indexed": indexed, "rows": [], "indices": [], "non_selection_rows": 0}
            tables.append(active)
            continue
        if active is None or not row:
            continue
        cells = row[:]
        export_index = None
        if active["indexed"]:
            if not cells[0].isdigit():
                raise ValueError("invalid_connector_export_index")
            export_index = int(cells.pop(0))
            if active["indices"] and export_index <= active["indices"][-1]:
                raise ValueError("duplicate_or_unordered_export_index")
            active["indices"].append(export_index)
        values = {h: cells[i] if i < len(cells) else "" for i, h in enumerate(active["headers"])}
        required = ("ID", "Data wydarzenia", "Wydarzenie", "Typ") if system == "kb21" else ("Date", "Event", "Pick")
        if all(values.get(k, "").strip() for k in required):
            active["rows"].append({"export_index": export_index, "original": values, "original_cells": cells})
        else:
            active["non_selection_rows"] += 1
    if len(tables) != 1:
        raise ValueError("missing_or_ambiguous_revision_table")

    modified = instant(source["revisionModifiedTime"])
    recovered = []
    for row in tables[0]["rows"]:
        values = row["original"]
        day = _calendar(values.get("Data wydarzenia" if system == "kb21" else "Date"))
        if system == "consensus":
            time_class = "SOURCE_DATE_NOT_VERIFIED_EVENT_DATE"
            key = tuple(values.get(k, "") for k in ("Date", "Analysis Time", "Event", "Market", "Pick"))
        else:
            key = (values["ID"],)
            captured_day = modified.astimezone(WARSAW).date().isoformat()
            time_class = ("INVALID_EVENT_DATE" if not day else "REVISION_AFTER_EVENT_DATE" if captured_day > day
                          else "SAME_EVENT_DATE_KICKOFF_UNKNOWN" if captured_day == day else "REVISION_BEFORE_EVENT_DATE")
        recovered.append(dict(row, source_record_key=list(key), date=day, time_class=time_class,
                              source_revision_id=str(source["revisionId"]),
                              source_revision_modified_at=source["revisionModifiedTime"],
                              fixture_id=None, forecast_frozen_at=None,
                              historical_only=True, eligible_as_new_prematch=False))
    return {"schema": "multimodel-v2-recorded-history-v1", "system": system,
            "file_id": source["fileId"], "revision_id": str(source["revisionId"]),
            "revision_modified_at": source["revisionModifiedTime"], "source_url": source.get("url"),
            "capture_sha256": capture["capture_sha256"], "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "rows": recovered, "time_classes": dict(Counter(r["time_class"] for r in recovered)),
            "non_selection_rows": tables[0]["non_selection_rows"],
            "register_writes": False, "n_effect": 0, "fresh_predictions_created": 0,
            "sampling": "one_observed_revision_not_earliest_cell_history"}


def compare_revisions(previous, current):
    if previous["file_id"] != current["file_id"] or previous["system"] != current["system"]:
        raise ValueError("different_history_sources")
    if instant(previous["revision_modified_at"]) >= instant(current["revision_modified_at"]):
        raise ValueError("revision_order_invalid")
    def index(snapshot):
        grouped = {}
        for row in snapshot["rows"]:
            grouped.setdefault(tuple(row["source_record_key"]), []).append(row)
        return grouped
    old, new = index(previous), index(current)
    ambiguous = {k for k in old.keys() | new.keys() if len(old.get(k, [])) > 1 or len(new.get(k, [])) > 1}
    changes = []
    for key in sorted((old.keys() & new.keys()) - ambiguous):
        left, right = old[key][0]["original"], new[key][0]["original"]
        fields, formatting = [], []
        for field in sorted(left.keys() | right.keys()):
            if left.get(field) == right.get(field):
                continue
            if field in NUMERIC:
                try:
                    if number(left.get(field)) == number(right.get(field)):
                        formatting.append(field)
                        continue
                except ValueError:
                    pass
            fields.append(field)
        if fields or formatting:
            changes.append({"source_record_key": list(key), "changed_fields": fields, "numeric_format_only": formatting})
    return {"schema": "multimodel-v2-recorded-history-diff-v1", "system": previous["system"],
            "previous_revision": previous["revision_id"], "current_revision": current["revision_id"],
            "previous_rows": len(previous["rows"]), "current_rows": len(current["rows"]),
            "added_record_keys": [list(k) for k in sorted(new.keys() - old.keys())],
            "removed_record_keys": [list(k) for k in sorted(old.keys() - new.keys())],
            "ambiguous_record_keys": [list(k) for k in sorted(ambiguous)], "changes": changes,
            "selection_rule": "KB_native_ID_or_exact_consensus_source_fields_no_fuzzy_join",
            "earliest_original_forecast_inferred": False, "register_writes": False, "n_effect": 0}
