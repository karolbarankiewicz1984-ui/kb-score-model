"""SINGLE-SOURCE KB21 calendar: API-Football only, Warsaw TODAY + TOMORROW.

The user intentionally accepts incomplete provider coverage: if a fixture is
not in this one successfully fetched provider response, it is OUT OF SCOPE.
No organizer/ESPN/football-data lookups, no 14x2 independent-signoff grid.

This is a NEW opt-in source-contract, NOT retroactive approval of the old
149 manual-calendar blockers, not STR/QUAL/MATCH or pre-odds P(model), and
never authorizes PLAY or writes historical KB21 N.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.api_market_http import ApiClient
from tools.kb21_api_prematch import in_scope

BASE = "https://v3.football.api-sports.io"
WARSAW = ZoneInfo("Europe/Warsaw")
SCHEMA = "kb21-api-football-single-source-two-day-v1"
DAY_SCHEMA = "kb21-api-football-single-source-day-v1"
MAX_PAGES = 25
MAX_EVENTS_PER_DAY = 10000
STOPPED = {"FT", "AET", "PEN", "CANC", "PST", "ABD", "AWD", "WO"}
FUTURE = {"NS"}
KNOWN_NONSTARTED = {"NS", "TBD", "PST", "CANC", "ABD", "AWD", "WO"}


def _iso_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def dates(start=None, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware now required")
    today = now.astimezone(WARSAW).date()
    if start is None:
        chosen = today
    else:
        if not isinstance(start, str):
            raise ValueError("Only ISO dates accepted")
        try:
            chosen = date.fromisoformat(start)
        except ValueError as exc:
            raise ValueError("Invalid ISO date") from exc
        if chosen.isoformat() != start or chosen != today:
            # Do not silently backfill previous dates or create retroactive
            # pre-match claims from a workflow_dispatch date override.
            raise ValueError("Live single-source mode must begin TODAY in Warsaw")
    return [chosen.isoformat(), (chosen + timedelta(days=1)).isoformat()]


def _page(response, target, requested_page):
    if not isinstance(response, dict):
        raise ValueError(f"{target}: API returned non-JSON-object")
    errors = response.get("errors")
    if errors not in ([], {}):
        raise ValueError(f"{target}: API error: {str(errors)[:300]}")
    if response.get("get") != "fixtures":
        raise ValueError(f"{target}: unexpected API endpoint")
    params = response.get("parameters")
    if (not isinstance(params, dict) or str(params.get("date")) != target
            or params.get("timezone") != "Europe/Warsaw"):
        raise ValueError(f"{target}: API response for wrong date/timezone")
    rows = response.get("response")
    if not isinstance(rows, list):
        raise ValueError(f"{target}: missing or malformed API fixtures response")
    results = response.get("results")
    if not isinstance(results, int) or isinstance(results, bool) or results != len(rows):
        raise ValueError(f"{target}: API results count differs from returned fixtures")
    pages = response.get("paging")
    if not isinstance(pages, dict):
        raise ValueError(f"{target}: pagination is missing")
    current, total = pages.get("current"), pages.get("total")
    if (not isinstance(current, int) or isinstance(current, bool)
            or not isinstance(total, int) or isinstance(total, bool)
            or current != requested_page or total < 0
            or total > MAX_PAGES or (total and requested_page > total)
            or (total == 0 and (requested_page != 1 or rows))):
        raise ValueError(f"{target}: invalid/incomplete pagination")
    if len(rows) > MAX_EVENTS_PER_DAY:
        raise ValueError(f"{target}: page exceeded safe source size")
    return rows, max(total, 1)


def _event(row, target, now):
    if not isinstance(row, dict):
        raise ValueError(f"{target}: malformed fixture row")
    fix, league, teams = row.get("fixture"), row.get("league"), row.get("teams")
    if not all(isinstance(x, dict) for x in (fix, league, teams)):
        raise ValueError(f"{target}: missing fixture/league/teams")
    ident = fix.get("id")
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        raise ValueError(f"{target}: fixture without unique positive ID")
    kickoff = _iso_datetime(fix.get("date"))
    if kickoff is None or kickoff.astimezone(WARSAW).date().isoformat() != target:
        raise ValueError(f"{target}: fixture {ident} has invalid/wrong Warsaw day")
    status_obj = fix.get("status") or {}
    status = status_obj.get("short") if isinstance(status_obj, dict) else None
    if not isinstance(status, str) or not status.strip():
        raise ValueError(f"{target}: fixture {ident} missing lifecycle status")
    name, country = league.get("name"), league.get("country")
    lid = league.get("id")
    if (not isinstance(name, str) or not name.strip()
            or not isinstance(country, str) or not country.strip()
            or not isinstance(lid, int) or isinstance(lid, bool)):
        raise ValueError(f"{target}: fixture {ident} missing league identity")
    h, a = teams.get("home"), teams.get("away")
    if not all(isinstance(x, dict) for x in (h, a)):
        raise ValueError(f"{target}: fixture {ident} has invalid teams")
    home, away = h.get("name"), a.get("name")
    if not all(isinstance(s, str) and s.strip() for s in (home, away)):
        # Some TBD fixtures have placeholders; they are not usable.
        if status == "NS":
            raise ValueError(f"{target}: scheduled fixture {ident} missing team names")
        home, away = str(home or "TBD"), str(away or "TBD")
    scoped = bool(in_scope(row))
    # "NS" only, with kickoff in future. Known live/cancelled/TBD/past
    # fixtures stay visible in provider_events but never become candidates.
    eligible = scoped and status in FUTURE and kickoff > now
    reason = ("CANDIDATE" if eligible else
              "OUTSIDE_KB21_COMPETITION_SCOPE" if not scoped else
              "NOT_SCHEDULED_STATUS_" + status if status != "NS" else
              "KICKOFF_ALREADY_STARTED")
    return {
        "fixture_id": ident, "date_warsaw": target,
        "kickoff_utc": kickoff.isoformat(),
        "kickoff_warsaw": kickoff.astimezone(WARSAW).isoformat(),
        "league_id": lid, "league": name, "country": country,
        "season": league.get("season"), "round": league.get("round"),
        "home": home, "away": away,
        "home_team_id": h.get("id"), "away_team_id": a.get("id"),
        "status": status, "status_long": status_obj.get("long"),
        "in_kb21_scope": scoped,
        "eligible_for_prematch_research": eligible,
        "candidate_status": reason,
        "provider": "API-Football",
        "calendar_source_count": 1,
    }


def collect_for_day(target, client, key, now):
    if not key:
        raise RuntimeError("Missing API_FOOTBALL_KEY; no false zero-game day")
    if not isinstance(target, str) or date.fromisoformat(target).isoformat() != target:
        raise ValueError("Invalid requested day")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Capture clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    events, seen = [], set()
    total_pages = None
    for page in range(1, MAX_PAGES + 1):
        payload, headers = client.get(
            BASE, key, "fixtures", date=target, timezone="Europe/Warsaw", page=page)
        rows, total = _page(payload, target, page)
        if total_pages is None:
            total_pages = total
        elif total != total_pages:
            raise ValueError(f"{target}: pagination changed mid-capture")
        for item in rows:
            event = _event(item, target, now)
            ident = event["fixture_id"]
            if ident in seen:
                raise ValueError(f"{target}: duplicate ID {ident} across pages")
            seen.add(ident)
            events.append(event)
        if len(events) > MAX_EVENTS_PER_DAY:
            raise ValueError(f"{target}: too many records")
        if page == total:
            break
    else:
        raise ValueError(f"{target}: pagination exceeded limit")
    events.sort(key=lambda r: (r["kickoff_utc"], r["fixture_id"]))
    candidates = [row for row in events if row["eligible_for_prematch_research"]]
    return {
        "schema": DAY_SCHEMA, "date": target, "source": "API-Football",
        "api_endpoint": "/fixtures?date=YYYY-MM-DD&timezone=Europe/Warsaw",
        "snapshot_utc": now.isoformat(), "query_timezone": "Europe/Warsaw",
        "api_pages_completed": total_pages,
        "provider_total_events": len(events),
        "in_scope_provider_events": sum(row["in_kb21_scope"] for row in events),
        "pre_match_fixtures": len(candidates),
        "provider_events": events, "candidates": candidates,
        "single_source_gate": "PASS_SOURCE",
        "provider_coverage_completeness_claim": False,
        "not_in_provider_means_out_of_scope": True,
        "api_error": None,
        "fixture_selection_rule": "ONLY_PROVIDER_PRESENT_SCHEDULED_NS_AND_FUTURE",
        "source_validation": "DATE_TIMEZONE_PAGINATION_ID_AND_STATUS_CHECKED",
        "manual_organizer_reviews_required_for_source_gate": 0,
        "calendar_gate_legacy": "UNCHANGED_NOT_EVALUATED",
        "safe_to_publish_play": False,
        "model_ready": False, "old_kb21_n_written": False,
    }


def build(now=None, client=None, key=None):
    now = now or datetime.now(timezone.utc)
    targets = dates(now=now)
    client = client or ApiClient()
    if key is None:
        key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY missing; cannot call provider")
    records = [collect_for_day(day, client, key, now) for day in targets]
    for record in records:
        if record["single_source_gate"] != "PASS_SOURCE":
            raise ValueError("Refusing incomplete provider day")
    return {
        "schema": SCHEMA, "dates": targets,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "authoritative_calendar_provider": "API-Football",
        "provider_count": 1,
        "source_of_truth_rule": "Only fixtures actually present in this API response are eligible; absent fixtures are ignored",
        "single_source_gate": "PASS_SOURCE",
        "legacy_149_missing_checks": "HISTORICAL_OLD_POLICY_NOT_REPAIRED",
        "legacy_42_manual_reviews": "NOT_REQUIRED_BY_NEW_SOURCE_POLICY",
        "total_provider_events": sum(x["provider_total_events"] for x in records),
        "total_research_candidates": sum(x["pre_match_fixtures"] for x in records),
        "days": records,
        "calendar_gate_legacy": "UNCHANGED_NOT_EVALUATED",
        "old_methodology_unchanged": True, "kb21_n_written": False,
        "safe_to_publish_play": False,
        "note": ("PASS_SOURCE certifies API response integrity ONLY, not complete "
                 "world coverage, event analysis, pre-odds P(model) or PLAY. "
                 "Other providers do not add missing fixtures."),
    }


def render_day(day):
    lines = [
        "# KB Score 2.1 — jeden terminarz / " + day["date"], "",
        "**GLOWNE ZRODLO: API-Football / SINGLE_SOURCE_GATE PASS_SOURCE.**",
        "**Nie jest to zgoda na PLAY ani przywrócenie STR/QUAL/MATCH/P(model).**", "",
        "Wszystkie zdarzenia zwrócone przez API: " + str(day["provider_total_events"]),
        "Zdarzenia w zakresie KB21: " + str(day["in_scope_provider_events"]),
        "Przyszłe NS zakwalifikowane do badania: " + str(day["pre_match_fixtures"]),
        "Odczyt UTC: " + day["snapshot_utc"] +
        "; stron API kompletnych: " + str(day["api_pages_completed"]),
        "", "| Godzina PL | Rozgrywki | Mecz | Status |",
        "|---|---|---|---|",
    ]
    for row in day["candidates"]:
        lines.append("| " + row["kickoff_warsaw"][11:16] + " | " +
                     row["league"] + " | " + row["home"] + " – " +
                     row["away"] + " | " + row["status"] + " |")
    if not day["candidates"]:
        lines.append("| — | — | Brak przyszłych meczów w zakresie KB21 "
                     "w prawidłowej odpowiedzi API | — |")
    lines += ["", "Nie dopisujemy meczów widocznych wyłącznie w ESPN, KNVB ani innych bazach.",
              "API zgłosi błąd, brak strony lub złą datę = FAIL_SOURCE, nie zero meczów.",
              "Prawidłowa pusta odpowiedź jest dopuszczalna; nie twierdzimy, "
              "że poza API nie ma innych spotkań.",
              "KB Score 2.1 nadal wymaga osobnej oceny sportowej i pre-price P(model).",
              ""]
    return "\n".join(lines)


def write_report(result, dest):
    if result.get("schema") != SCHEMA or len(result.get("days", [])) != 2:
        raise ValueError("Refuse incorrect source report")
    root = Path(dest)
    root.mkdir(parents=True, exist_ok=True)
    for day in result["days"]:
        base = "KB21_API_CALENDAR_" + day["date"]
        (root / (base + ".json")).write_text(
            json.dumps(day, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / (base + ".md")).write_text(render_day(day), encoding="utf-8")
    (root / "SINGLE_SOURCE_MANIFEST.json").write_text(
        json.dumps({key: value for key, value in result.items() if key != "days"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="reports/kb21_single_source")
    args = parser.parse_args()
    result = build()
    write_report(result, args.output_dir)
    print("KB21 SINGLE_SOURCE_GATE:", result["single_source_gate"],
          "; dates:", result["dates"],
          "; future in-scope:", result["total_research_candidates"],
          "; provider events:", result["total_provider_events"],
          "; manual calendar signatures: 0; PLAY: NO")


if __name__ == "__main__":
    main()
