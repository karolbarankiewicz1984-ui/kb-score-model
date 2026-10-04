#!/usr/bin/env python3
"""Historical API-Football Data Lab sampler (READ ONLY).

Purpose: measure historical data availability/quality for GOALS/BTTS/TEAM TOTALS,
CORNERS, CARDS and FOULS before any use in Markets DEV.

HARD ISOLATION: this program has no Google Sheets/model write path and must never
change KB N, DEV N, model parameters, calibration, thresholds or decisions.
"""
import json, os, sys, urllib.parse, urllib.request
from collections import defaultdict

BASE="https://v3.football.api-sports.io"
KEY=os.environ.get("API_FOOTBALL_KEY")
MAX_DETAIL_CALLS=24
DOMESTIC={("England","Premier League"),("Spain","La Liga"),("Italy","Serie A"),("Germany","Bundesliga"),("France","Ligue 1"),("Portugal","Primeira Liga"),("Netherlands","Eredivisie"),("Belgium","Jupiler Pro League"),("Turkey","Süper Lig"),("Poland","Ekstraklasa")}
CUPS={"UEFA Champions League","UEFA Europa League","UEFA Conference League","UEFA Nations League","World Cup"}


def get(endpoint, **params):
    if not KEY: raise RuntimeError("Missing API_FOOTBALL_KEY")
    req=urllib.request.Request(f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}",headers={"x-apisports-key":KEY})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=json.load(r); hdr={k.lower():v for k,v in r.headers.items()}
    if data.get("errors"): raise RuntimeError(data["errors"])
    return data,hdr


def wanted(g):
    l=g.get("league",{}); return (l.get("country"),l.get("name")) in DOMESTIC or l.get("name") in CUPS


def sv(stats,name):
    for x in stats or []:
        if x.get("type")==name:return x.get("value")
    return None


def main():
    # Default window deliberately small to protect quota; pass FROM TO explicitly when desired.
    start=sys.argv[1] if len(sys.argv)>1 else "2026-09-27"
    end=sys.argv[2] if len(sys.argv)>2 else "2026-10-03"
    fixtures,hdr=get("fixtures",**{"from":start,"to":end,"timezone":"Europe/Warsaw"})
    games=[g for g in fixtures.get("response",[]) if wanted(g) and g.get("fixture",{}).get("status",{}).get("short") in {"FT","AET","PEN"}]

    # Balanced round-robin by competition so one busy league cannot consume the sample.
    buckets=defaultdict(list)
    for g in games:buckets[(g["league"].get("country"),g["league"].get("name"))].append(g)
    selected=[]
    while len(selected)<MAX_DETAIL_CALLS and any(buckets.values()):
        for k in sorted(buckets):
            if buckets[k] and len(selected)<MAX_DETAIL_CALLS:selected.append(buckets[k].pop(0))

    rows=[]; family={k:{"usable":0,"missing":0} for k in ["goals_btts_team_totals","corners","cards","fouls"]}
    for g in selected:
        fid=g["fixture"]["id"]; d,hdr=get("fixtures/statistics",fixture=fid); blocks=d.get("response",[])
        teams=[]
        for b in blocks:
            s=b.get("statistics",[]); teams.append({"team":b.get("team",{}).get("name"),"corners":sv(s,"Corner Kicks"),"fouls":sv(s,"Fouls"),"yellow":sv(s,"Yellow Cards"),"red":sv(s,"Red Cards"),"shots":sv(s,"Total Shots"),"sot":sv(s,"Shots on Goal")})
        goals=g.get("goals",{}); goals_ok=goals.get("home") is not None and goals.get("away") is not None
        corners_ok=len(teams)==2 and all(t["corners"] is not None for t in teams)
        cards_ok=len(teams)==2 and all(t["yellow"] is not None for t in teams)
        fouls_ok=len(teams)==2 and all(t["fouls"] is not None for t in teams)
        oks={"goals_btts_team_totals":goals_ok,"corners":corners_ok,"cards":cards_ok,"fouls":fouls_ok}
        for k,v in oks.items():family[k]["usable" if v else "missing"]+=1
        rows.append({"fixture_id":fid,"date":g["fixture"].get("date"),"league":g["league"].get("name"),"country":g["league"].get("country"),"home":g["teams"]["home"].get("name"),"away":g["teams"]["away"].get("name"),"goals":goals,"family_usable":oks,"teams":teams})

    n=len(rows)
    for k,v in family.items():v["coverage_pct"]=round(100*v["usable"]/n,1) if n else None
    print(json.dumps({"window":{"from":start,"to":end},"finished_whitelist_fixtures":len(games),"sampled":n,"family_quality":family,"rows":rows,"rate_limit_remaining":hdr.get("x-ratelimit-requests-remaining"),"isolation":"DATA_LAB_ONLY_NO_KB_OR_DEV_N_WRITES","model_effect":"NONE","dev_n_effect":0,"kb_n_effect":0},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
