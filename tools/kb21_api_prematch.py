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
from zoneinfo import ZoneInfo
from tools.api_market_http import ApiClient

BASE="https://v3.football.api-sports.io"
DOMESTIC={
 ("England","Premier League"),("Spain","La Liga"),("Italy","Serie A"),
 ("Germany","Bundesliga"),("France","Ligue 1"),("Portugal","Primeira Liga"),
 ("Netherlands","Eredivisie"),("Belgium","Jupiler Pro League"),
 ("Turkey","Süper Lig"),("Poland","Ekstraklasa")
}
INTERNATIONAL={
 "UEFA Champions League","UEFA Europa League","UEFA Europa Conference League",
 "UEFA Conference League","UEFA Nations League","World Cup",
 "World Cup - Qualification Europe","Euro Championship","UEFA European Championship"
}
def in_scope(fixture):
    from tools.kb21_league_scope import in_scope as by_id
    return by_id(fixture)

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
    ap.add_argument("--date",default=dt.datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat())
    ap.add_argument("--out",default="data/api_football/kb21_inputs")
    ap.add_argument("--max-history-calls",type=int,default=100)
    args=ap.parse_args()
    key=os.getenv("API_FOOTBALL_KEY")
    if not key: raise SystemExit("API_FOOTBALL_KEY missing; no network requests made")
    client=ApiClient()
    now=dt.datetime.now(dt.timezone.utc)
    try:
        dt.date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit("Invalid date: expected YYYY-MM-DD")
    payload,_=client.get(BASE,key,"fixtures",date=args.date,timezone="Europe/Warsaw")
    if payload.get("errors"): raise RuntimeError(str(payload["errors"]))
    all_fixtures=payload.get("response",[])
    fixtures=[f for f in all_fixtures if in_scope(f) and parse_utc(f["fixture"]["date"])>now and f["fixture"]["status"]["short"]=="NS"]
    fixtures.sort(key=lambda f:(f["fixture"]["date"],f["fixture"]["id"]))
    candidates=[]
    history_cache={}
    if args.max_history_calls<0: raise SystemExit("max-history-calls must be nonnegative")
    required_teams={f["teams"][side]["id"] for f in fixtures for side in ("home","away")}
    if len(required_teams)>args.max_history_calls:
        raise SystemExit(f"Safety stop: {len(required_teams)} team histories exceeds limit {args.max_history_calls}; no incomplete report written")
    for fixture in fixtures:
        start=parse_utc(fixture["fixture"]["date"])
        teams=fixture["teams"]
        rates={}
        for side in ("home","away"):
            team_id=teams[side]["id"]
            if team_id not in history_cache:
                past,_=client.get(BASE,key,"fixtures",team=team_id,last=12)
                if past.get("errors"): raise RuntimeError(str(past["errors"]))
                history_cache[team_id]=past.get("response",[])
            rates[side]=historic_goal_rates(history_cache[team_id],team_id,min(start,now))
        candidates.append({
            "event":teams["home"]["name"]+" – "+teams["away"]["name"],
            "fixture_id":fixture["fixture"]["id"],
            "home_team_id":teams["home"]["id"],"away_team_id":teams["away"]["id"],
            "home_team":teams["home"]["name"],"away_team":teams["away"]["name"],
            "league_season":fixture["league"].get("season"),
            "league_id":fixture["league"].get("id"),"league_country":fixture["league"].get("country"),
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
            "readiness":"NOT_READY: independently verify full official calendar, complete analyst STR/QUAL/MATCH (35/35/30), and independently justified pre-price P(model); expected goals/xG optional",
            "freeze_allowed":False
        })
    path=Path(args.out)/f"{args.date}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"date":args.date,"snapshot_utc":now.isoformat(),
        "source":"API-Football","api_all_fixtures":len(all_fixtures),"pre_match_fixtures":len(fixtures),
        "history_api_calls":len(history_cache),"calendar_gate":"UNVERIFIED",
        "coverage_warning":"API league filter is not an independent or official calendar verification",
        "candidates":candidates,"kb_n_effect":0,"dev_n_effect":0,
        "model_effect":"NONE","register_writes":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(path),"pre_match_fixtures":len(fixtures),
                      "complete_model_inputs":0,"kb_n_effect":0,"dev_n_effect":0}))

if __name__=="__main__":main()
