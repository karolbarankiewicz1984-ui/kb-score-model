#!/usr/bin/env python3
"""Historical API-Football Data Lab sampler (READ ONLY)."""
import json, os, sys, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date, timedelta

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

def days(start,end):
    d=date.fromisoformat(start); stop=date.fromisoformat(end)
    if stop<d: raise ValueError("TO must be >= FROM")
    if (stop-d).days>14: raise ValueError("Diagnostic window max 15 days")
    while d<=stop:
        yield d.isoformat(); d+=timedelta(days=1)

def main():
    start=sys.argv[1] if len(sys.argv)>1 else "2026-09-27"
    end=sys.argv[2] if len(sys.argv)>2 else "2026-10-03"
    games=[]; hdr={}; fixture_calls=0
    for day in days(start,end):
        data,hdr=get("fixtures",date=day,timezone="Europe/Warsaw"); fixture_calls+=1
        games.extend(g for g in data.get("response",[]) if wanted(g) and g.get("fixture",{}).get("status",{}).get("short") in {"FT","AET","PEN"})
    games=list({g["fixture"]["id"]:g for g in games if g.get("fixture",{}).get("id") is not None}.values())
    buckets=defaultdict(list)
    for g in games:buckets[(g["league"].get("country"),g["league"].get("name"))].append(g)
    selected=[]
    while len(selected)<MAX_DETAIL_CALLS and any(buckets.values()):
        for k in sorted(buckets):
            if buckets[k] and len(selected)<MAX_DETAIL_CALLS:selected.append(buckets[k].pop(0))
    rows=[]; family={k:{"usable":0,"missing":0} for k in ["goals_btts_team_totals","corners","cards","fouls"]}
    for g in selected:
        fid=g["fixture"]["id"]; data,hdr=get("fixtures/statistics",fixture=fid); blocks=data.get("response",[])
        teams=[]
        for b in blocks:
            s=b.get("statistics",[]); teams.append({"team":b.get("team",{}).get("name"),"corners":sv(s,"Corner Kicks"),"fouls":sv(s,"Fouls"),"yellow":sv(s,"Yellow Cards"),"red":sv(s,"Red Cards"),"shots":sv(s,"Total Shots"),"sot":sv(s,"Shots on Goal")})
        goals=g.get("goals",{}); goals_ok=goals.get("home") is not None and goals.get("away") is not None
        oks={"goals_btts_team_totals":goals_ok,"corners":len(teams)==2 and all(t["corners"] is not None for t in teams),"cards":len(teams)==2 and all(t["yellow"] is not None for t in teams),"fouls":len(teams)==2 and all(t["fouls"] is not None for t in teams)}
        for k,v in oks.items():family[k]["usable" if v else "missing"]+=1
        rows.append({"fixture_id":fid,"date":g["fixture"].get("date"),"league":g["league"].get("name"),"country":g["league"].get("country"),"home":g["teams"]["home"].get("name"),"away":g["teams"]["away"].get("name"),"goals":goals,"family_usable":oks,"teams":teams})
    n=len(rows)
    for k,v in family.items():v["coverage_pct"]=round(100*v["usable"]/n,1) if n else None
    print(json.dumps({"window":{"from":start,"to":end},"fixture_calls":fixture_calls,"finished_whitelist_fixtures":len(games),"sampled":n,"family_quality":family,"rows":rows,"rate_limit_remaining":hdr.get("x-ratelimit-requests-remaining"),"isolation":"DATA_LAB_ONLY_NO_KB_OR_DEV_N_WRITES","model_effect":"NONE","dev_n_effect":0,"kb_n_effect":0},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
