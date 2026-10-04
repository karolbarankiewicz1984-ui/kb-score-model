#!/usr/bin/env python3
"""Patch the five-month international club backfill with UEFA Europa Conference League.

Merges Conference League matches into the existing API Coverage club snapshots.
Never modifies KB Score 2.1 CORE, KB/DEV registers, model parameters or N values.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
OUT = Path("data/api_football/international_5m")
CLUB_OUT = OUT / "club"
COMPETITION = "UEFA Europa Conference League"
FINISHED = {"FT", "AET", "PEN"}


def get(endpoint, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    last_error = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r), {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"API request failed after retries: {last_error}")


def stat_value(stats, name):
    for item in stats or []:
        if item.get("type") == name:
            return item.get("value")
    return None


def parse_team_stats(block):
    stats = block.get("statistics", [])
    return {
        "team_id": block.get("team", {}).get("id"),
        "team": block.get("team", {}).get("name"),
        "corners": stat_value(stats, "Corner Kicks"),
        "fouls": stat_value(stats, "Fouls"),
        "yellow": stat_value(stats, "Yellow Cards"),
        "red": stat_value(stats, "Red Cards"),
        "shots": stat_value(stats, "Total Shots"),
        "shots_on_goal": stat_value(stats, "Shots on Goal"),
        "shots_inside_box": stat_value(stats, "Shots insidebox"),
        "shots_outside_box": stat_value(stats, "Shots outsidebox"),
        "blocked_shots": stat_value(stats, "Blocked Shots"),
        "possession": stat_value(stats, "Ball Possession"),
        "passes": stat_value(stats, "Total passes"),
        "passes_accurate": stat_value(stats, "Passes accurate"),
        "offsides": stat_value(stats, "Offsides"),
        "goalkeeper_saves": stat_value(stats, "Goalkeeper Saves"),
    }


def daterange(start, end):
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        yield current.isoformat()
        current += timedelta(days=1)


def load_day(path, day):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema": "api-football-international-5m-v1",
        "category": "international_club",
        "date": day,
        "stored": 0,
        "competition_counts": {},
        "rows": [],
        "isolation": "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-05-04"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-10-03"
    CLUB_OUT.mkdir(parents=True, exist_ok=True)
    requests = 0
    added = 0
    day_errors = []
    detail_errors = []
    last_headers = {}

    for day in daterange(start, end):
        try:
            fixtures, last_headers = get("fixtures", date=day, timezone="Europe/Warsaw")
            requests += 1
        except Exception as exc:
            day_errors.append({"date": day, "error": str(exc)})
            continue
        if fixtures.get("errors"):
            day_errors.append({"date": day, "error": fixtures.get("errors")})
            continue

        matches = [g for g in fixtures.get("response", [])
                   if g.get("league", {}).get("name") == COMPETITION
                   and g.get("fixture", {}).get("status", {}).get("short") in FINISHED]
        if not matches:
            continue

        path = CLUB_OUT / f"{day}.json"
        payload = load_day(path, day)
        by_id = {r.get("fixture_id"): r for r in payload.get("rows", [])}

        for game in matches:
            fid = game.get("fixture", {}).get("id")
            if fid in by_id:
                continue
            try:
                detail, last_headers = get("fixtures/statistics", fixture=fid)
                requests += 1
                if detail.get("errors"):
                    raise RuntimeError(json.dumps(detail.get("errors"), ensure_ascii=False))
                blocks = detail.get("response", [])
            except Exception as exc:
                detail_errors.append({"date": day, "fixture_id": fid, "error": str(exc)})
                blocks = []

            row = {
                "category": "international_club",
                "fixture_id": fid,
                "date": game.get("fixture", {}).get("date"),
                "league_id": game.get("league", {}).get("id"),
                "competition": COMPETITION,
                "country": game.get("league", {}).get("country"),
                "season": game.get("league", {}).get("season"),
                "round": game.get("league", {}).get("round"),
                "home_id": game.get("teams", {}).get("home", {}).get("id"),
                "home": game.get("teams", {}).get("home", {}).get("name"),
                "away_id": game.get("teams", {}).get("away", {}).get("id"),
                "away": game.get("teams", {}).get("away", {}).get("name"),
                "goals": game.get("goals", {}),
                "score": game.get("score", {}),
                "teams": [parse_team_stats(b) for b in blocks],
            }
            by_id[fid] = row
            added += 1
            time.sleep(0.08)

        rows = sorted(by_id.values(), key=lambda x: x.get("fixture_id") or 0)
        payload["rows"] = rows
        payload["stored"] = len(rows)
        counts = {}
        for row in rows:
            comp = row.get("competition")
            counts[comp] = counts.get(comp, 0) + 1
        payload["competition_counts"] = counts
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Rebuild manifest from all stored day snapshots so totals are authoritative.
    manifest_path = OUT / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    club_counts = {}
    club_total = 0
    for path in CLUB_OUT.glob("*.json"):
        p = json.loads(path.read_text(encoding="utf-8"))
        club_total += int(p.get("stored", 0))
        for comp, count in p.get("competition_counts", {}).items():
            club_counts[comp] = club_counts.get(comp, 0) + int(count)
    comps = set(manifest.get("club_competitions", []))
    comps.discard("UEFA Conference League")
    comps.add(COMPETITION)
    manifest["club_competitions"] = sorted(comps)
    manifest.setdefault("stored", {})["international_club"] = club_total
    manifest.setdefault("competition_counts", {})["international_club"] = dict(sorted(club_counts.items()))
    manifest["conference_patch"] = {
        "added": added,
        "requests": requests,
        "day_errors": day_errors,
        "detail_errors": detail_errors,
        "rate_limit_remaining": last_headers.get("x-ratelimit-requests-remaining"),
    }
    manifest["isolation"] = "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES"
    manifest["model_effect"] = "NONE"
    manifest["kb_n_effect"] = 0
    manifest["dev_n_effect"] = 0
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"added": added, "requests": requests, "day_errors": len(day_errors),
                      "detail_errors": len(detail_errors), "club_total": club_total,
                      "kb_n_effect": 0, "dev_n_effect": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
