#!/usr/bin/env python3
"""Publish the complete API ranking; historical filename kept for workflow compatibility."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from api_market_policy import load_policy, rank_positions, target_date
from api_market_presentation import grouped_markdown
from api_market_storage import archive_publication, atomic_write

TARGET = target_date(sys.argv[1] if len(sys.argv) > 1 else None)
PATH = Path("data/api_football/market_work") / f"{TARGET}.json"


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    policy = load_policy()
    candidates = payload.get("background_candidates") or []
    payload["top_positions"] = rank_positions(candidates, policy["publish_min_final_pct"])
    payload.setdefault("v3", {})["publication_policy"] = policy
    payload = archive_publication(payload, TARGET, policy)
    positions = payload["top_positions"]
    atomic_write(Path("reports/api_market_scan") / f"{TARGET}.md",
                 grouped_markdown(payload, policy['publish_min_final_pct']))
    print(json.dumps({"date": TARGET, "background": len(candidates), "published": len(positions),
        "distinct_fixtures": len({x['fixture_id'] for x in positions}),
        "threshold": policy['publish_min_final_pct'], "prediction_id": payload['publication']['id'],
        "kb_n_effect": 0, "dev_n_effect": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
