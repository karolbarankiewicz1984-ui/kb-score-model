"""Read-only health check for the single-source KB21 API-Football calendar.

Detects missing in-scope league IDs, late snapshots and unusual disappearance
of fixtures compared with the prior run. It NEVER inserts games, grants PLAY,
sets original P(model), modifies N, or changes existing workflows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time
import json
from math import ceil
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
# Stable API-Football identifiers; the provider may rename displayed leagues.
DOMESTIC_IDS = {
    39: "England", 140: "Spain", 135: "Italy", 78: "Germany",
    61: "France", 94: "Portugal", 88: "Netherlands",
    144: "Belgium", 203: "Turkey", 106: "Poland",
}
INTERNATIONAL_IDS = {1, 2, 3, 4, 5, 32, 848}


def _read(path):
    if not path.is_file():
        raise ValueError("Missing calendar file: " + path.name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid calendar object: " + path.name)
    return data


def check(source_dir, previous_dir=None):
    src = Path(source_dir)
    manifest = _read(src / "SINGLE_SOURCE_MANIFEST.json")
    days = manifest.get("dates")
    if (manifest.get("single_source_gate") != "PASS_SOURCE"
            or manifest.get("provider_count") != 1
            or not isinstance(days, list) or len(days) != 2
            or days[0] == days[1]):
        raise ValueError("Incomplete or invalid single-source manifest")
    stamp = datetime.fromisoformat(manifest["generated_at_utc"].replace("Z", "+00:00"))
    if stamp.utcoffset() is None:
        raise ValueError("Naive capture timestamp")
    snapshot_day = stamp.astimezone(WARSAW)
    if snapshot_day.date().isoformat() != days[0]:
        raise ValueError("Snapshot is not from Warsaw today")

    results = {"source_gate": "PASS_SOURCE", "status": "PASS", "days": days,
               "snapshot_utc": stamp.isoformat(), "warnings": [], "errors": [],
               "summaries": [], "excluded_known_id": [],
               "previous_comparison": None, "safe_to_publish_play": False,
               "register_writes": False, "original_kb21_n_effect": 0}
    if snapshot_day.time() > time(11, 15):
        results["warnings"].append(
            "Capture occurred after 11:15 Warsaw, close to/after the legacy LIVE target.")
    for day in days:
        file = _read(src / ("KB21_API_CALENDAR_" + day + ".json"))
        if (file.get("date") != day or file.get("single_source_gate") != "PASS_SOURCE"
                or not isinstance(file.get("provider_events"), list)
                or not isinstance(file.get("candidates"), list)):
            raise ValueError("Malformed day calendar: " + day)
        events = file["provider_events"]
        candidates = file["candidates"]
        if file.get("provider_total_events") != len(events):
            raise ValueError("Provider count mismatch: " + day)
        if file.get("pre_match_fixtures") != len(candidates):
            raise ValueError("Candidate count mismatch: " + day)
        results["summaries"].append({
            "date": day, "provider_events": len(events),
            "in_scope_events": file.get("in_scope_provider_events"),
            "eligible_candidates": len(candidates)})
        if not events:
            results["warnings"].append(
                day + ": API returned zero events; this is not proof of no matches.")
        for item in events:
            lid = item.get("league_id")
            country = item.get("country")
            if type(lid) is not int:
                continue
            known_domestic = lid in DOMESTIC_IDS and country == DOMESTIC_IDS[lid]
            known_cup = lid in INTERNATIONAL_IDS
            if ((known_domestic or known_cup) and not item.get("in_kb21_scope")
                    and item.get("status") == "NS"):
                results["excluded_known_id"].append({
                    "date": day, "fixture_id": item.get("fixture_id"),
                    "league_id": lid, "league": item.get("league")})
    if results["excluded_known_id"]:
        results["errors"].append(
            str(len(results["excluded_known_id"])) +
            " scheduled fixtures in known KB21 competitions were excluded by the legacy name filter.")

    if previous_dir:
        prevpath = Path(previous_dir) / ("KB21_API_CALENDAR_" + days[0] + ".json")
        if prevpath.is_file():
            prev = _read(prevpath)
            current = _read(src / ("KB21_API_CALENDAR_" + days[0] + ".json"))
            if prev.get("date") == days[0] and isinstance(prev.get("provider_events"), list):
                previous_ids = {e["fixture_id"] for e in prev["provider_events"]
                                if e.get("in_kb21_scope") and e.get("fixture_id")}
                current_ids = {e["fixture_id"] for e in current["provider_events"]
                               if e.get("in_kb21_scope") and e.get("fixture_id")}
                gone = sorted(previous_ids - current_ids)
                new = sorted(current_ids - previous_ids)
                results["previous_comparison"] = {
                    "day": days[0], "previous_in_scope": len(previous_ids),
                    "current_in_scope": len(current_ids), "missing": len(gone),
                    "added": len(new), "missing_fixture_ids": gone[:50]}
                threshold = max(3, ceil(len(previous_ids) * .30))
                if len(gone) >= threshold:
                    results["warnings"].append(
                        days[0] + ": " + str(len(gone)) + " previously listed in-scope "
                        "fixtures disappeared; review cancellations/provider changes.")
    if results["errors"]:
        results["status"] = "FAIL"
    elif results["warnings"]:
        results["status"] = "WARN"
    return results


def markdown(result):
    lines = ["# KB21 calendar health / " + result["days"][0], "",
             "**Status: " + result["status"] + "**  |  Source: API-Football only",
             "", "| Warsaw day | All events | In scope | Future candidates |",
             "|---|---:|---:|---:|"]
    for item in result["summaries"]:
        lines.append("| " + item["date"] + " | " +
                     str(item["provider_events"]) + " | " +
                     str(item["in_scope_events"]) + " | " +
                     str(item["eligible_candidates"]) + " |")
    for label, key in (("Errors", "errors"), ("Warnings", "warnings")):
        lines += ["", "## " + label]
        lines += ["- " + msg for msg in result[key]] or ["- None"]
    if result["excluded_known_id"]:
        lines += ["", "## Excluded known-competition fixtures"]
        for event in result["excluded_known_id"][:25]:
            lines.append("- " + str(event["date"]) + " / fixture " +
                         str(event["fixture_id"]) + " / league ID " +
                         str(event["league_id"]) + " / " + str(event["league"]))
    if result["previous_comparison"]:
        x = result["previous_comparison"]
        lines += ["", "Previous snapshot, same Warsaw day: " +
                  str(x["previous_in_scope"]) + " in scope, " +
                  str(x["current_in_scope"]) + " now, " +
                  str(x["missing"]) + " missing, " + str(x["added"]) + " added."]
    lines += ["", "No auto-PLAY, no original KB21 scoring, no register changes.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", default="reports/kb21_single_source")
    p.add_argument("--previous-dir", default="")
    p.add_argument("--output-dir", default="reports/kb21_health")
    p.add_argument("--summary-file", default="")
    args = p.parse_args()
    try:
        result = check(args.source_dir, args.previous_dir or None)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print("::error::KB21 calendar health failed: " + str(exc).replace("\n", " "))
        raise SystemExit(2)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calendar-health.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = markdown(result)
    (out / "calendar-health.md").write_text(md, encoding="utf-8")
    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    for warning in result["warnings"]:
        print("::warning::" + warning)
    for error in result["errors"]:
        print("::error::" + error)
    print("KB21 calendar health:", result["status"])
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
