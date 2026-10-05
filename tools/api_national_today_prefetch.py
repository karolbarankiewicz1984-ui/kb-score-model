#!/usr/bin/env python3
"""Populate last-20 national-team history before the final API Market Scan sieve.

This prevents a coverage lock-in where a national team with sparse recent stored
history cannot pass the raw sieve and therefore never gets its extended history.
No writes to KB Score CORE, KB N or DEV N.
"""
from __future__ import annotations

import json
import sys
from datetime import date

import api_market_scan as v2
import api_market_v3_enrich as v3

TARGET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else date.today().isoformat()


def main():
    payload, _ = v2.api_get_all_pages("fixtures", date=TARGET, timezone="Europe/Warsaw")
    fixtures = [] if payload.get("errors") else payload.get("response", [])
    national = [
        g for g in fixtures
        if v2.competition_category(g.get("league", {})) == "national_team"
        and g.get("fixture", {}).get("status", {}).get("short") in {"NS", "TBD"}
    ]
    summary = v3.refresh_national_history(national, v2.load_rows())
    print(json.dumps({
        "date": TARGET,
        "national_fixtures": len(national),
        "teams": summary.get("teams", 0),
        "new_statistics_calls": summary.get("new_statistics_calls", 0),
        "errors": summary.get("errors", []),
        "isolation": "API_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
