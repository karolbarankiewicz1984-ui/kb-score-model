"""Audit completeness of KB21 candidate inputs without creating PLAY or register rows."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

FIELDS=("structural_0_100","quality_0_100","matchup_0_100","home_expected_goals","away_expected_goals")
def assess(record):
    reasons=[]
    if not record.get("fixture_verified_official"): reasons.append("OFFICIAL_FIXTURE_UNVERIFIED")
    if not record.get("fixture_verified_independent"): reasons.append("INDEPENDENT_FIXTURE_UNVERIFIED")
    sources=record.get("sources") or []
    if len(set(sources))<2: reasons.append("SOURCE_PROVENANCE_INSUFFICIENT")
    for name in FIELDS:
        v=record.get(name)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            reasons.append("MISSING_"+name.upper())
        elif not (0<=v<=100 if name.endswith("_0_100") else .05<=v<=6):
            reasons.append("OUT_OF_RANGE_"+name.upper())
    rates=record.get("api_goal_rates") or {}
    for side in ("home","away"):
        if not isinstance(rates.get(side),dict) or rates[side].get("sample_size",0)<5:
            reasons.append("GOAL_HISTORY_INSUFFICIENT_"+side.upper())
    return {"fixture_id":record.get("fixture_id"),"event":record.get("event"),
            "ready_for_review":not reasons,"blocking_reasons":reasons,
            "freeze_allowed":False,"kb_status":"NOT_ASSIGNED"}

def audit(data):
    rows=[assess(r) for r in data.get("candidates",[])]
    ready=sum(x["ready_for_review"] for x in rows)
    reason_counts={}
    for row in rows:
        for reason in row["blocking_reasons"]:
            reason_counts[reason]=reason_counts.get(reason,0)+1
    return {"date":data.get("date"),"status":"GATE_AUDIT_ONLY",
            "total":len(rows),"ready_for_review":ready,
            "blocked":len(rows)-ready,"blocker_counts":dict(sorted(reason_counts.items())),
            "rows":rows,
            "calendar_gate":"UNVERIFIED" if data.get("calendar_gate")!="VERIFIED" else "REVIEW_REQUIRED",
            "kb_n_effect":0,"dev_n_effect":0,"register_writes":False,
            "note":"Passing this input audit alone never authorizes PLAY or an original KB21 P(model)."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output")
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    report=audit(data)
    out=Path(args.output) if args.output else Path("reports/kb21_gate")/(str(report["date"])+".json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(out),"total":report["total"],"blocked":report["blocked"],"ready_for_review":report["ready_for_review"]}))

if __name__=="__main__":main()
