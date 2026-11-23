"""Join frozen A/B/C selections with verified post-match settlements."""
from github_models.abc_filter import evaluate
from github_models.settlement import settle
from github_models.market_settlement import settle_markets

def audit(predictions, markets, queue, history, events, as_of):
    candidates=evaluate(predictions,markets)["candidates"]
    one=settle(predictions,queue,history,as_of)["settlements"]
    two=settle_markets(markets,queue,history,events,as_of)["settlements"]
    if len(one)!=len(predictions["predictions"]) or len(two)!=len(markets["markets"]):
        raise ValueError("settlement_alignment")
    a={(str(p["fixture_id"]),p["model_id"]):s for p,s in zip(predictions["predictions"],one)}
    b={(str(p["fixture_id"]),p["model_id"],p["market"],p["line"],p["selection"]):s for p,s in zip(markets["markets"],two)}
    out=[]
    for c in candidates:
        fid=str(c["fixture_id"])
        if c["market"] in ("1X2", "double_chance"):
            x=a.get((fid,"github-elo"),{})
            y=a.get((fid,"callumfm-dixon-coles"),{})
            ok=x.get("status")=="settled" and y.get("status")=="settled" and x.get("actual")==y.get("actual")
            # Double chance covers two disjoint 1X2 results; no additional
            # outcomes feed or implied bookmaker settlement needed.
            dc_results = {"1X": ("1", "X"), "X2": ("X", "2"), "12": ("1", "2")}
            hit = (x["actual"] in dc_results[c["selection"]]
                   if c["market"] == "double_chance" else
                   x["actual"] == c["selection"]) if ok else None
            reason=None if ok else (x.get("reason") or y.get("reason") or "no_verified_final_yet")
            probability=c["probability_min"]
        else:
            x=b.get((fid,c["model"],c["market"],c["line"],c["selection"]),{})
            ok=x.get("status")=="settled"
            hit=x["hit"] if ok else None
            reason=None if ok else (x.get("reason") or "no_verified_statistics_yet")
            probability=c["probability"]
        out.append(dict(variant=c["variant"],fixture_id=fid,market=c["market"],
            probability=probability,line=c.get("line"),selection=c["selection"],
            status="settled" if ok else "unresolved",reason=reason,hit=hit))
    return out
