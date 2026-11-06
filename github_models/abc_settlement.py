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
        if c["market"]=="1X2":
            x=a.get((fid,"github-elo"),{})
            y=a.get((fid,"callumfm-dixon-coles"),{})
            ok=x.get("status")=="settled" and y.get("status")=="settled" and x.get("actual")==y.get("actual")
            hit=x["actual"]==c["selection"] if ok else None
            probability=c["probability_min"]
        else:
            x=b.get((fid,c["model"],c["market"],c["line"],c["selection"]),{})
            ok=x.get("status")=="settled"
            hit=x["hit"] if ok else None
            probability=c["probability"]
        out.append(dict(variant=c["variant"],fixture_id=fid,market=c["market"],
            probability=probability,status="settled" if ok else "unresolved",hit=hit))
    return out
