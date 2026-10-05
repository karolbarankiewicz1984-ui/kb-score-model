#!/usr/bin/env python3
"""Diversify only the user-facing API Market Scan publication list.

Background candidates remain untouched for audit/calibration. The report publishes
at most two positions per fixture and never promotes WATCH/under-threshold entries.
No writes to KB Score CORE, KB N or DEV N.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

TARGET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else date.today().isoformat()
PATH = Path("data/api_football/market_scan") / f"{TARGET}.json"
MAX_PUBLISH = 10
MAX_PER_FIXTURE = 2
MIN_FINAL = 75.0


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    candidates = payload.get("background_candidates") or payload.get("top_positions") or []
    selected = []
    counts = {}
    for item in candidates:
        if item.get("final_status") not in {"STRONG", "ACCEPT"}:
            continue
        if float(item.get("final_assessment_pct") or 0) < MIN_FINAL:
            continue
        fid = item.get("fixture_id")
        if counts.get(fid, 0) >= MAX_PER_FIXTURE:
            continue
        selected.append(item)
        counts[fid] = counts.get(fid, 0) + 1
        if len(selected) >= MAX_PUBLISH:
            break

    payload["top_positions"] = selected
    v3 = payload.setdefault("v3", {})
    v3["publication_policy"] = {
        "max_positions": MAX_PUBLISH,
        "max_per_fixture": MAX_PER_FIXTURE,
        "min_final_assessment_pct": MIN_FINAL,
        "no_watch_backfill": True,
    }
    PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "date": TARGET,
        "background": len(candidates),
        "published": len(selected),
        "distinct_fixtures": len(counts),
        "max_per_fixture": MAX_PER_FIXTURE,
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
