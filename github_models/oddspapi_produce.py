"""Build a verified Superbet research overlay, retrospective audit and separate PDF."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from github_models.oddspapi_integration import market_overlay, compare_variants
from github_models.market_settlement import settle_markets
from github_models.oddspapi_report_pdf import make_pdf
from github_models.oddspapi_market_gaps import coverage


def _write(path,data):
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                    encoding="utf-8")


def run(collection, queue, frozen, event_markets, history, event_history, outdir):
    if collection.get("bookmakers") != ["superbet.pl"]:
        raise ValueError("unsupported_bookmaker_scope")
    if frozen.get("schema")!="github-models-independent-predictions-v1":
        raise ValueError("wrong_frozen_prediction_schema")
    if event_markets.get("schema")!="github-models-event-markets-v1":
        raise ValueError("wrong_frozen_events_schema")
    as_of=collection["as_of_utc"]
    overlay=market_overlay(collection["links"],collection["snapshots"],event_markets,
                          as_of_utc=as_of,frozen_predictions=frozen)
    # No settlement inference from bookmaker market data. Verify outcomes in
    # separate independent final-score and event databases.
    if history is None or event_history is None:
        settlements={"schema":"github-models-event-settlement-v1",
                     "settlements":[],"status":"awaiting_verified_final_data"}
    else:
        settlements=settle_markets(event_markets,queue,history,event_history,as_of)
    audit=compare_variants(overlay,settlements)
    gaps=coverage(collection,event_markets,as_of_utc=as_of)
    out=Path(outdir)
    _write(out/"market_overlay.json",overlay)
    _write(out/"market_gaps.json",gaps)
    _write(out/"actual_settlements.json",settlements)
    _write(out/"shadow_variants_audit.json",audit)
    pdf=out/"MULTIMODEL_V2_SUPERBET_MARKET.pdf"
    make_pdf(collection,overlay,audit,pdf,market_gaps=gaps)
    print("MARKET_OVERLAY_COMPARISONS="+str(len(overlay["comparisons"])))
    print("MODEL_ONLY_UNQUOTED="+str(len(gaps["model_only_candidates"])))
    print("MODEL_ONLY_BY_MARKET="+json.dumps(gaps["by_market"],sort_keys=True))
    print("SETTLED_FORECASTS="+str(sum(x["status"]=="settled" for x in settlements["settlements"])))
    print("AUDIT_VARIANTS="+str(len(audit["metrics"])))
    print("ODDS_MARKET_PDF="+str(pdf))
    return overlay,audit


def main():
    p=argparse.ArgumentParser()
    for k in ("collection","queue","frozen","markets","outdir"):
        p.add_argument("--"+k,required=True)
    p.add_argument("--history")
    p.add_argument("--events")
    a=p.parse_args()
    get=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    run(get(a.collection),get(a.queue),get(a.frozen),
        get(a.markets),get(a.history) if a.history else None,
        get(a.events) if a.events else None,a.outdir)


if __name__=="__main__":
    main()
