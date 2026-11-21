"""One-off read-only OddsPapi bookings settlement evidence, never a payout check."""
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

FIXTURES = (
    "id1000002472341382", "id1000018272037454",
    "id1000018272037464", "id1000005373093090",
)
MARKETS = {str(10914+4*i): i+0.5 for i in range(7)}
STATUSES = {"WIN", "LOSE", "PUSH", "HALFWIN", "HALFLOSS", "CANCELLED", "UNDECIDED"}

def utc(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive_timestamp")
    return d

def request(endpoint, **params):
    if endpoint not in ("account", "settlements"):
        raise ValueError("endpoint_not_allowed")
    secret = os.environ.get("ODDSPAPI_API_KEY")
    if not secret:
        return None, "missing_secret"
    url = "https://api.oddspapi.io/v4/" + endpoint + "?" + urlencode(
        {**params, "apiKey": secret})
    try:
        with urlopen(Request(url, headers={"User-Agent":"multimodel-research-audit/1.0"}), timeout=25) as resp:
            return json.load(resp), None
    except HTTPError as exc:
        return None, "http_" + str(exc.code)
    except (URLError, TimeoutError, ValueError, OSError):
        return None, "network_or_response_error"

def quota():
    a, error = request("account")
    if error or not isinstance(a, dict):
        return None, error or "invalid_account"
    sid = a.get("current_subscription_id")
    matches = [s for s in a.get("subscriptions",[]) if s.get("is_active")
               and s.get("subscription_id")==sid]
    if len(matches)!=1:
        return None, "active_subscription_unverified"
    lim, used = matches[0].get("request_limit"), matches[0].get("request_count")
    if type(lim) is not int or type(used) is not int or lim<1 or used<0:
        return None, "invalid_quota"
    return {"limit":lim,"used":used,"cap":max(0,min(200,lim-50))}, None

def exact_quotes(snapshot):
    out={}
    for q in snapshot["quotes"]:
        mid=str(q.get("market_id"))
        if (q.get("bookmaker")!="superbet.pl" or q.get("market_name")!="Bookings - Over Under Full Time"
            or q.get("market_type")!="totals-bookings" or q.get("period")!="fulltime"
            or q.get("player_prop") is not False or str(q.get("player_id"))!="0"
            or mid not in MARKETS or q.get("handicap")!=MARKETS[mid]
            or q.get("outcome_name") not in ("Over","Under")):
            continue
        side=q["outcome_name"].lower()
        oid=str(q["outcome_id"])
        if oid!=str(int(mid)+(side=="under")):
            raise ValueError("unexpected_catalog_outcome_id")
        key=(mid,side)
        if key in out and out[key]!=oid:
            raise ValueError("duplicate_conflicting_outcome_id")
        out[key]=oid
    return out

def extract(payload, fid, quotes):
    if not isinstance(payload,dict) or str(payload.get("fixtureId"))!=fid:
        return {"status":"invalid_fixture_response"}
    markets=payload.get("markets")
    if not isinstance(markets,dict):
        return {"status":"invalid_markets_response"}
    rows=[]
    lower, upper=0, None
    for mid,line in MARKETS.items():
        outcomes=markets.get(mid,{}).get("outcomes",{})
        vals={}
        for side in ("over","under"):
            if (mid,side) not in quotes:
                continue
            oid=quotes[(mid,side)]
            v=outcomes.get(oid,{}).get("players",{}).get("0",{}).get("result")
            vals[side]=v if v in STATUSES else None
        if not vals:
            continue
        pair_status="incomplete_or_unresolved"
        if vals.get("over")=="WIN" and vals.get("under")=="LOSE":
            lower=max(lower,int(line)+1)
            pair_status="complete"
        elif vals.get("over")=="LOSE" and vals.get("under")=="WIN":
            upper=min(upper,int(line)) if upper is not None else int(line)
            pair_status="complete"
        rows.append({"market_id":mid,"line":line,"statuses":vals,"pair_status":pair_status})
    complete=sum(r["pair_status"]=="complete" for r in rows)
    conflict=upper is not None and lower>upper
    return {"status":"contradictory" if conflict else ("observed" if complete else "unresolved"),
            "rows":rows,"complete_pairs":complete,
            "provider_integer_total_lower":lower if complete and not conflict else None,
            "provider_integer_total_upper":upper if complete and not conflict else None,
            "uniquely_implied_total":lower if complete and not conflict and upper==lower else None}

def main():
    co=json.loads(Path("input/collection.json").read_text())
    assert co["bookmakers"]==["superbet.pl"]
    assert co["provider"] in ("OddsPapi","oddspapi-v4")
    linked={str(x["odds_fixture_id"]):str(x["fixture_id"]) for x in co["links"]["links"]
            if x["status"]=="matched"}
    allowed={}
    now=datetime.now(timezone.utc)
    for s in co["snapshots"]:
        fid=str(s["fixture_id"])
        if fid not in FIXTURES:
            continue
        if fid in allowed or linked.get(fid)!=str(s["pitch_fixture_id"]) or s["provider"]!="oddspapi-v4":
            raise ValueError("unverified_fixture_link")
        if not (utc(s["captured_at_utc"]) < utc(s["kickoff_utc"]) <= now-timedelta(hours=3)):
            raise ValueError("fixture_timing_unverified")
        quotes=exact_quotes(s)
        if not quotes:
            raise ValueError("no_archived_bookings")
        allowed[fid]=(s,quotes)
    if set(allowed)!=set(FIXTURES):
        raise ValueError("required_archive_fixtures_missing")
    before,error=quota()
    result={"schema":"multimodel-bookings-settlements-pilot-v1",
            "source_run_id":44776156677,"as_of_utc":now.isoformat(),
            "quota_before":before,"quota_error":error,"attempted_billable_calls":0,
            "bookmaker":"superbet.pl","provider_settlement_is_bookmaker_payout":False,
            "bookings_unit_confirmed":False,"production_promotion":False,
            "max_billable_calls":4,"fixtures":[]}
    if before and before["used"]+len(FIXTURES)<=before["cap"]:
        for fid in FIXTURES:
            q,err=quota()
            if err or q["used"]+1>q["cap"]:
                result["stop_reason"]=err or "quota_reserve_guard"
                break
            s,quotes=allowed[fid]
            result["attempted_billable_calls"]+=1
            payload,err=request("settlements",fixtureId=fid,playerId=0)
            record={"fixture_id":fid,"home":s["home"],"away":s["away"],"kickoff_utc":s["kickoff_utc"]}
            record.update({"status":"request_failed","reason":err} if err else extract(payload,fid,quotes))
            result["fixtures"].append(record)
            if err in ("http_401","http_403","http_429"):
                result["stop_reason"]=err
                break
            time.sleep(2.2)
    else:
        result["stop_reason"]=error or "quota_reserve_guard"
    result["quota_after"],result["quota_after_error"]=quota()
    target=Path("out/BOOKINGS_SETTLEMENT_PILOT.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
