#!/usr/bin/env python3
"""API-Football -> KB21 guarded candidate input, without modifying KB registers.

Uses only prior FINISHED matches to estimate pre-match goal rates.
Structural/quality/matchup scores are NOT derivable from this feed; deliberately
emits incomplete inputs, which the KB engine must reject until verified.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from tools.api_market_http import ApiClient

BASE="https://v3.football.api-sports.io"

def parse_utc(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))

def historic_goal_rates(matches, team_id, cutoff):
    selected=[]
    for match in matches:
        f=match.get("fixture",{})
        t=match.get("teams",{})
        if f.get("status",{}).get("short") not in {"FT","AET","PEN"}: continue
        if parse_utc(f["date"]) >= cutoff: continue
        home=t.get("home",{}).get("id")==team_id
        away=t.get("away",{}).get("id")==team_id
        if not (home or away): continue
        g=match.get("goals",{})
        gf=g.get("home" if home else "away")
        ga=g.get("away" if home else "home")
        if not isinstance(gf,int) or not isinstance(ga,int): continue
        selected.append((parse_utc(f["date"]),gf,ga,f.get("id")))
    selected.sort(reverse=True)
    sample=selected[:10]
    if len(sample)<5: return None
    return {"sample_size":len(sample),"goals_for_per_match":round(sum(x[1] for x in sample)/len(sample),4),
            "goals_against_per_match":round(sum(x[2] for x in sample)/len(sample),4),
            "fixture_ids":[x[3] for x in sample]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--out",default="data/api_football/kb21_inputs")
    args=ap.parse_args()
    key=os.getenv("API_FOOTBALL_KEY")
    if not key: raise SystemExit("API_FOOTBALL_KEY missing; no network requests made")
    client=ApiClient()
    now=dt.datetime.now(dt.timezone.utc)
    payload,_=client.get(BASE,key,"fixtures",date=args.date,timezone="Europe/Warsaw")
    if payload.get("errors"): raise RuntimeError(str(payload["errors"]))
    fixtures=[f for f in payload.get("response",[]) if parse_utc(f["fixture"]["date"])>now and f["fixture"]["status"]["short"]=="NS"]
    candidates=[]
    for fixture in fixtures:
        start=parse_utc(fixture["fixture"]["date"])
        teams=fixture["teams"]
        rates={}
        for side in ("home","away"):
            team_id=teams[side]["id"]
            past,_=client.get(BASE,key,"fixtures",team=team_id,last=12)
            if past.get("errors"): raise RuntimeError(str(past["errors"]))
            rates[side]=historic_goal_rates(past.get("response",[]),team_id,start)
        candidates.append({
            "event":teams["home"]["name"]+" – "+teams["away"]["name"],
            "fixture_id":fixture["fixture"]["id"],
            "league":fixture["league"]["name"],
            "kickoff_utc":fixture["fixture"]["date"],
            "snapshot_utc":now.isoformat(),
            "api_goal_rates":rates,
            "fixture_verified_official":False,
            "fixture_verified_independent":False,
            "structural_0_100":None,"quality_0_100":None,"matchup_0_100":None,
            "home_expected_goals":None,"away_expected_goals":None,
            "selection":"home",
            "sources":["API-Football fixtures","API-Football historical fixtures"],
            "readiness":"NOT_READY: independently verify calendar, normalized 35/35/30 and expected goals",
            "freeze_allowed":False
        })
    path=Path(args.out)/f"{args.date}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"date":args.date,"snapshot_utc":now.isoformat(),
        "source":"API-Football","pre_match_fixtures":len(fixtures),
        "candidates":candidates,"kb_n_effect":0,"dev_n_effect":0,
        "model_effect":"NONE","register_writes":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(path),"pre_match_fixtures":len(fixtures),
                      "complete_model_inputs":0,"kb_n_effect":0,"dev_n_effect":0}))

if __name__=="__main__":main()
