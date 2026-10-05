#!/usr/bin/env python3
"""Settle frozen v3 positions and rebuild calibration summary."""
from __future__ import annotations
import json, math, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import api_market_scan as v2

WARSAW=ZoneInfo("Europe/Warsaw")
TARGET=sys.argv[1] if len(sys.argv)>1 and sys.argv[1].strip() else (datetime.now(WARSAW).date()-timedelta(days=1)).isoformat()
SRC=Path("data/api_football/market_scan")/f"{TARGET}.json"
OUTDIR=Path("data/api_football/calibration")
CLOSE=Path("data/api_football/closing_snapshots")/TARGET

def sv(stats,name):
    for x in stats or []:
        if x.get("type")==name:return x.get("value")
    return None

def actual_metric(fixture,blocks,item):
    side=item.get("team_side")
    if item["market"]=="team_goals": return fixture.get("goals",{}).get(side)
    team_id=item.get("team_id")
    for b in blocks or []:
        if b.get("team",{}).get("id")!=team_id: continue
        s=b.get("statistics") or []
        names={"yellow":"Yellow Cards","corners":"Corner Kicks","fouls":"Fouls","shots":"Total Shots","shots_on_goal":"Shots on Goal","offsides":"Offsides","goalkeeper_saves":"Goalkeeper Saves"}
        return sv(s,names[item["market"]])
    return None

def closing_for(item):
    if not CLOSE.exists(): return None
    key=v2.market_key(item); best=None
    try: kickoff=datetime.fromisoformat(item["kickoff"].replace("Z","+00:00"))
    except Exception: kickoff=None
    for p in sorted(CLOSE.glob("*.json")):
        try: data=json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        try: cap=datetime.fromisoformat(data.get("captured_at_utc").replace("Z","+00:00"))
        except Exception: cap=None
        if kickoff and cap and cap>kickoff: continue
        for x in data.get("items") or []:
            if x.get("key")==key and x.get("market_probability_pct") is not None:
                best={"captured_at_utc":data.get("captured_at_utc"),"market_probability_pct":x.get("market_probability_pct"),"paired_books":x.get("paired_books"),"bookmaker_spread_pp":x.get("bookmaker_spread_pp")}
    return best

def brier(p,y):
    if p is None:return None
    return (float(p)/100.0-float(y))**2

def logloss(p,y):
    if p is None:return None
    q=min(0.999,max(0.001,float(p)/100.0))
    return -(y*math.log(q)+(1-y)*math.log(1-q))

def band(p):
    if p is None:return "NA"
    lo=int(float(p)//5)*5
    return f"{lo}-{lo+4}"

def rebuild_summary():
    obs=[]
    for p in OUTDIR.glob("20??-??-??.json"):
        try: obs.extend(json.loads(p.read_text(encoding="utf-8")).get("observations") or [])
        except Exception: pass
    groups={}
    def add(key,o):
        g=groups.setdefault(key,{"n":0,"hits":0,"brier_api":[],"brier_final":[],"logloss_api":[],"logloss_final":[]})
        g["n"]+=1; g["hits"]+=int(o["hit"])
        for name,val in (("brier_api",o.get("brier_api")),("brier_final",o.get("brier_final")),("logloss_api",o.get("logloss_api")),("logloss_final",o.get("logloss_final"))):
            if val is not None:g[name].append(val)
    for o in obs:
        add(f"market:{o['market']}",o); add(f"status:{o['final_status']}",o); add(f"api_band:{band(o.get('api_pure_pct'))}",o); add(f"final_band:{band(o.get('final_assessment_pct'))}",o)
        d=float(o.get("market_delta_pp") or 0); add("market_direction:"+("UP" if d>0.4 else "DOWN" if d<-0.4 else "FLAT"),o)
    summary={}
    for k,g in groups.items():
        summary[k]={"n":g["n"],"hits":g["hits"],"hit_rate_pct":round(100*g["hits"]/g["n"],1) if g["n"] else None,"brier_api":round(sum(g["brier_api"])/len(g["brier_api"]),4) if g["brier_api"] else None,"brier_final":round(sum(g["brier_final"])/len(g["brier_final"]),4) if g["brier_final"] else None,"logloss_api":round(sum(g["logloss_api"])/len(g["logloss_api"]),4) if g["logloss_api"] else None,"logloss_final":round(sum(g["logloss_final"])/len(g["logloss_final"]),4) if g["logloss_final"] else None}
    payload={"schema":"api-market-calibration-summary-v1","observations":len(obs),"groups":summary,"policy":{"n_lt_50":"observe_only","n_50_99":"signals_only","n_100_plus":"eligible_for_cautious_calibration","n_250_plus":"stronger_basis","automatic_weight_changes":False},"isolation":"API_ONLY_NO_KB_SCORE_CORE_WRITES","kb_n_effect":0,"dev_n_effect":0}
    (OUTDIR/"_summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return len(obs)

def main():
    if not SRC.exists(): print(json.dumps({"date":TARGET,"status":"no-freeze"})); return
    freeze=json.loads(SRC.read_text(encoding="utf-8")); positions=freeze.get("top_positions") or []
    obs=[]; errors=[]; cache={}
    for item in positions:
        fid=item["fixture_id"]
        if fid not in cache:
            try:
                fp,_=v2.api_get("fixtures",id=fid); fixtures=fp.get("response",[]) if not fp.get("errors") else []
                sp,_=v2.api_get("fixtures/statistics",fixture=fid); blocks=sp.get("response",[]) if not sp.get("errors") else []
                cache[fid]=(fixtures[0] if fixtures else {},blocks)
            except Exception as exc: errors.append({"fixture_id":fid,"error":str(exc)}); cache[fid]=({},[])
        fixture,blocks=cache[fid]
        if fixture.get("fixture",{}).get("status",{}).get("short") not in {"FT","AET","PEN"}: continue
        actual=actual_metric(fixture,blocks,item)
        if not isinstance(actual,(int,float)): errors.append({"fixture_id":fid,"selection":item.get("selection"),"error":"missing_actual_metric"}); continue
        hit=1 if float(actual)>float(item["line"]) else 0
        close=closing_for(item)
        o={"date":TARGET,"fixture_id":fid,"selection":item.get("selection"),"competition":item.get("competition"),"category":item.get("category"),"market":item["market"],"line":item["line"],"actual":actual,"hit":hit,"api_pure_pct":item.get("api_pure_pct"),"reliability_adjusted_pct":item.get("reliability_adjusted_pct"),"market_adjusted_pct":item.get("market_adjusted_pct"),"market_delta_pp":item.get("market_delta_pp"),"final_assessment_pct":item.get("final_assessment_pct"),"final_status":item.get("final_status"),"closing":close}
        o["brier_api"]=brier(o["api_pure_pct"],hit); o["brier_final"]=brier(o["final_assessment_pct"],hit); o["logloss_api"]=logloss(o["api_pure_pct"],hit); o["logloss_final"]=logloss(o["final_assessment_pct"],hit)
        obs.append(o)
    OUTDIR.mkdir(parents=True,exist_ok=True)
    path=OUTDIR/f"{TARGET}.json"; path.write_text(json.dumps({"schema":"api-market-settlement-v1","date":TARGET,"observations":obs,"errors":errors,"isolation":"API_ONLY_NO_KB_SCORE_CORE_WRITES","kb_n_effect":0,"dev_n_effect":0},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    total=rebuild_summary()
    print(json.dumps({"date":TARGET,"settled":len(obs),"errors":len(errors),"calibration_total":total,"output":str(path)}))
if __name__=="__main__": main()
