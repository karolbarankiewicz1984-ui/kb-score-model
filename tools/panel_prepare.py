"""Prepare a local bundle from explicitly selected successful GitHub runs.

Uses existing artifacts only, not dispatch or sports provider APIs. Requires
authenticated gh CLI. No upload. Run from repository root.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from github_models.panel_export import build, MAX_BYTES
from tools.panel_publish import check

REPO="karolbarankiewicz1984-ui/kb-score-model"
ROLES={
    "abc":(".github/workflows/github-models-v2-daily-audit.yml", "github-models-v2-abc-complete-"),
    "odds":(".github/workflows/oddspapi-daily.yml","oddspapi-daily"),
    "audit":(".github/workflows/oddspapi-audit.yml","oddspapi-rolling-audit"),
}
def api(path):
    return json.loads(subprocess.check_output(["gh","api",path]))
def select(role, run, artifacts):
    workflow,name=ROLES[role]
    if run.get("path")!=workflow or run.get("head_branch")!="main" or run.get("status")!="completed" or run.get("conclusion")!="success":
        raise ValueError("unverified_source_run:"+role)
    expected=f"{name}{run['id']}-{run['run_attempt']}" if role=="abc" else name
    matches=[a for a in artifacts if a.get("name")==expected and a.get("expired") is False and type(a.get("size_in_bytes")) is int and 0<a["size_in_bytes"]<=MAX_BYTES]
    if len(matches)!=1:
        raise ValueError("missing_or_ambiguous_artifact:"+role)
    return matches[0]
def fetch(role, run_id, path):
    base=f"/repos/{REPO}/actions"
    run=api(f"{base}/runs/{run_id}")
    if run.get("id")!=run_id: raise ValueError("run_id_mismatch")
    listing=api(f"{base}/runs/{run_id}/artifacts?per_page=100")
    if listing["total_count"]!=len(listing["artifacts"]): raise ValueError("artifact_list_incomplete")
    artifact=select(role,run,listing["artifacts"])
    with path.open("wb") as f:
        subprocess.run(["gh","api",f"{base}/artifacts/{artifact['id']}/zip"],stdout=f,check=True)
    if path.stat().st_size>MAX_BYTES: raise ValueError("download_too_large")
    return artifact["id"]
def main():
    p=argparse.ArgumentParser();p.add_argument("--day",required=True)
    for role in ROLES:p.add_argument("--"+role+"-run",required=True,type=int)
    p.add_argument("--out",required=True,type=Path);a=p.parse_args()
    runs={role:getattr(a,role+"_run") for role in ROLES}
    if min(runs.values())<=0:raise ValueError("invalid_run_id")
    with tempfile.TemporaryDirectory() as d:
        paths={role:Path(d)/(role+".zip") for role in ROLES}
        for role in ROLES: print(role,"artifact",fetch(role,runs[role],paths[role]))
        build(paths["abc"],paths["odds"],paths["audit"],a.day,runs,a.out)
        check(a.out)
    print("Local bundle ready; not published.")
if __name__=="__main__":main()
