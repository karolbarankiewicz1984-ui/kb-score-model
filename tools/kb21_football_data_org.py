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
def fetch(date, token, opener=urllib.request.urlopen):
    dt.date.fromisoformat(date)
    query=urllib.parse.urlencode({"dateFrom":date,"dateTo":date})
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
            "status":"INDEPENDENT_SNAPSHOT_UNMATCHED","kb_n_effect":0,
            "dev_n_effect":0,"register_writes":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--out",default="data/football_data_org")
    a=p.parse_args()
    token=os.environ.get("FOOTBALL_DATA_ORG_KEY")
    if not token: raise SystemExit("FOOTBALL_DATA_ORG_KEY missing")
    result=fetch(a.date,token)
    path=Path(a.out)/(a.date+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":a.date,"fixtures":len(result["fixtures"]),"output":str(path),
                      "verified":0,"kb_n_effect":0}))
if __name__=="__main__":main()
