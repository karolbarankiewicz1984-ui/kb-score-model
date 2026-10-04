#!/usr/bin/env python3
"""Read-only API-Football probe for KB Score Data Lab.

This tool is deliberately isolated from KB Score 2.1 and Markets DEV state:
- does not write Rejestr/Rynki_DEV/Parametry/Kalibracja
- does not change N or DEV N
- does not calculate or modify model parameters
"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")


def api_get(endpoint: str, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def stat_value(stats, name):
    for item in stats or []:
        if item.get("type") == name:
            return item.get("value")
    return None


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        raise SystemExit("Usage: api_football_probe.py YYYY-MM-DD")

    fixtures = api_get("fixtures", date=date, timezone="Europe/Warsaw")
    if fixtures.get("errors"):
        raise RuntimeError(fixtures["errors"])

    games = fixtures.get("response", [])
    out = {
        "date": date,
        "fixture_count": len(games),
        "quota": fixtures.get("results"),
        "sample": [],
        "isolation": "DATA_LAB_ONLY_NO_KB_OR_DEV_N_WRITES",
    }

    # Keep the smoke test cheap: statistics for at most the first completed fixture.
    completed = [g for g in games if g.get("fixture", {}).get("status", {}).get("short") in {"FT", "AET", "PEN"}]
    for g in completed[:1]:
        fid = g["fixture"]["id"]
        stats = api_get("fixtures/statistics", fixture=fid).get("response", [])
        teams = []
        for block in stats:
            s = block.get("statistics", [])
            teams.append({
                "team": block.get("team", {}).get("name"),
                "shots": stat_value(s, "Total Shots"),
                "shots_on_goal": stat_value(s, "Shots on Goal"),
                "corners": stat_value(s, "Corner Kicks"),
                "fouls": stat_value(s, "Fouls"),
                "yellow_cards": stat_value(s, "Yellow Cards"),
                "red_cards": stat_value(s, "Red Cards"),
                "possession": stat_value(s, "Ball Possession"),
            })
        out["sample"].append({
            "fixture_id": fid,
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "teams": teams,
        })

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
