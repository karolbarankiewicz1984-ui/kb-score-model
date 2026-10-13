"""Isolated experimental goal-market probabilities; never original KB21 P(model)."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

VERSION = "experimental-goals-v0.1"
def poisson_cdf(k, lam):
    if not isinstance(lam,(int,float)) or isinstance(lam,bool) or not math.isfinite(lam) or not 0 < lam <= 6:
        raise ValueError("goal rate must be finite and in (0,6]")
    return sum(math.exp(-lam)*lam**n/math.factorial(n) for n in range(k+1))

def estimate(home_rate,away_rate):
    if not 0 < home_rate <= 6 or not 0 < away_rate <= 6:
        raise ValueError("rates out of range")
    total=home_rate+away_rate
    return {"over_1_5":round(1-poisson_cdf(1,total),6),
            "over_2_5":round(1-poisson_cdf(2,total),6),
            "over_3_5":round(1-poisson_cdf(3,total),6),
            "btts_yes":round((1-math.exp(-home_rate))*(1-math.exp(-away_rate)),6)}

def run(data):
    if not data.get("date"): raise ValueError("date required")
    output=[]
    for item in data.get("matches",[]):
        if not item.get("fixture_id") or not item.get("kickoff_utc"):
            raise ValueError("fixture_id and kickoff_utc required")
        kickoff=dt.datetime.fromisoformat(item["kickoff_utc"].replace("Z","+00:00"))
        snapshot=dt.datetime.fromisoformat(item["snapshot_utc"].replace("Z","+00:00"))
        if kickoff.tzinfo is None or snapshot.tzinfo is None or snapshot >= kickoff:
            raise ValueError("snapshot must be timezone-aware and before kickoff")
        h=item.get("home_goals_per_match")
        a=item.get("away_goals_per_match")
        if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in (h,a)):
            raise ValueError("missing or non-finite rates")
        output.append({"fixture_id":item["fixture_id"],"kickoff_utc":item["kickoff_utc"],
                       "snapshot_utc":item["snapshot_utc"],"model":VERSION,
                       "rate_type":"historical_goals_proxy_NOT_xG",
                       "markets":estimate(h,a),"decision":"EXPERIMENT_ONLY_NOT_PLAY",
                       "kb_n_effect":0,"dev_n_effect":0})
    return {"date":data["date"],"model":VERSION,"status":"EXPERIMENT_ONLY",
            "matches":output,"register_writes":False,"kb_n_effect":0,"dev_n_effect":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    target=Path(args.output)
    if not str(target).startswith("reports/experimental_engine/"):
        raise ValueError("outputs must be under reports/experimental_engine/")
    result=run(json.loads(Path(args.input).read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
