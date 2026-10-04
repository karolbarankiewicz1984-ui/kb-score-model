#!/usr/bin/env python3
"""Five-month API-Football backfill for international club and national-team matches.

This is an API Coverage data layer only. It NEVER changes KB Score 2.1 CORE,
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
OUT = Path("data/api_football/international_5m")
FINISHED = {"FT", "AET", "PEN"}

CLUB_COMPETITIONS = {
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Conference League",
    "UEFA Super Cup",
}

NATIONAL_COMPETITIONS = {
    "World Cup",
    "World Cup - Qualification Europe",
    "Euro Championship",
    "Euro Championship - Qualification",
    "UEFA Nations League",
    "Friendlies",
}


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


def category(game):
    name = game.get("league", {}).get("name")
    if name in CLUB_COMPETITIONS:
        return "international_club"
    if name in NATIONAL_COMPETITIONS:
        return "national_team"
    return None


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


def load_existing(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-05-04"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-10-03"
    club_out = OUT / "club"
    national_out = OUT / "national"
    club_out.mkdir(parents=True, exist_ok=True)
    national_out.mkdir(parents=True, exist_ok=True)

    request_count = 0
    totals = {"international_club": 0, "national_team": 0}
    competition_counts = {"international_club": {}, "national_team": {}}
    day_errors = []
    detail_errors = []
    last_headers = {}

    for day in daterange(start, end):
        club_path = club_out / f"{day}.json"
        national_path = national_out / f"{day}.json"
        old_club = load_existing(club_path)
        old_national = load_existing(national_path)
        if old_club is not None and old_national is not None:
            for cat, old in [("international_club", old_club), ("national_team", old_national)]:
                totals[cat] += int(old.get("stored", 0))
                for comp, count in old.get("competition_counts", {}).items():
                    competition_counts[cat][comp] = competition_counts[cat].get(comp, 0) + int(count)
            print(f"SKIP {day}: snapshots exist")
            continue

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

        rows = {"international_club": [], "national_team": []}
        daily_counts = {"international_club": {}, "national_team": {}}

        for game in fixtures.get("response", []):
            cat = category(game)
            if not cat:
                continue
            if game.get("fixture", {}).get("status", {}).get("short") not in FINISHED:
                continue

            fid = game.get("fixture", {}).get("id")
            try:
                detail, last_headers = get("fixtures/statistics", fixture=fid)
                request_count += 1
                if detail.get("errors"):
                    raise RuntimeError(json.dumps(detail.get("errors"), ensure_ascii=False))
                blocks = detail.get("response", [])
            except Exception as exc:
                detail_errors.append({"date": day, "fixture_id": fid, "category": cat, "error": str(exc)})
                blocks = []

            comp = game.get("league", {}).get("name")
            daily_counts[cat][comp] = daily_counts[cat].get(comp, 0) + 1
            competition_counts[cat][comp] = competition_counts[cat].get(comp, 0) + 1
            rows[cat].append({
                "category": cat,
                "fixture_id": fid,
                "date": game.get("fixture", {}).get("date"),
                "league_id": game.get("league", {}).get("id"),
                "competition": comp,
                "country": game.get("league", {}).get("country"),
                "season": game.get("league", {}).get("season"),
                "round": game.get("league", {}).get("round"),
                "home_id": game.get("teams", {}).get("home", {}).get("id"),
                "home": game.get("teams", {}).get("home", {}).get("name"),
                "away_id": game.get("teams", {}).get("away", {}).get("id"),
                "away": game.get("teams", {}).get("away", {}).get("name"),
                "goals": game.get("goals", {}),
                "score": game.get("score", {}),
                "teams": [parse_team_stats(block) for block in blocks],
            })
            time.sleep(0.08)

        for cat, path in [("international_club", club_path), ("national_team", national_path)]:
            rows[cat].sort(key=lambda x: x.get("fixture_id") or 0)
            totals[cat] += len(rows[cat])
            payload = {
                "schema": "api-football-international-5m-v1",
                "category": cat,
                "date": day,
                "stored": len(rows[cat]),
                "competition_counts": daily_counts[cat],
                "rows": rows[cat],
                "isolation": "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
                "model_effect": "NONE",
                "kb_n_effect": 0,
                "dev_n_effect": 0,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK {day}: club={len(rows['international_club'])}, national={len(rows['national_team'])}")

    manifest = {
        "schema": "api-football-international-5m-manifest-v1",
        "requested_window": {"from": start, "to": end},
        "club_competitions": sorted(CLUB_COMPETITIONS),
        "national_competitions": sorted(NATIONAL_COMPETITIONS),
        "requests_this_run": request_count,
        "stored": totals,
        "competition_counts": {
            "international_club": dict(sorted(competition_counts["international_club"].items())),
            "national_team": dict(sorted(competition_counts["national_team"].items())),
        },
        "day_errors": day_errors,
        "detail_errors": detail_errors,
        "rate_limit_remaining": last_headers.get("x-ratelimit-requests-remaining"),
        "isolation": "API_COVERAGE_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }
    (OUT / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "from": start,
        "to": end,
        "stored": totals,
        "requests_this_run": request_count,
        "day_errors": len(day_errors),
        "detail_errors": len(detail_errors),
        "output": str(OUT),
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
