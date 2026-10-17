"""Compare TWO real, pre-first-kickoff snapshots of KNVB/FPL/DFL schedules.

A single archival capture is evidence of one source state, not stability.
Two genuinely earlier captures can reveal a removed, added or rescheduled
fixture. They NEVER establish official full-day completeness or human signoff.
Historical/current-day captures after first ESPN kickoff are NOT retroactively
considered pre-match. Missing ESPN kickoffs fail closed.
"""
import argparse
from collections import Counter
from datetime import date, timedelta, timezone
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team
from tools.kb21_pregame_vault import KIND, verify

SCHEMA = "kb21-early-official-revision-audit-v1"
LEAGUE_KIND = {league: name for name, (league, _) in KIND.items()}


def _pairs(league, rows):
    found = {}
    for fixture in rows:
        if not isinstance(fixture, dict):
            raise ValueError("Invalid official fixture object")
        home, away = fixture.get("home"), fixture.get("away")
        if not isinstance(home, str) or not isinstance(away, str):
            raise ValueError("Organizer names missing")
        pair = (_team(league, home), _team(league, away))
        if not all(pair) or pair[0] == pair[1] or pair in found:
            raise ValueError("Duplicate/ambiguous organizer team pair")
        kickoff = _instant(fixture.get("kickoff_utc"))
        found[pair] = kickoff.astimezone(timezone.utc).isoformat() if kickoff else None
    return found


def compare(queue, vaults):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid independent candidate queue")
    days = queue["days"]
    if not 1 <= len(days) <= 3 or len(days) != len(set(days)):
        raise ValueError("Expected one to three unique target dates")
    for day in days:
        date.fromisoformat(day)
    day_early = {}
    by_day = {}
    for day in days:
        events = [f for f in queue["fixtures"] if f.get("date_warsaw") == day]
        instants = [_instant(f.get("kickoff")) for f in events]
        by_day[day] = events
        day_early[day] = (
            min(instants) if events and len(instants) == len(events)
            and all(x is not None for x in instants) else None
        )
    for fixture in queue["fixtures"]:
        if fixture.get("date_warsaw") not in days:
            raise ValueError("Independent fixture outside target calendar window")

    # Verify each archive once. A rejected archive can never be counted.
    validated = []
    for folder in vaults:
        manifest, docs = verify(folder)
        validated.append((Path(folder).name, manifest, docs))
    rows = []
    for day in days:
        for league, kind in LEAGUE_KIND.items():
            candidates = [f for f in by_day[day]
                          if str(f.get("fixture_id", "")).startswith(league + ":")]
            deadline = day_early[day]
            row = {
                "day": day, "league_id": league,
                "independent_fixture_candidates": len(candidates),
                "earliest_independent_day_kickoff_utc": (
                    deadline.astimezone(timezone.utc).isoformat()
                    if deadline is not None else None),
                "eligible_snapshot_count": 0,
                "first_capture_utc": None, "last_capture_utc": None,
                "earlier_organizer_count": None, "later_organizer_count": None,
                "added_pairs": [], "removed_pairs": [],
                "kickoff_changes": [],
                "status": "NO_SAFE_EARLIEST_WHOLE_DAY_KICKOFF",
                "full_organizer_day_attested": False,
                "human_signed": False, "calendar_gate": "BLOCKED",
            }
            if deadline is None:
                rows.append(row)
                continue
            eligible = []
            for archive_name, manifest, docs in validated:
                if day not in manifest["days"] or kind not in docs:
                    continue
                doc = docs[kind]
                capture = _instant(doc.get("captured_at_utc"))
                if (capture is None or capture >= deadline
                        or capture.date() < date.fromisoformat(day) - timedelta(days=3)):
                    continue
                if doc.get("errors"):
                    continue
                if (kind == "fpl"
                        and doc.get("season_full_380_catalogue") is not True):
                    continue
                if (kind == "knvb" and doc.get("status")
                        != "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW"):
                    continue
                if (kind == "dfl" and (
                        doc.get("status") != "OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW"
                        or doc.get("table_headers_detected") is not True
                        or doc.get("page_invalid_row_count") != 0)):
                    continue
                eligible.append((capture, archive_name, doc))
            eligible.sort(key=lambda item: (item[0], item[1]))
            row["eligible_snapshot_count"] = len(eligible)
            if not eligible:
                row["status"] = "NO_EARLY_OFFICIAL_SNAPSHOT"
                rows.append(row)
                continue
            first, last = eligible[0], eligible[-1]
            row["first_capture_utc"] = first[0].astimezone(timezone.utc).isoformat()
            row["last_capture_utc"] = last[0].astimezone(timezone.utc).isoformat()
            early_pairs = _pairs(league, first[2]["by_day"][day])
            late_pairs = _pairs(league, last[2]["by_day"][day])
            row["earlier_organizer_count"] = len(early_pairs)
            row["later_organizer_count"] = len(late_pairs)
            if len(eligible) < 2:
                row["status"] = "SINGLE_EARLY_SNAPSHOT_NO_DRIFT_COMPARISON"
                rows.append(row)
                continue
            if first[0] == last[0] and first[1] != last[1]:
                row["status"] = "SIMULTANEOUS_ARCHIVES_CANNOT_ORDER"
                rows.append(row)
                continue
            row["added_pairs"] = [
                {"home": h, "away": a, "latest_kickoff_utc": late_pairs[h, a]}
                for h, a in sorted(late_pairs.keys() - early_pairs.keys())
            ]
            row["removed_pairs"] = [
                {"home": h, "away": a, "earliest_kickoff_utc": early_pairs[h, a]}
                for h, a in sorted(early_pairs.keys() - late_pairs.keys())
            ]
            row["kickoff_changes"] = [
                {"home": h, "away": a, "old_kickoff_utc": early_pairs[h, a],
                 "new_kickoff_utc": late_pairs[h, a]}
                for h, a in sorted(early_pairs.keys() & late_pairs.keys())
                if early_pairs[h, a] != late_pairs[h, a]
            ]
            row["status"] = (
                "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW"
                if row["added_pairs"] or row["removed_pairs"] or row["kickoff_changes"]
                else "NO_CHANGE_BETWEEN_OBSERVED_EARLY_SNAPSHOTS"
            )
            rows.append(row)
    status_counts = Counter(x["status"] for x in rows)
    return {
        "schema": SCHEMA, "days": days, "rows": rows,
        "summary": {
            "league_day_cells": len(rows),
            "with_two_eligible_captures": sum(x["eligible_snapshot_count"] >= 2
                and x["status"] != "SIMULTANEOUS_ARCHIVES_CANNOT_ORDER" for x in rows),
            "with_organizer_changes": status_counts[
                "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW"],
            "single_eligible_capture": status_counts[
                "SINGLE_EARLY_SNAPSHOT_NO_DRIFT_COMPARISON"],
            "without_safe_earliest_kickoff": status_counts[
                "NO_SAFE_EARLIEST_WHOLE_DAY_KICKOFF"],
            "statuses": dict(sorted(status_counts.items())),
        },
        "calendar_gate": "BLOCKED", "safe_to_publish_play": False,
        "note": ("Comparing actual two pre-start snapshots is an unsigned "
                 "source revision check only. No match may be approved, "
                 "no zero-game day certified, no betting observations added."),
    }


