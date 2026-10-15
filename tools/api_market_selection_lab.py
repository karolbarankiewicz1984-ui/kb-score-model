#!/usr/bin/env python3
"""Read-only historical selection laboratory for frozen API Market settlements.

Never modifies CORE, KB N, DEV N, published picks or live scan configuration.
Retrospective experiments are NOT out-of-sample validation.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

BANDS = [(67,70,"67-69.9"), (70,75,"70-74.9"), (75,80,"75-79.9"),
         (80,85,"80-84.9"), (85,90,"85-89.9"), (90,101,"90-100")]

def valid_number(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def band(score):
    return next((label for low,high,label in BANDS if low<=score<high),"outside")

def load(paths):
    unique = {}
    errors = []
    for path in paths:
        source = json.loads(Path(path).read_text(encoding="utf-8"))
        if source.get("schema") != "api-market-settlement-v2":
            raise ValueError(f"Invalid settlement format: {path}")
        errors.extend(source.get("errors") or [])
        for item in source.get("observations") or []:
            identifier = item.get("observation_id")
            if not identifier:
                raise ValueError(f"Missing observation_id in {path}")
            unique.setdefault(identifier,item)
    return list(unique.values()), len(errors)

def quote(item, min_odd=1.20, bookmakers=None):
    offers=[]
    for offer in (item.get("market_data") or {}).get("quotes") or []:
        bookmaker=str(offer.get("bookmaker") or "").strip()
        odd=offer.get("selected_odd")
        if bookmakers is not None and bookmaker.casefold() not in bookmakers:
            continue
        if valid_number(odd) and odd>=min_odd:
            offers.append({"odd":float(odd),"bookmaker":bookmaker})
    return max(offers,key=lambda o:o["odd"]) if offers else None

def published(rows, threshold=67):
    return [r for r in rows if r.get("published") is True
            and type(r.get("hit")) is int and r["hit"] in (0,1)
            and valid_number(r.get("final_assessment_pct"))
            and r["final_assessment_pct"]>=threshold and r.get("fixture_id") is not None]

def playable(rows, min_odd=1.20, bookmakers=None):
    result=[]
    for r in rows:
        best=quote(r,min_odd,bookmakers)
        if best:
            result.append(dict(r,selected_quote=best))
    return result

def capped(rows, cap=3, diverse=False):
    groups=defaultdict(list)
    for r in rows:
        groups[(r["date"],str(r["fixture_id"]))].append(r)
    out=[]
    for _, options in sorted(groups.items()):
        options.sort(key=lambda r:(-r["final_assessment_pct"],
                                   -r["selected_quote"]["odd"],
                                   str(r["observation_id"])))
        used=set()
        count=0
        for r in options:
            if count>=cap:
                break
            if diverse and r.get("market") in used:
                continue
            out.append(r)
            count+=1
            used.add(r.get("market"))
    return out

def metrics(rows, price=False):
    n=len(rows)
    hits=sum(r["hit"] for r in rows)
    x={"n":n,"hits":hits,"misses":n-hits,
       "fixtures":len({(r["date"],r["fixture_id"]) for r in rows}),
       "accuracy_pct":round(100*hits/n,2) if n else None}
    if price:
        profit=sum(r["selected_quote"]["odd"]-1 if r["hit"] else -1 for r in rows)
        x.update({"profit_units":round(profit,3),
                  "roi_pct":round(100*profit/n,2) if n else None,
                  "mean_odd":round(sum(r["selected_quote"]["odd"] for r in rows)/n,3) if n else None})
    return x

def groups(rows, key):
    result=defaultdict(list)
    for r in rows:
        result[key(r)].append(r)
    return {str(k):metrics(v,True) for k,v in sorted(result.items())}

def audit(rows, errors=0, threshold=67, min_odd=1.20, cap=3):
    pub=published(rows,threshold)
    all_quotes=playable(pub,min_odd)
    scenarios={
        "all_bookmakers_best_quote":all_quotes,
        "without_corners":[r for r in all_quotes if r.get("market")!="corners"],
        "max_3_per_fixture":capped(all_quotes,cap),
        "max_3_distinct_markets":capped(all_quotes,cap,True),
        "sts_superbet_only":playable(pub,min_odd,{"sts","superbet"}),
        "betano_only":playable(pub,min_odd,{"betano"}),
    }
    return {
        "schema":"api-market-selection-lab-v1",
        "method":"retrospective_read_only",
        "threshold":threshold,"min_quoted_odds":min_odd,
        "settlement_errors":errors,
        "all_published":metrics(pub),
        "scenarios":{name:metrics(value,True) for name,value in scenarios.items()},
        "by_date":groups(all_quotes,lambda r:r["date"]),
        "by_market":groups(all_quotes,lambda r:str(r.get("market"))),
        "by_assessment_band":groups(all_quotes,lambda r:band(r["final_assessment_pct"])),
        "notes":[
            "Score /100 is not a calibrated win probability.",
            "Best quoted price is optimistic, not verified Polish-bookmaker availability.",
            "Numerous lines from one fixture are correlated. Distinct fixtures are reported.",
            "No taxes, stake limits, slippage or cancelled bet rules included.",
            "Post-hoc scenarios must be checked prospectively before any production decision."
        ]
    }

def markdown(result):
    def fmt(x):
        return "-" if x is None else f"{x:.2f}"
    lines=["# API Market: selection shadow audit","",
           "**Read-only retrospective experiment; no change to existing model.**","",
           f"Published: {result['all_published']['n']}; missing-stat errors: {result['settlement_errors']}.","",
           "## Selection scenarios","",
           "| Variant | Picks | Matches | Hits | Accuracy % | Profit (1u/pick) | ROI % |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for name,m in result["scenarios"].items():
        lines.append(f"| {name} | {m['n']} | {m['fixtures']} | {m['hits']} | {fmt(m['accuracy_pct'])} | {fmt(m['profit_units'])} | {fmt(m['roi_pct'])} |")
    for key in ("by_date","by_market","by_assessment_band"):
        lines+=["",f"## {key}","","| Group | Picks | Matches | Hits | Accuracy % | ROI % |",
                "|---|---:|---:|---:|---:|---:|"]
        for group,m in result[key].items():
            lines.append(f"| {group} | {m['n']} | {m['fixtures']} | {m['hits']} | {fmt(m['accuracy_pct'])} | {fmt(m['roi_pct'])} |")
    lines+=["","## Limitations",""]+[f"- {x}" for x in result["notes"]]
    return "\n".join(lines)+"\n"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settlement_files",nargs="+",type=Path)
    parser.add_argument("--output",type=Path,default=Path("reports/api_market_scan/selection_lab"))
    parser.add_argument("--min-odd",type=float,default=1.20)
    parser.add_argument("--threshold",type=float,default=67)
    args=parser.parse_args()
    if args.min_odd<1 or not math.isfinite(args.min_odd):
        parser.error("Invalid min odds")
    rows,errors=load(args.settlement_files)
    result=audit(rows,errors,threshold=args.threshold,min_odd=args.min_odd)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"SELECTION_AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (args.output/"SELECTION_AUDIT.md").write_text(markdown(result),encoding="utf-8")
    print(json.dumps(result["scenarios"],ensure_ascii=False))

if __name__=="__main__":
    main()
