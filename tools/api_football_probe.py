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
MAX_STAT_CALLS = 12

# Deliberately narrow competition whitelist. Names are matched together with country
# to avoid lower/regional leagues. European/international cups are matched by name.
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
CUPS = {
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Conference League",
    "UEFA Nations League",
    "World Cup",
}


def api_get(endpoint: str, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
        headers = {k.lower(): v for k, v in r.headers.items()}
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
    pair = (league.get("country"), league.get("name"))
    return pair in DOMESTIC or league.get("name") in CUPS


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


def coverage_for_fixture(g, cache):
    lid = g.get("league", {}).get("id")
    season = g.get("league", {}).get("season")
    key = (lid, season)
    if not lid or not season:
        return None
    if key not in cache:
        data, _ = api_get("leagues", id=lid, season=season)
        response = data.get("response", [])
        cov = None
        if response:
            for s in response[0].get("seasons", []):
                if s.get("year") == season:
                    cov = s.get("coverage")
                    break
        cache[key] = cov
    return cache[key]


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        raise SystemExit("Usage: api_football_probe.py YYYY-MM-DD")

    fixtures, headers = api_get("fixtures", date=date, timezone="Europe/Warsaw")
    games = fixtures.get("response", [])
    relevant = [g for g in games if wanted(g)]
    completed = [g for g in relevant if g.get("fixture", {}).get("status", {}).get("short") in {"FT", "AET", "PEN"}]

    # Coverage is checked before statistics calls. This saves quota and makes missing
    # statistics explicit rather than treating them as model evidence.
    cov_cache = {}
    eligible = []
    coverage_meta = []
    for g in completed:
        cov = coverage_for_fixture(g, cov_cache)
        stat_ok = bool(((cov or {}).get("fixtures") or {}).get("statistics_fixtures"))
        coverage_meta.append({
            "league_id": g.get("league", {}).get("id"),
            "league": g.get("league", {}).get("name"),
            "season": g.get("league", {}).get("season"),
            "statistics_fixtures": stat_ok,
        })
        if stat_ok:
            eligible.append(g)

    samples = []
    quality_counts = {"full_core": 0, "partial": 0, "none": 0}
    for g in eligible[:MAX_STAT_CALLS]:
        fid = g["fixture"]["id"]
        data, headers = api_get("fixtures/statistics", fixture=fid)
        teams = [team_stats(b) for b in data.get("response", [])]
        core_vals = [t.get(k) for t in teams for k in ("corners", "fouls", "yellow_cards")]
        if len(teams) == 2 and all(v is not None for v in core_vals):
            quality = "FULL_CORE"
            quality_counts["full_core"] += 1
        elif teams:
            quality = "PARTIAL"
            quality_counts["partial"] += 1
        else:
            quality = "NONE"
            quality_counts["none"] += 1
        samples.append({
            "fixture_id": fid,
            "league_id": g.get("league", {}).get("id"),
            "league": g.get("league", {}).get("name"),
            "country": g.get("league", {}).get("country"),
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "quality": quality,
            "teams": teams,
        })

    league_summary = {}
    for g in relevant:
        key = f"{g.get('league', {}).get('country')} | {g.get('league', {}).get('name')}"
        league_summary[key] = league_summary.get(key, 0) + 1

    out = {
        "date": date,
        "all_fixtures": len(games),
        "whitelist_fixtures": len(relevant),
        "whitelist_completed": len(completed),
        "statistics_eligible_completed": len(eligible),
        "stat_calls_made": len(samples),
        "coverage_sample": quality_counts,
        "whitelist_leagues_today": dict(sorted(league_summary.items())),
        "league_season_coverage": coverage_meta,
        "samples": samples,
        "rate_limit_remaining": headers.get("x-ratelimit-requests-remaining"),
        "isolation": "DATA_LAB_ONLY_NO_KB_OR_DEV_N_WRITES",
        "next_use": "DIAGNOSTIC_ONLY_NOT_MODEL_INPUT",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
