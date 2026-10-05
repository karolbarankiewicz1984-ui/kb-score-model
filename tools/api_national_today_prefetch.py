#!/usr/bin/env python3
"""Populate last-20 national-team history before the final API Market Scan sieve.

This prevents a coverage lock-in where a national team with sparse recent stored
history cannot pass the raw sieve and therefore never gets its extended history.
The consolidated bridge file is written into the existing national-history folder
already read by api_market_scan.py. No writes to KB Score CORE, KB N or DEV N.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import api_market_scan as v2
import api_market_v3_enrich as v3

TARGET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else date.today().isoformat()
BRIDGE = Path("data/api_football/international_5m/national/dynamic_last20.json")


def consolidate_dynamic_rows():
    by_id = {}
    for row in v3.load_dynamic_rows():
        fid = row.get("fixture_id")
        if fid is None:
            continue
        old = by_id.get(fid)
        if old is None or len(row.get("teams") or []) >= len(old.get("teams") or []):
            by_id[fid] = row
    rows = sorted(by_id.values(), key=lambda r: v2.parse_dt(r.get("date")))
    BRIDGE.parent.mkdir(parents=True, exist_ok=True)
    BRIDGE.write_text(json.dumps({
        "schema": "api-national-dynamic-bridge-v1",
        "target": TARGET,
        "rows": rows,
        "isolation": "API_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(rows)


def main():
    payload, _ = v2.api_get_all_pages("fixtures", date=TARGET, timezone="Europe/Warsaw")
    fixtures = [] if payload.get("errors") else payload.get("response", [])
    national = [
        g for g in fixtures
        if v2.competition_category(g.get("league", {})) == "national_team"
        and g.get("fixture", {}).get("status", {}).get("short") in {"NS", "TBD"}
    ]
    summary = v3.refresh_national_history(national, v2.load_rows())
    bridge_rows = consolidate_dynamic_rows()
    print(json.dumps({
        "date": TARGET,
        "national_fixtures": len(national),
        "teams": summary.get("teams", 0),
        "new_statistics_calls": summary.get("new_statistics_calls", 0),
        "bridge_rows": bridge_rows,
        "errors": summary.get("errors", []),
        "isolation": "API_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
