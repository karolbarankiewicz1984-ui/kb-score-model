"""Read-only API pre-match diagnostic. NOT historical KB Score P(model)."""
import argparse
import json
import math
from pathlib import Path

def diagnose(row):
    rates=row.get("api_goal_rates") or {}
    h=rates.get("home") or {}
    a=rates.get("away") or {}
    if min(h.get("sample_size",0),a.get("sample_size",0))<5:
        return {"status":"INSUFFICIENT_HISTORY","p_model":None}
    values=[h.get("goals_for_per_match"),h.get("goals_against_per_match"),
            a.get("goals_for_per_match"),a.get("goals_against_per_match")]
    if any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in values):
        return {"status":"INVALID_HISTORY","p_model":None}
    # Transparent exploratory estimate: blended team attack and opponent defence.
    # Not xG; do not feed this to KB21 engine as xG or historical P(model).
    home_rate=max(.05,(values[0]+values[3])/2)
    away_rate=max(.05,(values[2]+values[1])/2)
    def pmf(lam,k):
        return math.exp(-lam+k*math.log(lam)-math.lgamma(k+1))
    home=[pmf(home_rate,k) for k in range(24)]
    away=[pmf(away_rate,k) for k in range(24)]
    ph=sum(home[i]*away[j] for i in range(24) for j in range(i))
    pd=sum(home[i]*away[i] for i in range(24))
    pa=sum(home[i]*away[j] for i in range(24) for j in range(i+1,24))
    return {"status":"EXPLORATORY_API_ONLY","p_model":None,
            "diagnostic_probabilities":{"home":round(ph,5),"draw":round(pd,5),"away":round(pa,5),
              "over_2_5":round(1-math.exp(-(home_rate+away_rate))*(1+home_rate+away_rate+(home_rate+away_rate)**2/2),5)},
            "goal_rate_estimates":{"home":round(home_rate,4),"away":round(away_rate,4)},
            "limitations":"Last-10 goals proxy, no xG/ELO/lineup/league-strength; no PLAY, LEARN, CONTROL, freeze or N."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output")
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows=[{"event":x.get("event"),"fixture_id":x.get("fixture_id"),"league":x.get("league"),
           "kickoff_utc":x.get("kickoff_utc"),**diagnose(x)} for x in data["candidates"]]
    out={"date":data["date"],"status":"DIAGNOSTIC_ONLY","rows":rows,
         "kb_n_effect":0,"dev_n_effect":0,"register_writes":False}
    target=Path(args.output) if args.output else Path("reports/kb21_diagnostic")/(data["date"]+".json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(target),"rows":len(rows),"diagnostic_ready":sum(x["status"]=="EXPLORATORY_API_ONLY" for x in rows),
        "kb_n_effect":0,"dev_n_effect":0}))

if __name__=="__main__":main()
