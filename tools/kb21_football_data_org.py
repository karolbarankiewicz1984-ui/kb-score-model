"""Read-only football-data.org v4 schedule snapshot; no model writes."""
import argparse
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE="https://api.football-data.org/v4/matches"
TARGET_CODES=("PL","PD","BL1","SA","FL1","DED","PPL","CL","ELC","EC","WC")
def fetch(date, token, opener=urllib.request.urlopen, competition_codes=None):
    dt.date.fromisoformat(date)
    filters={"dateFrom":date,"dateTo":date}
    if competition_codes:
        filters["competitions"]=",".join(competition_codes)
    query=urllib.parse.urlencode(filters)
    req=urllib.request.Request(BASE+"?"+query,headers={"X-Auth-Token":token,"Accept":"application/json"})
    try:
        with opener(req,timeout=25) as response:
            data=json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("football-data.org request failed: HTTP "+str(exc.code)) from exc
    if not isinstance(data.get("matches"),list):
        raise ValueError("football-data.org response lacks matches list")
    rows=[]
    for m in data["matches"]:
        home=m.get("homeTeam") or {}
        away=m.get("awayTeam") or {}
        comp=m.get("competition") or {}
        if not home.get("id") or not away.get("id") or not m.get("utcDate"):
            continue
        rows.append({"provider_match_id":m.get("id"),"home_team_id":home["id"],
                     "away_team_id":away["id"],"home_team":home.get("name"),
                     "away_team":away.get("name"),"kickoff_utc":m["utcDate"],
                     "competition_code":comp.get("code"),"competition":comp.get("name"),
                     "status":m.get("status"),"source_url":None})
    return {"date":date,"provider":"football-data.org","provider_endpoint":BASE,
            "provider_ids_are_not_api_football_ids":True,"fixtures":rows,
            "requested_competitions":list(competition_codes or []),
            "status":"INDEPENDENT_SNAPSHOT_UNMATCHED","kb_n_effect":0,
            "dev_n_effect":0,"register_writes":False}

def coverage(token, opener=urllib.request.urlopen):
    req=urllib.request.Request("https://api.football-data.org/v4/competitions",headers={"X-Auth-Token":token,"Accept":"application/json"})
    try:
        with opener(req,timeout=25) as response:
            data=json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("football-data.org competitions request failed: HTTP "+str(exc.code)) from exc
    if not isinstance(data.get("competitions"),list):
        raise ValueError("football-data.org response lacks competitions list")
    competitions=[{"id":c.get("id"),"code":c.get("code"),"name":c.get("name"),"area":(c.get("area") or {}).get("name"),"plan":c.get("plan")} for c in data["competitions"]]
    return {"provider":"football-data.org","status":"SUBSCRIPTION_COVERAGE_DISCOVERY",
            "competitions":competitions,"competition_count":len(competitions),
            "kb_n_effect":0,"dev_n_effect":0,"register_writes":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date")
    p.add_argument("--coverage-only",action="store_true")
    p.add_argument("--target-competitions",action="store_true",help="Filter to available KB21 target competitions")
    p.add_argument("--out",default="data/football_data_org")
    a=p.parse_args()
    token=os.environ.get("FOOTBALL_DATA_ORG_KEY")
    if not token: raise SystemExit("FOOTBALL_DATA_ORG_KEY missing")
    if not a.coverage_only and not a.date: raise SystemExit("--date required unless --coverage-only")
    codes=None
    if a.target_competitions and not a.coverage_only:
        coverage_path=Path(a.out)/"coverage.json"
        if not coverage_path.exists(): raise SystemExit("Coverage snapshot missing; run --coverage-only first")
        known=json.loads(coverage_path.read_text(encoding="utf-8")).get("competitions",[])
        codes=[c["code"] for c in known if c.get("code") in TARGET_CODES and c.get("plan")=="TIER_ONE"]
        if not codes: raise SystemExit("No eligible TIER_ONE target competitions in coverage snapshot")
    result=coverage(token) if a.coverage_only else fetch(a.date,token,competition_codes=codes)
    path=Path(a.out)/("coverage.json" if a.coverage_only else a.date+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":a.date,"fixtures":len(result.get("fixtures",[])),
                      "competitions":result.get("competition_count"),"output":str(path),
                      "verified":0,"kb_n_effect":0}))
if __name__=="__main__":main()
