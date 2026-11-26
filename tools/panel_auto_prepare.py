"""Select a same-day frozen bundle using ONLY existing successful Actions artifacts.

Run on a trusted operator machine/private CI. No provider requests, dispatch,
fallback to stale forecasts or publication. Publication remains a separate step.
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from github_models.panel_export import build, decode, inspect_zip, stamp
from tools.panel_prepare import REPO, ROLES, api, fetch
from tools.panel_publish import check

WARSAW = ZoneInfo("Europe/Warsaw")
LIMIT = 10

def recent(role):
    workflow = ROLES[role][0].rsplit("/", 1)[1]
    data = api(f"/repos/{REPO}/actions/workflows/{workflow}/runs?branch=main&status=success&per_page={LIMIT}")
    runs = data["workflow_runs"]
    if len(runs) > LIMIT:
        raise ValueError("run_limit")
    for run in runs:
        if (run.get("path") != ROLES[role][0] or run.get("head_branch") != "main"
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or type(run.get("id")) is not int or run["id"] <= 0):
            raise ValueError("invalid_run_metadata")
    return sorted(runs, key=lambda r: (stamp(r["created_at"]), r["id"]), reverse=True)

def member(path, name):
    with ZipFile(path) as z:
        inspect_zip(z)
        return z.read(name) if name in z.namelist() else None

def prepare(out, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(WARSAW).date().isoformat()
    odds, abc, audit = (recent(role) for role in ("odds", "abc", "audit"))
    if not odds or not abc or not audit:
        raise ValueError("missing_successful_runs")
    with tempfile.TemporaryDirectory() as d:
        paths = {role: Path(d) / (role + ".zip") for role in ROLES}
        ids = {"odds": odds[0]["id"], "audit": audit[0]["id"]}
        fetch("odds", ids["odds"], paths["odds"])
        raw = member(paths["odds"], "pitch_queue.json")
        if raw is None:
            raise ValueError("missing_odds_queue")
        cutoff = stamp(decode(raw)["generated_at_utc"])
        if cutoff > now or cutoff.astimezone(WARSAW).date().isoformat() != day:
            raise ValueError("no_current_warsaw_day_odds")
        name = f"reports/github_models/queues/{day}.json"
        for run in abc:
            fetch("abc", run["id"], paths["abc"])
            if member(paths["abc"], name) == raw:
                ids["abc"] = run["id"]
                break
        else:
            raise ValueError("no_exact_abc_queue_match")
        fetch("audit", ids["audit"], paths["audit"])
        candidate = Path(d) / "candidate.zip"
        build(paths["abc"], paths["odds"], paths["audit"], day, ids, candidate)
        manifest = check(candidate)
        audit_at = stamp(manifest["audit_as_of_utc"])
        if not now - timedelta(hours=48) <= audit_at <= now:
            raise ValueError("audit_not_recent")
        # Refuse to overwrite even a local output; publish only after validation.
        with candidate.open("rb") as src, Path(out).open("xb") as dst:
            import shutil
            shutil.copyfileobj(src, dst)
    return ids

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    ids = prepare(a.out)
    print("Validated current Warsaw-day snapshot; not published. Source run IDs:", ids)

if __name__ == "__main__":
    main()
