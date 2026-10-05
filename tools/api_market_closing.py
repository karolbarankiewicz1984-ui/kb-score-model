#!/usr/bin/env python3
"""Collect near-kickoff closing-market snapshots for frozen v3 positions."""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import api_market_scan as v2
from api_market_policy import target_date
from api_market_storage import frozen_candidates

WARSAW=ZoneInfo("Europe/Warsaw")
TARGET=target_date(sys.argv[1] if len(sys.argv)>1 else None)
SRC=Path("data/api_football/market_scan")/f"{TARGET}.json"
OUT=Path("data/api_football/closing_snapshots")/TARGET

def main():
    positions=list({v2.market_key(x): x for x in frozen_candidates(TARGET)}.values())
    if not positions:
        print(json.dumps({"date":TARGET,"status":"no-verified-freeze"})); return
    now=datetime.now(timezone.utc)
    active=[]
    for x in positions:
        try: ko=datetime.fromisoformat(x["kickoff"].replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception: continue
        mins=(ko-now).total_seconds()/60
        if 0 <= mins <= 120: active.append(x)
    if not active:
        print(json.dumps({"date":TARGET,"status":"no-near-kickoff","positions":0})); return
    odds_cache={}; items=[]; errors=[]
    for x in active:
        fid=x["fixture_id"]
        if fid not in odds_cache:
            try:
                p,_=v2.api_get_all_pages("odds",fixture=fid)
                odds_cache[fid]=[] if p.get("errors") else p.get("response",[])
            except Exception as exc:
                odds_cache[fid]=[]; errors.append({"fixture_id":fid,"error":str(exc)})
        market=v2.extract_market_quotes(odds_cache[fid],x)
        items.append({"key":v2.market_key(x),"fixture_id":fid,"kickoff":x.get("kickoff"),"team":x.get("team"),"market":x.get("market"),"line":x.get("line"),"market_probability_pct":market.get("market_probability_pct"),"paired_books":market.get("paired_books",0),"bookmaker_spread_pp":market.get("bookmaker_spread_pp"),"quotes":market.get("quotes",[])})
    OUT.mkdir(parents=True,exist_ok=True)
    stamp=now.strftime("%H%M%S")
    path=OUT/f"{stamp}.json"
    path.write_text(json.dumps({"schema":"api-closing-snapshot-v1","date":TARGET,"captured_at_utc":now.isoformat(),"items":items,"errors":errors,"isolation":"API_ONLY_NO_KB_SCORE_CORE_WRITES","kb_n_effect":0,"dev_n_effect":0},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":TARGET,"positions":len(items),"output":str(path),"errors":len(errors)}))
if __name__=="__main__": main()
