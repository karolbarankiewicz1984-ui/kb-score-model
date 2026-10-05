#!/usr/bin/env python3
"""Sync API-Football pre-match odds reference catalogues.

Stores bet and bookmaker reference data only. This file is part of the isolated
API Coverage / Market Overlay layer and never changes KB Score 2.1 CORE.
"""
import json, os, urllib.request
from pathlib import Path

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
OUT = Path("data/api_football/reference")


def get(endpoint):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    req = urllib.request.Request(f"{BASE}/{endpoint}", headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bets = get("odds/bets")
    bookmakers = get("odds/bookmakers")
    (OUT / "odds_bets.json").write_text(json.dumps(bets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "odds_bookmakers.json").write_text(json.dumps(bookmakers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "bets": len(bets.get("response", [])),
        "bookmakers": len(bookmakers.get("response", [])),
        "isolation": "MARKET_OVERLAY_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
