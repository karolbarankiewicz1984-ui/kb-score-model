"""Settle frozen experimental predictions against API-Football final regulation scores.
No original KB Score or API Market writes. Requires archived prematch snapshot.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

MARKETS={"over_1_5":lambda h,a:h+a>1,"over_2_5":lambda h,a:h+a>2,
         "over_3_5":lambda h,a:h+a>3,"btts_yes":lambda h,a:h>0 and a>0}
def settle(predictions, fixtures):
    if predictions.get("status")!="EXPERIMENT_ONLY" or predictions.get("register_writes") is not False:
        raise ValueError("not an isolated experimental prediction snapshot")
    by_id={str(x["fixture"]["id"]):x for x in fixtures}
    rows=[]
    for m in predictions.get("matches",[]):
        fid=str(m["fixture_id"])
        f=by_id.get(fid)
        if not f:
            rows.append({"fixture_id":fid,"status":"PENDING","reason":"RESULT_UNAVAILABLE"})
            continue
        status=f.get("fixture",{}).get("status",{}).get("short")
        if status not in ("FT","AET","PEN"):
            rows.append({"fixture_id":fid,"status":"PENDING","reason":"NOT_FINAL_"+str(status)})
            continue
        score=f.get("score",{}).get("fulltime",{})
        h,a=score.get("home"),score.get("away")
        if not all(isinstance(x,int) and not isinstance(x,bool) and x>=0 for x in (h,a)):
            rows.append({"fixture_id":fid,"status":"PENDING","reason":"NO_REGULATION_SCORE"})
            continue
        events=[]
        for market,p in m["markets"].items():
            if market not in MARKETS: continue
            if not isinstance(p,(int,float)) or not 0<=p<=1: raise ValueError("invalid probability")
            hit=bool(MARKETS[market](h,a))
            events.append({"market":market,"probability":p,"occurred":hit,
                           "brier":round((p-int(hit))**2,8),
                           "prediction_hash_source":"frozen_fixture_id_and_snapshot"})
        rows.append({"fixture_id":fid,"status":"SETTLED","home_goals":h,"away_goals":a,
                     "events":events,"snapshot_utc":m["snapshot_utc"]})
    return {"date":predictions["date"],"schema":"experimental-settlement-v1",
            "rows":rows,"register_writes":False,"kb_n_effect":0,"dev_n_effect":0}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("results")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    path=Path(args.output)
    if not str(path).startswith("data/experimental_engine/settlements/"): raise ValueError("isolated output only")
    predictions=json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    raw=json.loads(Path(args.results).read_text(encoding="utf-8"))
    out=settle(predictions,raw.get("response",[]))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(path),"settled":sum(x["status"]=="SETTLED" for x in out["rows"]),
                      "pending":sum(x["status"]=="PENDING" for x in out["rows"])}))
if __name__=="__main__":main()
