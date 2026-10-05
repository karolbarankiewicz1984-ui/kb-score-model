#!/usr/bin/env python3
"""Build the user-facing STS publication list for API Market Scan.

Background candidates remain untouched for audit/calibration. The report publishes
only STS-oriented market families/lines, at most two positions per fixture, and
never promotes WATCH/under-threshold entries. This is a publication profile, not a
change to API PURE or KB Score CORE.
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

# STS-oriented user profile. These are intentionally common/practical pre-match
# football market families rather than every metric analysed by the API model.
# Exact STS availability can still vary by match; the model has no direct STS odds feed.
STS_LINES = {
    "team_goals": {0.5, 1.5, 2.5},
    "corners": {3.5, 4.5, 5.5, 6.5},
    "yellow": {1.5, 2.5, 3.5},
}
STS_PRIORITY = {"team_goals": 3, "corners": 2, "yellow": 1}


def sts_compatible(item):
    market = item.get("market")
    try:
        line = float(item.get("line"))
    except (TypeError, ValueError):
        return False
    return market in STS_LINES and line in STS_LINES[market]


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    candidates = payload.get("background_candidates") or payload.get("top_positions") or []

    eligible = []
    for item in candidates:
        if item.get("final_status") not in {"STRONG", "ACCEPT"}:
            continue
        if float(item.get("final_assessment_pct") or 0) < MIN_FINAL:
            continue
        if not sts_compatible(item):
            continue
        eligible.append(item)

    eligible.sort(
        key=lambda x: (
            STS_PRIORITY.get(x.get("market"), 0),
            float(x.get("final_assessment_pct") or 0),
            float(x.get("reliability_adjusted_pct") or 0),
            float(x.get("confidence_api") or 0),
        ),
        reverse=True,
    )

    selected = []
    counts = {}
    for item in eligible:
        fid = item.get("fixture_id")
        if counts.get(fid, 0) >= MAX_PER_FIXTURE:
            continue
        copy = dict(item)
        copy["bookmaker_profile"] = "STS"
        copy["sts_profile"] = "typical_market_family_not_live_verified"
        selected.append(copy)
        counts[fid] = counts.get(fid, 0) + 1
        if len(selected) >= MAX_PUBLISH:
            break

    payload["top_positions"] = selected
    v3 = payload.setdefault("v3", {})
    v3["publication_policy"] = {
        "bookmaker_profile": "STS",
        "profile_type": "market-and-line compatibility; no direct STS odds feed",
        "preferred_markets": ["team_goals", "corners", "yellow"],
        "excluded_from_main_pdf_but_kept_in_background": [
            "fouls", "shots", "shots_on_goal", "offsides", "goalkeeper_saves"
        ],
        "yellow_min_line": 1.5,
        "corners_min_line": 3.5,
        "max_positions": MAX_PUBLISH,
        "max_per_fixture": MAX_PER_FIXTURE,
        "min_final_assessment_pct": MIN_FINAL,
        "no_watch_backfill": True,
    }
    PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "date": TARGET,
        "background": len(candidates),
        "sts_eligible": len(eligible),
        "published": len(selected),
        "distinct_fixtures": len(counts),
        "bookmaker_profile": "STS",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
