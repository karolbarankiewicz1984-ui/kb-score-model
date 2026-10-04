#!/usr/bin/env python3
"""Five-month API-Football backfill for the KB Score API Coverage data layer.

This collector is deliberately isolated from KB Score 2.1 CORE. It stores only
factual finished-match data under data/api_football/backfill_5m and NEVER writes
KB/DEV registers, model parameters, KB N or DEV N.
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
OUT = Path("data/api_football/backfill_5m")

# Main European domestic leagues selected for the first API Coverage backfill.
DOMESTIC = {
    ("England", "Premier League"),
    ("Spain", "La Liga"),
    ("Italy", "Serie A"),
    ("Germany", "Bundesliga"),
    ("France", "Ligue 1"),
    ("Portugal", "Primeira Liga"),
    ("Netherlands", "Eredivisie"),
    ("Belgium", "Jupiler Pro League"),
    ("Turkey", "Süper Lig"),
    ("Poland", "Ekstraklasa"),
}
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
                payload = json.load(r)
                headers = {k.lower(): v for k, v in r.headers.items()}
            return payload, headers
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


def wanted(game):
    league = game.get("league", {})
    return (league.get("country"), league.get("name")) in DOMESTIC


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
    if stop < current:
        raise ValueError("TO must be >= FROM")
    if (stop - current).days > 190:
        raise ValueError("Backfill safety limit is 191 days")
    while current <= stop:
        yield current.isoformat()
        current += timedelta(days=1)


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-05-04"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-10-03"
    OUT.mkdir(parents=True, exist_ok=True)

    request_count = 0
    total_fixtures = 0
    stored_rows = 0
    detail_errors = []
    day_errors = []
    league_counts = {}
    last_headers = {}

    for day in daterange(start, end):
        path = OUT / f"{day}.json"
        # Idempotent/resumable: keep an already collected daily snapshot.
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                total_fixtures += int(old.get("finished_whitelist_fixtures", 0))
                stored_rows += int(old.get("stored", 0))
                for league, count in old.get("league_counts", {}).items():
                    league_counts[league] = league_counts.get(league, 0) + int(count)
                print(f"SKIP {day}: snapshot exists")
                continue
            except Exception:
                pass

        try:
            fixtures, last_headers = get("fixtures", date=day, timezone="Europe/Warsaw")
            request_count += 1
        except Exception as exc:
            day_errors.append({"date": day, "stage": "fixtures", "error": str(exc)})
            print(f"ERROR fixtures {day}: {exc}")
            continue

        if fixtures.get("errors"):
            day_errors.append({"date": day, "stage": "fixtures", "error": fixtures.get("errors")})
            print(f"API ERROR fixtures {day}: {fixtures.get('errors')}")
            continue

        games = [
            game for game in fixtures.get("response", [])
            if wanted(game)
            and game.get("fixture", {}).get("status", {}).get("short") in FINISHED
        ]
        rows = []
        daily_leagues = {}

        for game in games:
            fid = game.get("fixture", {}).get("id")
            try:
                detail, last_headers = get("fixtures/statistics", fixture=fid)
                request_count += 1
                if detail.get("errors"):
                    raise RuntimeError(json.dumps(detail.get("errors"), ensure_ascii=False))
                blocks = detail.get("response", [])
            except Exception as exc:
                detail_errors.append({"date": day, "fixture_id": fid, "error": str(exc)})
                blocks = []

            teams = [parse_team_stats(block) for block in blocks]
            league_name = game.get("league", {}).get("name")
            country = game.get("league", {}).get("country")
            label = f"{country} | {league_name}"
            daily_leagues[label] = daily_leagues.get(label, 0) + 1
            league_counts[label] = league_counts.get(label, 0) + 1

            rows.append({
                "fixture_id": fid,
                "date": game.get("fixture", {}).get("date"),
                "league_id": game.get("league", {}).get("id"),
                "league": league_name,
                "country": country,
                "season": game.get("league", {}).get("season"),
                "round": game.get("league", {}).get("round"),
                "home_id": game.get("teams", {}).get("home", {}).get("id"),
                "home": game.get("teams", {}).get("home", {}).get("name"),
                "away_id": game.get("teams", {}).get("away", {}).get("id"),
                "away": game.get("teams", {}).get("away", {}).get("name"),
                "goals": game.get("goals", {}),
                "score": game.get("score", {}),
                "teams": teams,
            })
            time.sleep(0.08)

        rows.sort(key=lambda x: x.get("fixture_id") or 0)
        daily_payload = {
            "schema": "api-football-backfill-5m-v1",
            "date": day,
            "finished_whitelist_fixtures": len(games),
            "stored": len(rows),
            "league_counts": daily_leagues,
            "rows": rows,
            "isolation": "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
            "model_effect": "NONE",
            "kb_n_effect": 0,
            "dev_n_effect": 0,
        }
        path.write_text(json.dumps(daily_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_fixtures += len(games)
        stored_rows += len(rows)
        print(f"OK {day}: {len(rows)} matches")

    manifest = {
        "schema": "api-football-backfill-5m-manifest-v1",
        "requested_window": {"from": start, "to": end},
        "leagues": sorted([f"{c} | {l}" for c, l in DOMESTIC]),
        "requests_this_run": request_count,
        "finished_whitelist_fixtures": total_fixtures,
        "stored_rows": stored_rows,
        "league_counts": dict(sorted(league_counts.items())),
        "day_errors": day_errors,
        "detail_errors": detail_errors,
        "rate_limit_remaining": last_headers.get("x-ratelimit-requests-remaining"),
        "isolation": "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }
    (OUT / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "from": start,
        "to": end,
        "stored_rows": stored_rows,
        "requests_this_run": request_count,
        "day_errors": len(day_errors),
        "detail_errors": len(detail_errors),
        "output": str(OUT),
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
