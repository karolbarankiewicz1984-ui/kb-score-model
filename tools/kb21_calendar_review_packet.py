"""Unsiged KB21 organizer review packet: per-league/day blockers, fixtures and time windows.

A configured adapter is not a signed complete calendar. This packet does NOT
authorize PLAY, verify no-match days, score games, or modify historical N.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from tools.kb21_calendar_evidence_dashboard import COMPETITIONS
from tools.kb21_fixture_crosscheck import _instant

ROLES = {
    "FULL_SEASON_FPL": "FULL_SEASON_SNAPSHOT_NOT_ATTESTATION",
    "UEFA_ARTICLE_DATE_TEAMS_ONLY": "DATE_TEAM_ONLY_NO_KICKOFF_PROOF",
    "BELGIAN_SELECTED_ROUND_UNDATED": "UNDATED_ROUND_ONLY",
    "HISTORICAL_2026_WC_CYCLE_CONTEXT": "HISTORICAL_CYCLE_NOT_A_DAY_CALENDAR",
    "NO_DIRECT_MACHINE_ADAPTER": "NO_DIRECT_SOURCE",
}


def build(queue, gate, dashboard, now=None):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)
            or not isinstance(gate, dict) or not isinstance(gate.get("days"), dict)
            or not isinstance(dashboard, dict) or not isinstance(dashboard.get("rows"), list)):
        raise ValueError("Invalid Calendar Gate packet inputs")
    days = queue["days"]
    if (not 1 <= len(days) <= 3 or len(set(days)) != len(days)
            or set(gate["days"]) != set(days)
            or set(dashboard.get("days", [])) != set(days)
            or gate.get("calendar_gate") != dashboard.get("calendar_gate")):
        raise ValueError("Review packet calendar scope mismatch")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    expected = {(day, league) for day in days for league in COMPETITIONS}
    dashboard_rows = {}
    for row in dashboard["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid dashboard source row")
        key = row.get("day"), row.get("league_id")
        if key not in expected or key in dashboard_rows:
            raise ValueError("Unexpected or duplicate source day/league")
        dashboard_rows[key] = row
    if set(dashboard_rows) != expected:
        raise ValueError("All fourteen competitions required for every date")
    official_errors = {}
    for day in days:
        value = gate["days"][day]
        if not isinstance(value, dict) or not isinstance(value.get("competitions"), list):
            raise ValueError("Missing validated organizer competition checks")
        for row in value["competitions"]:
            if not isinstance(row, dict) or not isinstance(row.get("errors"), list):
                raise ValueError("Invalid organizer blocker list")
            key = day, row.get("league_id")
            if key not in expected or key in official_errors:
                raise ValueError("Unrecognized or duplicate formal blocker scope")
            if not all(isinstance(e, str) and e for e in row["errors"]):
                raise ValueError("Malformed formal blocker")
            official_errors[key] = sorted(set(row["errors"]))
    if set(official_errors) != expected:
        raise ValueError("Missing formal competition/day errors")
    fixtures = {key: [] for key in expected}
    seen = set()
    for item in queue["fixtures"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid independent candidate")
        fixture_id = item.get("fixture_id")
        if not isinstance(fixture_id, str) or ":" not in fixture_id or fixture_id in seen:
            raise ValueError("Invalid or duplicated candidate ID")
        seen.add(fixture_id)
        key = item.get("date_warsaw"), fixture_id.rsplit(":", 1)[0]
        if key not in expected:
            raise ValueError("Candidate outside official calendar scope")
        kickoff = _instant(item.get("kickoff"))
        fixtures[key].append({
            "fixture_id": fixture_id,
            "fixture": item.get("fixture") if isinstance(item.get("fixture"), str) else None,
            "kickoff_source": item.get("kickoff"),
            "kickoff_utc": kickoff.astimezone(timezone.utc).isoformat() if kickoff else None,
            "organizer_confirmed": False,
        })
    rows, blockers = [], Counter()
    for day in days:
        for league in COMPETITIONS:
            key = day, league
            source = dashboard_rows[key]
            url = source.get("organizer_review_url")
            if url and (urlsplit(url).scheme != "https" or not urlsplit(url).hostname):
                raise ValueError("Invalid organizer entry URL")
            candidates = fixtures[key]
            count = source.get("espn_candidates")
            matched = source.get("paired_for_review")
            if (count != len(candidates) or not isinstance(matched, int)
                    or isinstance(matched, bool) or not 0 <= matched <= count):
                raise ValueError("Inconsistent source review/candidate counts")
            official = official_errors[key]
            blockers.update(official)
            times = [_instant(c.get("kickoff_source")) for c in candidates]
            known = [x for x in times if x is not None]
            first = min(known) if known else None
            if candidates and len(known) != len(candidates):
                time_status = "MISSING_KICKOFF_NO_PREMATCH_PROOF"
            elif first and first <= now:
                time_status = "FIRST_KICKOFF_PASSED_NO_RETROACTIVE_APPROVAL"
            elif first:
                time_status = "FUTURE_FIRST_KICKOFF_MANUAL_REVIEW_REQUIRED"
            else:
                time_status = "ZERO_CANDIDATES_NOT_CONFIRMED_ZERO_DAY"
            source_status = source.get("evidence_status")
            if candidates and (matched != count or source_status in (
                    "SOURCE_ISSUES_REQUIRING_REVIEW",
                    "DIRECT_SOURCE_MISSING",
                    "MISSING_OR_CONFLICTING_CANDIDATES",
                    "ORGANIZER_ONLY_FIXTURES")):
                priority = 1
            elif candidates:
                priority = 2
            else:
                priority = 3
            rows.append({
                "day": day, "league_id": league, "competition": COMPETITIONS[league],
                "priority": priority, "organizer_url": url,
                "source_file": source.get("adapter_source"),
                "comparison_file": source.get("adapter_comparison"),
                "source_role": ROLES.get(source.get("direct_evidence_scope"),
                                         "PARTIAL_DIAGNOSTIC_SOURCE"),
                "source_status": source_status,
                "fixtures": sorted(candidates,
                                   key=lambda c: (c["kickoff_utc"] or "9999", c["fixture_id"])),
                "independent_candidates": count, "paired_only_for_review": matched,
                "first_candidate_kickoff_utc": first.astimezone(timezone.utc).isoformat()
                if first else None,
                "time_status": time_status,
                "formal_errors": official,
                "source_errors": source.get("source_errors", []),
                "full_day_approved_by_this_packet": False,
                "reviewer": None, "manual_review_required": True,
                "calendar_gate": "BLOCKED",
            })
    rows.sort(key=lambda x: (x["day"], x["priority"],
                              -x["independent_candidates"], x["league_id"]))
    return {
        "schema": "kb21-calendar-review-packet-v1",
        "days": days, "generated_at_utc": now.isoformat(), "rows": rows,
        "totals": {
            "league_day_reviews": len(rows),
            "adapters_configured": dashboard.get("totals", {}).get("direct_adapters"),
            "fixtures_to_review": len(queue["fixtures"]),
            "diagnostic_pairs_only": sum(x["paired_only_for_review"] for x in rows),
            "source_day_signoffs_from_packet": 0,
            "formal_blocker_occurrences": sum(blockers.values()),
            "formal_blocker_types": dict(sorted(blockers.items())),
            "day_league_checks_after_first_kickoff": sum(
                x["time_status"] == "FIRST_KICKOFF_PASSED_NO_RETROACTIVE_APPROVAL"
                for x in rows),
        },
        "publication": "DIAGNOSTIC / NO PLAY",
        "safe_to_publish_play": False,
        "calendar_gate": "BLOCKED",
        "note": ("Unsigned diagnostic aid. Pair agreement is not organizer "
                 "authentication. An empty source is not verified zero. "
                 "The reviewer must independently inspect full dated official "
                 "schedules before first kickoff and sign using the existing "
                 "Calendar Gate protocol."),
    }


def render(packet):
    total = packet["totals"]
    lines = [
        "# KB Score 2.1 — szczegółowa karta kontroli terminarzy",
        "", "**NIE PLAY — BRAK AUTOMATYCZNEGO PODPISU**", "",
        "Stan UTC: " + packet["generated_at_utc"],
        "Adaptery: " + str(total["adapters_configured"]) + "/14 (nie oznacza pełnej weryfikacji)",
        "Pozycji organizator/dzień: " + str(total["league_day_reviews"]),
        "Kandydaci ESPN: " + str(total["fixtures_to_review"]) +
        "; porównania diagnostyczne: " + str(total["diagnostic_pairs_only"]),
        "Błędy formalne na poziomie rozgrywek: " + str(total["formal_blocker_occurrences"]),
        "Przekroczony początek pierwszego meczu (liga/dzień): " +
        str(total["day_league_checks_after_first_kickoff"]),
        "", "## Najczęstsze błędy formalne", "",
    ]
    for code, count in sorted(total["formal_blocker_types"].items(),
                              key=lambda p: (-p[1], p[0]))[:12]:
        lines.append("- " + str(count) + " × " + code)
    for day in packet["days"]:
        lines += ["", "## " + day, "",
                  "| P | Liga | ESPN | Porównane | Zakres dowodu | Okno czasowe |",
                  "|---|---|---:|---:|---|---|"]
        daily = [row for row in packet["rows"] if row["day"] == day]
        for row in daily:
            lines.append("| P" + str(row["priority"]) + " | " + row["competition"]
                         + " | " + str(row["independent_candidates"])
                         + " | " + str(row["paired_only_for_review"])
                         + " | " + row["source_role"]
                         + " | " + row["time_status"] + " |")
        lines += ["", "### Zadania z konkretnymi dowodami", ""]
        for row in daily:
            url = ("[oficjalny kalendarz](" + row["organizer_url"] + ")"
                   if row["organizer_url"] else "BRAK URL")
            lines.append("#### P" + str(row["priority"]) + " " +
                         row["competition"] + " — " + url)
            lines.append("Źródło: " + str(row["source_status"]) + " / " +
                         row["source_role"] + "; pierwszy start ESPN: " +
                         str(row["first_candidate_kickoff_utc"] or "nieznany") +
                         "; " + row["time_status"])
            for event in row["fixtures"]:
                lines.append("- ESPN " + event["fixture_id"] + " "
                             + str(event["fixture"]) + " / " +
                             str(event["kickoff_source"]) +
                             " (niezatwierdzony czas organizatora)")
            for error in row["formal_errors"]:
                lines.append("- BLOKADA: " + error)
            for error in row["source_errors"][:4]:
                lines.append("- PROBLEM POBRANIA: " + str(error))
            if not row["fixtures"]:
                lines.append("- Brak kandydatów nie oznacza oficjalnie pustego dnia.")
            lines.append("")
    lines += ["", "Przed zatwierdzeniem: pełna, aktualna karta organizatora, "
              "godziny i strefa czasowa, niezależne porównanie oraz osobista "
              "weryfikacja przed pierwszym meczem. "
              "Ten raport nigdy nie zatwierdza PLAY ani historycznego N.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("gate")
    p.add_argument("dashboard")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    obj = build(
        json.loads(Path(a.queue).read_text(encoding="utf-8")),
        json.loads(Path(a.gate).read_text(encoding="utf-8")),
        json.loads(Path(a.dashboard).read_text(encoding="utf-8")),
    )
    for filename, value in (
        (a.output_json, json.dumps(obj, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(obj))):
        dest = Path(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding="utf-8")
    print("KB21 calendar review packet:", obj["totals"], "NO PLAY")


if __name__ == "__main__":
    main()
