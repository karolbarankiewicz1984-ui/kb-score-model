"""Quota-limited Polish bookmaker collection via OddsPapi v4.

Exactly Superbet.pl only while STS is absent from the subscription catalogue.
One fixtures call, at most N tournament-batch calls; caches the soccer market
dictionary across Actions runs (as an Actions cache, NOT a repo secret).
Research forecasts are never changed. Never log raw provider response.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from github_models.oddspapi_integration import join_fixtures
from github_models.oddspapi_market import api_get, normalize_snapshot, subscription_budget

SPORT_ID = 10
POLISH_BOOK = "superbet.pl"
RESERVE = 50
MAX_TOTAL_CALLS = 200


def _utc(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone_required")
    return result.astimezone(timezone.utc)


def extract_batch(raw):
    """Accept documented single fixture plus safe documented batch variants.

    Reject unknown structures rather than silently publishing no odds.
    """
    if isinstance(raw,list):
        if any(not isinstance(x,dict) or not x.get("fixtureId") for x in raw):
            raise ValueError("oddspapi_batch_list_schema_invalid")
        return raw
    if not isinstance(raw,dict):
        raise ValueError("oddspapi_batch_response_invalid")
    if "fixtureId" in raw:
        return [raw]
    if isinstance(raw.get("fixtures"),list):
        return extract_batch(raw["fixtures"])
    if isinstance(raw.get("data"),list):
        return extract_batch(raw["data"])
    if raw and all(isinstance(v,dict) and v.get("fixtureId") for v in raw.values()):
        return list(raw.values())
    if raw=={}:
        return []
    raise ValueError("oddspapi_batch_response_unknown_shape")


def _save(path, obj):
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(obj, ensure_ascii=False, separators=(",",":"),
                               allow_nan=False)+"\n", encoding="utf-8")


def _quota_state(account, anticipated):
    state=subscription_budget(account, requested=anticipated, reserve=RESERVE)
    if state["request_limit"] != 250:
        # Keep the program safe under plan changes: never allocate more than
        # the originally agreed 250-call budget without operator review.
        if state["request_limit"] > 250 and state["request_count"]+anticipated > MAX_TOTAL_CALLS:
            raise RuntimeError("manual_review_required_for_plan_change")
    if state["request_count"]+anticipated>min(state["request_limit"]-RESERVE,MAX_TOTAL_CALLS):
        raise RuntimeError("monthly_odds_spend_guard")
    books=set(state["bookmakers_in_plan"])
    if POLISH_BOOK not in books:
        raise RuntimeError("polish_superbet_not_in_subscription")
    return state, ("sts.pl" in books or "sts" in books)


def _cache_catalog(path):
    dest=Path(path)
    if dest.is_file():
        cached=json.loads(dest.read_text(encoding="utf-8"))
        if (isinstance(cached,dict) and cached.get("provider")=="oddspapi-v4"
                and isinstance(cached.get("soccer_markets"),list)
                and len(cached["soccer_markets"])>100):
            return cached["soccer_markets"],False
    raw=api_get("markets",params={"language":"en"})
    if not isinstance(raw,list):
        raise ValueError("oddspapi_market_catalog_unknown_shape")
    soccer=[m for m in raw if m.get("sportId")==SPORT_ID]
    if len(soccer)<100:
        raise ValueError("oddspapi_market_catalog_too_small")
    _save(path,{"provider":"oddspapi-v4","cached_at_utc":datetime.now(timezone.utc).isoformat(),
                "soccer_markets":soccer})
    return soccer,True


def collect(queue, *, now, catalog_path, batches=2, output_dir):
    if type(batches) is not int or not 1<=batches<=3:
        raise ValueError("one_to_three_batches_per_run")
    stamp=_utc(now)
    month=stamp.strftime("%Y-%m")
    catalog_path=Path(catalog_path)
    if month not in str(catalog_path):
        raise ValueError("market_cache_must_be_month_scoped")
    account=api_get("account")
    has_catalog=catalog_path.is_file()
    anticipated=1+batches+(0 if has_catalog else 1)
    state,sts_in_plan=_quota_state(account,anticipated)
    if sts_in_plan:
        # Explicit user preference was Superbet + STS. STS requires a separate
        # provider validation before accepting new bookmaker data.
        print("STS_STATUS=CATALOG_LISTING_FOUND_NEEDS_SAFE_VALIDATION")
    else:
        print("STS_STATUS=NOT_AVAILABLE_IN_SUBSCRIPTION")
    print("POLISH_BOOKMAKER=superbet.pl")
    print("QUOTA_USED_BEFORE="+str(state["request_count"]))
    print("QUOTA_REMAINING_AFTER_RESERVE="+str(state["remaining_before_reserve"]))
    print("BILLABLE_RUN_MAX="+str(anticipated))
    catalog,was_refreshed=_cache_catalog(catalog_path)
    time.sleep(1.1)
    end=stamp+timedelta(days=7)
    raw_fixtures=api_get("fixtures",params={
        "sportId":SPORT_ID,"from":stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to":end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "statusId":0,"hasOdds":"true",
        "bookmakers":POLISH_BOOK,"language":"en"})
    if not isinstance(raw_fixtures,list):
        raise ValueError("oddspapi_fixtures_not_list")
    links=join_fixtures(queue,raw_fixtures,as_of_utc=stamp.isoformat())
    good=[row for row in links["links"] if row["status"]=="matched"]
    by_tournament=Counter(int(row["tournament_id"]) for row in good)
    selected_ids=[tid for tid,_ in sorted(by_tournament.items(),
                              key=lambda pair:(-pair[1],pair[0]))[:batches*3]]
    verified={row["odds_fixture_id"]:row for row in good if int(row["tournament_id"]) in selected_ids}
    print("PITCH_QUEUE_FIXTURES="+str(len(queue.get("fixtures",[]))))
    print("ODDSPAPI_FIXTURES_WITH_SUPERBET="+str(len(raw_fixtures)))
    print("VERIFIED_FIXTURE_LINKS="+str(len(good)))
    print("SELECTED_TOURNAMENTS="+str(len(selected_ids)))
    all_snapshots=[]
    request_log=[{"endpoint":"markets","calls":int(was_refreshed)},
                 {"endpoint":"fixtures","calls":1}]
    for pos in range(0,len(selected_ids),3):
        group=selected_ids[pos:pos+3]
        if not group: continue
        # Recheck real account quota before EACH billed call and never retry
        # without operator action. Another consumer could use the shared plan.
        check=api_get("account")
        _quota_state(check,1)
        time.sleep(1.1)
        raw=api_get("odds-by-tournaments",params={
            "tournamentIds":",".join(str(x) for x in group),
            "bookmaker":POLISH_BOOK,"language":"en","verbosity":3})
        request_log.append({"endpoint":"odds-by-tournaments","calls":1,
                            "tournament_count":len(group)})
        fixtures=extract_batch(raw)
        for odd in fixtures:
            fid=str(odd["fixtureId"])
            link=verified.get(fid)
            if link is None: continue
            payload=dict(odd)
            if str(payload.get("tournamentId")) != str(link["tournament_id"]):
                raise ValueError("batch_tournament_identity_mismatch")
            # One bookmaker only. Explicitly reject all other book keys.
            blocks=payload.get("bookmakerOdds") or {}
            if any(slug!=POLISH_BOOK for slug in blocks):
                raise ValueError("unexpected_bookmaker_in_filtered_batch")
            try:
                snapshot=normalize_snapshot(payload,catalog,
                    captured_at_utc=datetime.now(timezone.utc).isoformat())
            except ValueError as e:
                if str(e)=="snapshot_not_strictly_prematch":
                    continue
                raise
            snapshot["pitch_fixture_id"]=link["fixture_id"]
            snapshot["home"]=link["home"]
            snapshot["away"]=link["away"]
            snapshot["tournament_id"]=link["tournament_id"]
            all_snapshots.append(snapshot)
        print("BATCH_"+str(1+pos//3)+"_FIXTURES="+str(len(fixtures)))
    if len({x["fixture_id"] for x in all_snapshots})!=len(all_snapshots):
        raise ValueError("duplicate_batch_fixture")
    results={"schema":"github-models-oddspapi-poland-collection-v1",
             "provider":"OddsPapi","bookmakers":[POLISH_BOOK],
             "sts_status":"not_in_account" if not sts_in_plan else "not_validated",
             "as_of_utc":datetime.now(timezone.utc).isoformat(),"market_catalog_refresh":was_refreshed,
             "links":links,
             "captured_fixture_count":len(all_snapshots),
             "captured_quote_count":sum(len(x["quotes"]) for x in all_snapshots),
             "billable_requests_made":sum(x["calls"] for x in request_log),
             "monthly_limit":state["request_limit"],
             "monthly_usage_before":state["request_count"],
             "request_log":request_log,
             "snapshots":all_snapshots}
    dest=Path(output_dir)
    _save(dest/"collection.json", results)
    _save(dest/"fixture_links.json", links)
    _save(dest/"quota_and_scope.json",{
        "schema":"github-models-odds-collection-summary-v1",
        **{k:v for k,v in results.items() if k not in ("snapshots","links")},
        "future_deployment":"research_only"})
    print("COLLECTION_STATUS=PASS_RESEARCH")
    print("COLLECTION_FIXTURES="+str(len(all_snapshots)))
    print("COLLECTION_QUOTES="+str(results["captured_quote_count"]))
    print("BILLABLE_REQUESTS_USED_THIS_RUN="+str(results["billable_requests_made"]))
    return results


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True)
    p.add_argument("--catalog-cache",required=True)
    p.add_argument("--batches",type=int,default=1)
    p.add_argument("--output-dir",required=True)
    a=p.parse_args(argv)
    queue=json.loads(Path(a.queue).read_text(encoding="utf-8"))
    collect(queue,now=datetime.now(timezone.utc).isoformat(),
            catalog_path=a.catalog_cache,batches=a.batches,output_dir=a.output_dir)


if __name__=="__main__":
    main()
