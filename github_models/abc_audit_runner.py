"""Daily read-only A/B/C archive audit."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from github_models.abc_settlement import audit
from github_models.abc_metrics import metrics

def run(root, history, events, as_of):
    rows=[]
    archives=0
    for f in sorted((root/"frozen").glob("*/*.json")):
        rel=f.relative_to(root)
        q=root/"queues"/rel.parts[1]/rel.name
        m=root/"markets"/rel.parts[1]/rel.name
        if not q.is_file() or not m.is_file():
            continue
        load=lambda p:json.loads(p.read_text(encoding="utf-8"))
        rows.extend(audit(load(f),load(m),load(q),history,events,as_of))
        archives+=1
    # Repeated snapshots of the same match/line/selection are not independent
    # observations. Retain the earliest archived candidate; fail closed if
    # archived duplicates disagree about the actual outcome.
    unique={}
    duplicates=0
    revisions=0
    outcome_conflicts=0
    for row in rows:
        key=(row["variant"],str(row["fixture_id"]),row["market"],
             row["selection"],row.get("line"))
        if key not in unique:
            unique[key]=dict(row)
            continue
        duplicates+=1
        earlier=unique[key]
        if abs(earlier["probability"]-row["probability"])>1e-9:
            revisions+=1
        if earlier["status"]=="settled" and row["status"]=="settled" and earlier["hit"]!=row["hit"]:
            earlier.update(status="unresolved",hit=None,reason="conflicting_archive_outcomes")
            outcome_conflicts+=1
    groups=defaultdict(list)
    reasons=defaultdict(int)
    for row in unique.values():
        groups[(row["variant"],"all")].append(row)
        groups[(row["variant"],row["market"])].append(row)
        if row["status"]!="settled":
            reasons[row.get("reason") or "unexplained_pending"]+=1
    return dict(schema="abc-audit-v2",as_of_utc=as_of,archives_processed=archives,
        forecast_records=len(rows),unique_candidate_records=len(unique),
        duplicate_snapshots_suppressed=duplicates,probability_revisions_observed=revisions,
        conflicting_archive_outcomes=outcome_conflicts,
        unresolved_reasons=dict(reasons),
        summary=[dict(variant=v,market=m,**metrics(items)) for (v,m),items in sorted(groups.items())],
        calibration="unverified",production_unchanged=True)

def main():
    p=argparse.ArgumentParser()
    for key in ("archive-dir","history","events","as-of","output"):
        p.add_argument("--"+key,required=True)
    a=p.parse_args()
    load=lambda p:json.loads(Path(p).read_text(encoding="utf-8"))
    report=run(Path(a.archive_dir),load(a.history),load(a.events),a.as_of)
    dest=Path(a.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()
