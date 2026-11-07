"""Read-only API-Football final-score bridge for MULTIMODEL V2 settlement."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from github_models.fast_final_parser import parse_final, parse_stats

def fetch(endpoint, params, key):
    url = "https://v3.football.api-sports.io/" + endpoint + "?" + urlencode(params)
    req = Request(url, headers={"x-apisports-key": key, "User-Agent": "multimodel-v2-settlement/1.0"})
    with urlopen(req, timeout=25) as response:
        raw=response.read(5_000_000)
    if len(raw)>=5_000_000:
        raise ValueError("response_size_limit")
    payload=json.loads(raw)
    if payload.get("errors") or not isinstance(payload.get("response"),list):
        raise ValueError("invalid_api_response")
    return payload["response"],hashlib.sha256(raw).hexdigest()

def observed():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def identity(row):
    return (row.get("league"),row.get("home"),row.get("away"),row.get("match_date"))

def collect(history,events,key,days,max_stats=24,getter=fetch):
    manifest={"schema":"v2-postmatch-api-football-v1","status":"ok",
              "queries":[],"accepted_scores":0,"event_matches":0,
              "stats_requests":0,"stats_request_limit":max_stats,
              "corroborated_existing_scores":0,"rejections":{},
              "timestamps":"observation time, not actual whistle time",
              "training_data_unchanged":True}
    if not key:
        manifest["status"]="missing_key"
        return history,events,manifest
    added_scores=[]
    added_events=[]
    rejected=Counter()
    originals={}
    for row in history:
        originals.setdefault(identity(row),set()).add((row["home_goals"],row["away_goals"]))
    already=set()
    for day in days:
        try:
            matches,digest=getter("fixtures",{"date":day,"timezone":"Europe/Warsaw","status":"FT"},key)
            time=observed()
            manifest["queries"].append({"date":day,"status":"ok","rows":len(matches),"sha256":digest,"observed_at_utc":time})
        except Exception as exc:
            manifest["status"]="partial_provider_failure"
            manifest["queries"].append({"date":day,"status":"error","error_type":type(exc).__name__})
            continue
        for match in matches:
            try:
                row=parse_final(match,history,time)
                if row["fixture_id"] in already:
                    raise ValueError("duplicate_provider_fixture")
                already.add(row["fixture_id"])
            except (ValueError,KeyError,TypeError,AttributeError) as exc:
                rejected[str(exc)]+=1
                continue
            old=originals.get(identity(row),set())
            if len(old)==1 and (row["home_goals"],row["away_goals"]) in old:
                manifest["corroborated_existing_scores"]+=1
            else:
                added_scores.append(row)
                if old:
                    rejected["conflicting_provider_score_kept_for_ambiguous_review"]+=1
            if manifest["stats_requests"]>=max_stats:
                continue
            try:
                manifest["stats_requests"]+=1
                response,_=getter("fixtures/statistics",{"fixture":int(row["source_record_id"])},key)
                counts=parse_stats(response,match)
                if not counts:
                    rejected["no_verified_event_counts"]+=1
                    continue
                now=observed()
                new={k:row[k] for k in ("fixture_id","league","country_code","home","away","match_date","kickoff_utc","source_provider","source_record_id")}
                new.update(completed_at_utc=now,published_at_utc=now,events=counts)
                added_events.append(new)
            except Exception as exc:
                rejected["statistics_"+type(exc).__name__]+=1
    manifest["accepted_scores"]=len(added_scores)
    manifest["event_matches"]=len(added_events)
    manifest["rejections"]=dict(rejected)
    return history+added_scores,events+added_events,manifest

def main():
    p=argparse.ArgumentParser()
    for arg in ("history-input","events-input","history-output","events-output","manifest"):
        p.add_argument("--"+arg,required=True)
    p.add_argument("--days-back",type=int,default=2)
    p.add_argument("--max-stats",type=int,default=24)
    args=p.parse_args()
    if not 1<=args.days_back<=3 or not 0<=args.max_stats<=80:
        p.error("invalid_limits")
    load=lambda p:json.loads(Path(p).read_text(encoding="utf-8"))
    today=datetime.now(ZoneInfo("Europe/Warsaw")).date()
    days=[(today-timedelta(days=i)).isoformat() for i in range(1,args.days_back+1)]
    history,events,manifest=collect(load(args.history_input),load(args.events_input),
          os.getenv("API_FOOTBALL_KEY",""),days,args.max_stats)
    for name,value in [(args.history_output,history),(args.events_output,events),(args.manifest,manifest)]:
        dest=Path(name)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:manifest[k] for k in ("status","accepted_scores","event_matches","stats_requests","corroborated_existing_scores")},ensure_ascii=False))
if __name__=="__main__":
    main()
