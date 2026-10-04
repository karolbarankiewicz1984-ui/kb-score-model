#!/usr/bin/env python3
"""Daily API-Football collector for the KB Score data lab.

Stores factual finished-match statistics only. It NEVER writes KB/DEV registers,
never changes model parameters and never increments KB N or DEV N.
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
OUT = Path("data/api_football/daily")
DOMESTIC = {("England","Premier League"),("Spain","La Liga"),("Italy","Serie A"),("Germany","Bundesliga"),("France","Ligue 1"),("Portugal","Primeira Liga"),("Netherlands","Eredivisie"),("Belgium","Jupiler Pro League"),("Turkey","Süper Lig"),("Poland","Ekstraklasa")}
CUPS = {"UEFA Champions League","UEFA Europa League","UEFA Conference League","UEFA Nations League","World Cup"}


def get(endpoint, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), {k.lower(): v for k, v in r.headers.items()}


def wanted(g):
    l = g.get("league", {})
    return (l.get("country"), l.get("name")) in DOMESTIC or l.get("name") in CUPS


def sv(stats, name):
    for x in stats or []:
        if x.get("type") == name:
            return x.get("value")
    return None


def main():
    # Scheduled runs collect yesterday (Europe/Warsaw convention supplied to API).
    target = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
    data, hdr = get("fixtures", date=target, timezone="Europe/Warsaw")
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))

    games = [g for g in data.get("response", []) if wanted(g) and g.get("fixture",{}).get("status",{}).get("short") in {"FT","AET","PEN"}]
    rows = []
    detail_errors = []
    for g in games:
        fid = g["fixture"]["id"]
        detail, hdr = get("fixtures/statistics", fixture=fid)
        if detail.get("errors"):
            detail_errors.append({"fixture_id": fid, "errors": detail["errors"]})
            blocks = []
        else:
            blocks = detail.get("response", [])
        teams = []
        for b in blocks:
            s = b.get("statistics", [])
            teams.append({
                "team": b.get("team",{}).get("name"),
                "corners": sv(s,"Corner Kicks"), "fouls": sv(s,"Fouls"),
                "yellow": sv(s,"Yellow Cards"), "red": sv(s,"Red Cards"),
                "shots": sv(s,"Total Shots"), "shots_on_goal": sv(s,"Shots on Goal"),
                "shots_inside_box": sv(s,"Shots insidebox"), "shots_outside_box": sv(s,"Shots outsidebox"),
                "blocked_shots": sv(s,"Blocked Shots"), "possession": sv(s,"Ball Possession"),
                "passes": sv(s,"Total passes"), "passes_accurate": sv(s,"Passes accurate"),
                "offsides": sv(s,"Offsides"), "goalkeeper_saves": sv(s,"Goalkeeper Saves")
            })
        rows.append({
            "fixture_id": fid, "date": g["fixture"].get("date"),
            "league": g["league"].get("name"), "country": g["league"].get("country"),
            "season": g["league"].get("season"),
            "home": g["teams"]["home"].get("name"), "away": g["teams"]["away"].get("name"),
            "goals": g.get("goals",{}), "score": g.get("score",{}), "teams": teams
        })

    # Deterministic output makes repeat runs idempotent: same date replaces the same snapshot.
    rows.sort(key=lambda x: x["fixture_id"])
    payload = {
        "schema": "api-football-daily-v1", "date": target,
        "finished_whitelist_fixtures": len(games), "stored": len(rows),
        "detail_errors": detail_errors, "rows": rows,
        "rate_limit_remaining": hdr.get("x-ratelimit-requests-remaining"),
        "isolation": "DATA_ONLY_NO_KB_OR_DEV_WRITES",
        "model_effect": "NONE", "kb_n_effect": 0, "dev_n_effect": 0
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{target}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"date":target,"stored":len(rows),"detail_errors":len(detail_errors),"output":str(path),"kb_n_effect":0,"dev_n_effect":0}, ensure_ascii=False))

if __name__ == "__main__":
    main()
