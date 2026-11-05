#!/usr/bin/env python3
"""Frozen pre-match API Market Scan picks; isolated from KB Score and Markets DEV."""
import json,sys
from pathlib import Path
from datetime import datetime,timezone
from api_market_playable_shadow import evaluate,CONFIG
ROOT=Path(__file__).resolve().parents[1]
day=sys.argv[1]
cfg=json.loads(CONFIG.read_text())
src=ROOT/"data/api_football/market_scan"/f"{day}.json"
payload=json.loads(src.read_text())
accepted,_=evaluate(payload,cfg)
out=ROOT/"reports/api_market_scan/audit_input"/f"{day}.json"
out.parent.mkdir(parents=True,exist_ok=True)
frozen=[]
for x in accepted:
    frozen.append({k:x.get(k) for k in ("fixture_id","home","away","home_id","away_id","team_id","team_side","market","market_scope","line","direction","selection","kickoff","final_assessment_pct","best_quote")})
out.write_text(json.dumps({"schema":"api-market-audit-input-v1","date":day,"frozen_at_utc":datetime.now(timezone.utc).isoformat(),"picks":frozen},ensure_ascii=False,indent=2)+"\n")
print(f"Frozen {len(frozen)} positions to {out}")