def render(report):
    s = report["summary"]
    lines = [
        "# KB Score 2.1 — zmiany oficjalnych terminarzy między porannymi odczytami",
        "", "**WYŁĄCZNIE DIAGNOSTYKA — NIE PLAY**", "",
        "Dni: " + ", ".join(report["days"]),
        f"Kontrole źródło/dzień: {s['league_day_cells']}; porównane po dwóch "
        f"wcześniejszych pobraniach: {s['with_two_eligible_captures']}; "
        f"wykryte zmiany: {s['with_organizer_changes']}.",
        "", "| Dzień | Liga | Wczesne źródła | Stan | Dodane | Usunięte | Zmieniony czas |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for row in report["rows"]:
        lines.append(f"| {row['day']} | {row['league_id']} | "
                     f"{row['eligible_snapshot_count']} | {row['status']} | "
                     f"{len(row['added_pairs'])} | {len(row['removed_pairs'])} | "
                     f"{len(row['kickoff_changes'])} |")
        if row["status"] == "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW":
            lines.append(f"- **WYMAGA KONTROLI {row['day']} {row['league_id']}** "
                         f"({row['first_capture_utc']} → {row['last_capture_utc']}): "
                         + json.dumps({
                             "dodane": row["added_pairs"],
                             "usuniete": row["removed_pairs"],
                             "zmiany_godziny": row["kickoff_changes"],
                         }, ensure_ascii=False))
    lines.extend(["", "Zgodność dwóch odczytów NIE potwierdza kompletności "
                  "całego dnia, braku meczów, prawidłowości godzin ani "
                  "bezpieczeństwa publikacji typów.", ""])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queue", required=True)
    p.add_argument("--vault-dir", required=True)
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    queue = json.loads(Path(a.queue).read_text(encoding="utf-8"))
    root = Path(a.vault_dir)
    folders = sorted(p.parent for p in root.glob("*/manifest.json"))
    report = compare(queue, folders)
    for name, text in (
        (a.output_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(report))):
        file = Path(name)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
    print("KB21 official pregame revision audit:", report["summary"], "NO PLAY")


if __name__ == "__main__":
    main()
