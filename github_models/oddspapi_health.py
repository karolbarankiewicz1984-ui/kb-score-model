"""Machine-readable quality gates and visible GitHub warnings for the daily odds PDF.

Warnings do not silently turn a zero-offer report into a successful betting
recommendation. Does not use paid API endpoints; source evidence is preserved.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


def report_health(collection, overlay, gaps, queue):
    if collection.get("bookmakers") != ["superbet.pl"]:
        raise ValueError("unauthorized_bookmaker_scope")
    linked=collection.get("links",{}).get("links",[])
    matched=sum(x.get("status")=="matched" for x in linked)
    quotes=sum(len(s.get("quotes",[])) for s in collection.get("snapshots",[]))
    comparisons=overlay.get("comparisons",[])
    reasons=Counter(x.get("status","unknown") for x in linked)
    warnings=[]
    if not queue.get("fixtures"):
        warnings.append("source_queue_empty")
    if not matched:
        warnings.append("zero_verified_matches")
    if not quotes:
        warnings.append("zero_superbet_quotes")
    if not comparisons:
        warnings.append("zero_exact_model_market_comparisons")
    if len(queue.get("dates",[])) < 7:
        warnings.append("source_queue_less_than_seven_day_horizon")
    if len(queue.get("fixtures",[])) < 20:
        warnings.append("source_queue_unusually_small_review_provenance")
    for name in ("fouls","cards"):
        item=gaps.get("by_market",{}).get(name,{})
        if item.get("high_confidence_candidates",0) and not item.get("priced_and_settlement_compatible",0):
            warnings.append("no_comparable_superbet_"+name)
    return {
        "schema":"github-models-oddspapi-collection-health-v1",
        "source_queue_fixtures":len(queue.get("fixtures",[])),
        "source_queue_generated_at_utc":queue.get("generated_at_utc"),
        "linked_fixtures":matched,
        "link_status_counts":dict(reasons),
        "priced_fixtures":len(collection.get("snapshots",[])),
        "active_superbet_quotes":quotes,
        "exact_model_market_comparisons":len(comparisons),
        "candidate_market_gaps":gaps.get("by_market",{}),
        "warnings":warnings,
        "status":"attention" if warnings else "ok",
        "never_invent_or_promote_picks":True,
    }


def main():
    p=argparse.ArgumentParser()
    for k in ("collection","overlay","gaps","queue","out"):
        p.add_argument("--"+k,required=True)
    a=p.parse_args()
    get=lambda name:json.loads(Path(name).read_text(encoding="utf-8"))
    report=report_health(get(a.collection),get(a.overlay),get(a.gaps),get(a.queue))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ODDSPAPI_HEALTH="+report["status"])
    print("ODDSPAPI_HEALTH_WARNINGS="+",".join(report["warnings"]))
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    markdown=["### MultiModel V2 — OddsPapi source & coverage",
              "| Check | Verified |","|---|---:|",
              "| Queue fixtures | "+str(report["source_queue_fixtures"])+" |",
              "| Matched fixtures | "+str(report["linked_fixtures"])+" |",
              "| Priced fixtures | "+str(report["priced_fixtures"])+" |",
              "| Quotes | "+str(report["active_superbet_quotes"])+" |",
              "| Exact model/market comparisons | "+str(report["exact_model_market_comparisons"])+" |",
              "Warnings: "+(", ".join(report["warnings"]) if report["warnings"] else "none")]
    if summary:
        with open(summary,"a",encoding="utf-8") as stream:
            stream.write("\n".join(markdown)+"\n")
    for reason in report["warnings"]:
        print("::warning title=OddsPapi collection coverage::"+reason)
    # No automatic rollback or model promotion.
    return report


if __name__=="__main__":
    main()
