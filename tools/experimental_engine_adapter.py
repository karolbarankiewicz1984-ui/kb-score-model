"""Convert factual API-Football KB21-style candidate snapshots into isolated experimental inputs.
No KB21 model calculations or writes are performed.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from tools.experimental_engine_goals import run

def transform(source):
    matches=[]
    excluded=[]
    for row in source.get("candidates",[]):
        fid=row.get("fixture_id")
        rates=row.get("api_goal_rates") or {}
        h=rates.get("home") or {}
        a=rates.get("away") or {}
        if min(h.get("sample_size",0),a.get("sample_size",0))<5:
            excluded.append({"fixture_id":fid,"reason":"INSUFFICIENT_HISTORY"})
            continue
        vals=[h.get("goals_for_per_match"),h.get("goals_against_per_match"),
              a.get("goals_for_per_match"),a.get("goals_against_per_match")]
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or v<0 for v in vals):
            excluded.append({"fixture_id":fid,"reason":"INVALID_GOAL_HISTORY"})
            continue
        matches.append({"fixture_id":fid,"kickoff_utc":row.get("kickoff_utc"),
                        "snapshot_utc":row.get("snapshot_utc") or source.get("snapshot_utc"),
                        "home_goals_per_match":max(.05,(vals[0]+vals[3])/2),
                        "away_goals_per_match":max(.05,(vals[2]+vals[1])/2)})
    return {"date":source["date"],"matches":matches},excluded

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    target=Path(a.output)
    if not str(target).startswith("reports/experimental_engine/"):
        raise ValueError("output must be isolated under reports/experimental_engine/")
    source=json.loads(Path(a.input).read_text(encoding="utf-8"))
    transformed,excluded=transform(source)
    result=run(transformed)
    result["excluded"]=excluded
    result["source"]="API-Football historical completed fixtures, captured pre-match"
    result["source_snapshot_utc"]=source.get("snapshot_utc")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(target),"matches":len(result["matches"]),"excluded":len(excluded)}))

if __name__=="__main__": main()
