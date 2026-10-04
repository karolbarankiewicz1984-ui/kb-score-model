#!/usr/bin/env python3
"""Read-only API-Football quality/coverage probe for KB Score Data Lab.

Hard isolation contract:
- NEVER writes Rejestr/Rynki_DEV/Parametry/Kalibracja
- NEVER changes KB N or DEV N
- NEVER changes model weights, thresholds or decisions
- output is diagnostic JSON only
"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
TARGET_COUNTRIES = {"England","Spain","Italy","Germany","France","Portugal","Netherlands","Belgium","Turkey"}
TARGET_WORDS = ("Nations League","Champions League","Europa League","Conference League")
MAX_STAT_CALLS = 12  # safe on free quota; one fixtures call + <=12 stats calls


def api_get(endpoint: str, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
        headers = dict(r.headers.items())
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data, headers


def stat_value(stats, name):
    for item in stats or []:
        if item.get("type") == name:
            return item.get("value")
    return None


def wanted(g):
    league = g.get("league", {})
    return league.get("country") in TARGET_COUNTRIES or any(w.lower() in str(league.get("name", "")).lower() for w in TARGET_WORDS)


def team_stats(block):
    s = block.get("statistics", [])
    return {
        "team": block.get("team", {}).get("name"),
        "shots": stat_value(s, "Total Shots"),
        "shots_on_goal": stat_value(s, "Shots on Goal"),
        "corners": stat_value(s, "Corner Kicks"),
        "fouls": stat_value(s, "Fouls"),
        "yellow_cards": stat_value(s, "Yellow Cards"),
        "red_cards": stat_value(s, "Red Cards"),
        "possession": stat_value(s, "Ball Possession"),
    }


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        raise SystemExit("Usage: api_football_probe.py YYYY-MM-DD")

    fixtures, headers = api_get("fixtures", date=date, timezone="Europe/Warsaw")
    games = fixtures.get("response", [])
    relevant = [g for g in games if wanted(g)]
    completed = [g for g in relevant if g.get("fixture", {}).get("status", {}).get("short") in {"FT","AET","PEN"}]

    # Prefer relevant completed matches and stop after enough calls.
    samples = []
    coverage = {"full_core":0,"partial":0,"none":0}
    for g in completed[:MAX_STAT_CALLS]:
        fid = g["fixture"]["id"]
        data, _ = api_get("fixtures/statistics", fixture=fid)
        blocks = data.get("response", [])
        teams = [team_stats(b) for b in blocks]
        # Core DEV fields: corners, fouls, yellow cards for both teams.
        core_vals = [t.get(k) for t in teams for k in ("corners","fouls","yellow_cards")]
        if len(teams) == 2 and all(v is not None for v in core_vals):
            quality = "FULL_CORE"
            coverage["full_core"] += 1
        elif teams:
            quality = "PARTIAL"
            coverage["partial"] += 1
        else:
            quality = "NONE"
            coverage["none"] += 1
        samples.append({
            "fixture_id": fid,
            "league": g.get("league", {}).get("name"),
            "country": g.get("league", {}).get("country"),
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "quality": quality,
            "teams": teams,
        })

    league_summary = {}
    for g in relevant:
        key = f"{g.get('league',{}).get('country')} | {g.get('league',{}).get('name')}"
        league_summary[key] = league_summary.get(key, 0) + 1

    out = {
        "date": date,
        "all_fixtures": len(games),
        "relevant_fixtures": len(relevant),
        "relevant_completed": len(completed),
        "stat_calls_made": len(samples),
        "coverage_sample": coverage,
        "relevant_leagues": dict(sorted(league_summary.items(), key=lambda x: (-x[1], x[0]))),
        "samples": samples,
        "rate_limit_remaining": headers.get("x-ratelimit-requests-remaining"),
        "isolation": "DATA_LAB_ONLY_NO_KB_OR_DEV_N_WRITES",
        "next_use": "DIAGNOSTIC_ONLY_NOT_MODEL_INPUT",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
