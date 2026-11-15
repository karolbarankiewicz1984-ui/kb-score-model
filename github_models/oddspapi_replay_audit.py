"""Audit previously frozen Polish odds overlays against independent final results.

Never retroactively backdate model predictions or choose a best price after
observing outcomes. The first timestamped verified quote is selected per
distinct fixture/market/side/line. ROI is only a descriptive simulated return
at then-recorded exact odds, not a profit promise.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean

from github_models.market_settlement import settle_markets
from github_models.settlement import matching_outcomes
from github_models.oddspapi_market import utc


def audit_one(overlay, queue, history, events, now):
    valid=[]
    rejected=Counter()
    for r in overlay.get("comparisons", []):
        if (r.get("bookmaker")!="superbet.pl" or
            r.get("eligible_min_odds_1_20") is not True):
            rejected["book_or_price_unavailable"]+=1;continue
        try:
            kickoff=utc(r["kickoff_utc"])
            captured=utc(r["odds_captured_at_utc"])
            frozen=utc(r["forecast_frozen_at_utc"])
            odds=r["price"]
            p=r["p_model"]
            if (not frozen<kickoff or not captured<kickoff or
                captured>now or frozen>now):
                rejected["not_verified_prekickoff"]+=1;continue
            if type(odds) not in (int,float) or not math.isfinite(odds) or odds<1.2:
                rejected["price_invalid"]+=1;continue
            if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:
                rejected["model_probability_invalid"]+=1;continue
        except (ValueError,KeyError,TypeError):
            rejected["time_or_price_invalid"]+=1;continue
        valid.append(r)
    event_rows=[]
    event_indexes=[]
    entries=[]
    fixtures={str(f["fixture_id"]):f for f in queue.get("fixtures",[])}
    for row in valid:
        key=(str(row["fixture_id"]),row["market"],row["line"],row["selection"])
        entry={"key":key,"fixture_id":str(row["fixture_id"]),
               "market":row["market"],"selection":row["selection"],
               "line":row["line"],"kickoff_utc":row["kickoff_utc"],
               "p_model":row["p_model"],"price":row["price"],
               "p_market":row.get("market_no_vig_probability"),
               "odds_captured_at_utc":row["odds_captured_at_utc"],
               "forecast_frozen_at_utc":row["forecast_frozen_at_utc"],
               "status":"unresolved","reason":"final_result_pending"}
        if str(row["fixture_id"]) not in fixtures:
            entry["reason"]="fixture_missing_in_archived_queue"
        elif row["market"]=="1X2":
            try:
                candidates=matching_outcomes(fixtures[str(row["fixture_id"])],history,
                                             as_of_utc=now.isoformat(),
                                             resolved_identity=row.get("resolved_identity"))
                if len(candidates)==1:
                    event=candidates[0]
                    hg,ag=event["home_goals"],event["away_goals"]
                    actual="1" if hg>ag else "2" if hg<ag else "X"
                    entry.update(status="settled",hit=(actual==row["selection"]),reason=None)
                elif len(candidates)>1:
                    entry["reason"]="ambiguous_verified_final"
                else:
                    entry["reason"]="no_verified_final_yet"
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                entry["reason"]="final_identity_unverified:"+type(exc).__name__
        elif row["market"] in {"goals","corners","cards","fouls"} and row.get("settlement_verified"):
            event_indexes.append(len(entries))
            event_rows.append({"fixture_id":row["fixture_id"],"market":row["market"],
                               "line":row["line"],"selection":row["selection"],
                               "probability":row["p_model"],
                               "frozen_at_utc":row["forecast_frozen_at_utc"],
                               "resolved_identity":row.get("resolved_identity")})
        else:
            entry["reason"]="market_settlement_not_verified"
        entries.append(entry)
    if event_rows:
        report=settle_markets({"markets":event_rows},queue,history,events,now.isoformat())
        if len(report["settlements"])!=len(event_indexes):
            raise ValueError("market_settlement_result_misalignment")
        for index,result in zip(event_indexes,report["settlements"]):
            row=entries[index]
            if result["status"]=="settled":
                row.update(status="settled",reason=None,hit=result["hit"])
            else:
                row.update(reason=result.get("reason") or result["status"])
    return entries,rejected


def _metrics(items):
    if not items:return None
    return {"n":len(items),"matches":len({r["fixture_id"] for r in items}),
            "hit_rate":round(mean(float(r["hit"]) for r in items),6),
            "brier":round(mean((r["p_test"]-float(r["hit"]))**2 for r in items),6),
            "log_loss":round(mean(-(int(r["hit"])*math.log(max(r["p_test"],1e-12))+
                            (1-int(r["hit"]))*math.log(max(1-r["p_test"],1e-12))) for r in items),6),
            "unit_stake_roi_before_fees_and_tax":round(mean(r["price"]*int(r["hit"])-1 for r in items),6)}


def run(root, history, events, as_of_utc):
    now=utc(as_of_utc)
    rows=[]
    errors=Counter()
    snapshots_seen=0
    for file in sorted(Path(root).rglob("market_overlay.json")):
        folder=file.parent
        queuefile=folder/"pitch_queue.json"
        if not queuefile.is_file():
            errors["archive_missing_queue"]+=1;continue
        try:
            overlay=json.loads(file.read_text(encoding="utf-8"))
            queue=json.loads(queuefile.read_text(encoding="utf-8"))
            chunk,issues=audit_one(overlay,queue,history,events,now)
            rows+=chunk
            errors.update(issues)
            snapshots_seen+=1
        except (OSError,ValueError,TypeError,KeyError) as exc:
            errors["archive_file_invalid:"+type(exc).__name__]+=1
    # Freeze first observed price per exact selection, do not choose an
    # ex-post maximum, and do not count repeated daily snapshots as new games.
    history_by_key=defaultdict(list)
    for row in rows:
        history_by_key[tuple(row["key"])].append(row)
    unique={}
    trends=[]
    for key,values in history_by_key.items():
        values.sort(key=lambda r:(r["odds_captured_at_utc"],r["forecast_frozen_at_utc"]))
        first=values[0]
        distinct_hits={r.get("hit") for r in values if r.get("status")=="settled"}
        if len(distinct_hits)>1:
            errors["contradictory_settlements"]+=1
            continue
        if first["status"]!="settled":
            eligible=next((r for r in values if r["status"]=="settled"),None)
            if eligible:
                # Use settlement from later report, but retain first price and P.
                first=dict(first,status="settled",reason=None,hit=eligible["hit"])
        unique[key]=first
        if len(values)>=2:
            last=values[-1]
            trends.append({"fixture_id":key[0],"market":key[1],"line":key[2],
                           "selection":key[3],"snapshots":len(values),
                           "first_price":first["price"],"last_price":last["price"],
                           "first_captured_utc":first["odds_captured_at_utc"],
                           "last_captured_utc":last["odds_captured_at_utc"],
                           "price_delta":round(last["price"]-first["price"],5)})
    settled=[r for r in unique.values() if r.get("status")=="settled"]
    variants=defaultdict(list)
    by_market=defaultdict(list)
    by_band=defaultdict(list)
    for row in settled:
        m=row.get("p_market")
        p=row["p_model"]
        tested=[("model_only",p)]
        if type(m) in (int,float) and math.isfinite(m) and 0<=m<=1:
            if abs(p-m)<=.10:
                tested.append(("market_agreement_filter",p))
            tested.append(("market_50_50_shadow",.5*(p+m)))
        for variant,score in tested:
            record=dict(row,p_test=score)
            variants[variant].append(record)
            by_market[(variant,row["market"])].append(record)
            band = "lt70" if score<.7 else "70-80" if score<.8 else "80-90" if score<.9 else "90-100"
            by_band[(variant,band)].append(record)
    return {"schema":"github-models-oddspapi-frozen-audit-v1",
            "as_of_utc":as_of_utc,
            "archives_processed":snapshots_seen,
            "recorded_selection_quotes":len(rows),
            "unique_selection_quotes":len(unique),
            "settled_selection_quotes":len(settled),
            "unique_settled_fixtures":len({r["fixture_id"] for r in settled}),
            "duplicates_suppressed":len(rows)-len(unique),
            "exclusions":dict(errors),
            "summary":[{"variant":v,**_metrics(g)} for v,g in sorted(variants.items())],
            "by_market":[{"variant":v,"market":m,**_metrics(g)}
                         for (v,m),g in sorted(by_market.items())],
            "by_probability_band":[{"variant":v,"band":b,**_metrics(g)}
                                   for (v,b),g in sorted(by_band.items())],
            "price_changes":trends[:1000],
            "promotion_gate":{"minimum_distinct_matches":100,
                              "minimum_reached":len({r["fixture_id"] for r in settled})>=100,
                              "production_weight_change_permitted":False},
            "no_model_retraining":True,
            "caveat":"Retrospective only; uncalibrated p_model and single bookmaker prices, NO independently established EV.",
            "decision":"INSUFFICIENT_PROSPECTIVE_EVIDENCE"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-dir",required=True)
    p.add_argument("--history",required=True)
    p.add_argument("--events",required=True)
    p.add_argument("--as-of",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    get=lambda fn:json.loads(Path(fn).read_text(encoding="utf-8"))
    result=run(Path(a.archive_dir),get(a.history),get(a.events),a.as_of)
    dest=Path(a.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                    encoding="utf-8")
    print("AUDIT_ARCHIVES="+str(result["archives_processed"]))
    print("AUDIT_UNIQUE_SETTLED_FIXTURES="+str(result["unique_settled_fixtures"]))
    print("AUDIT_DECISION="+result["decision"])


if __name__=="__main__":
    main()
