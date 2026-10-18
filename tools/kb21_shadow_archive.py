"""Append-only GitHub audit archive for independent KB21 shadow experiments.

Writes ONLY data/kb21_shadow_audits/<date>/<run>-attempt<n>.json.
No KB Score main register, old N, odds, API Market or model code may be edited.
When there are no genuine pregame forecasts, nothing is archived.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime

from tools.kb21_shadow_audit import AUDIT_SCHEMA, _iso_datetime

PREFIX = "data/kb21_shadow_audits"
MAX_BYTES = 2_000_000


def prepare(report, run_id, attempt):
    if not isinstance(report, dict) or report.get("schema") != AUDIT_SCHEMA:
        raise ValueError("Only validated KB21 shadow settlement reports can be archived")
    day = report.get("date")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid report date")
    audited = _iso_datetime(report.get("audited_at_utc"))
    if audited is None or audited.date() < date.fromisoformat(day):
        raise ValueError("Invalid audit clock")
    if (report.get("source") != "API-Football result fixtures (same provider IDs)"
            or report.get("model") != "kb21-api-last10-goals-shadow-v1"
            or report.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
            or report.get("old_kb21_n_effect") != 0
            or report.get("register_writes") is not False
            or report.get("safe_to_publish_play") is not False
            or not isinstance(report.get("results"), list)
            or report.get("unique_pregame_predictions") != len(report["results"])
            or isinstance(run_id, bool) or not isinstance(run_id, int)
            or run_id <= 0 or isinstance(attempt, bool) or not isinstance(attempt, int)
            or attempt <= 0):
        raise ValueError("Unsafe, retroactive or improperly labeled audit archive")
    if not report["results"]:
        return None
    seen = set()
    for row in report["results"]:
        fid = row.get("fixture_id") if isinstance(row, dict) else None
        kickoff = _iso_datetime(row.get("kickoff_utc")) if isinstance(row, dict) else None
        freeze = _iso_datetime(row.get("freeze_utc")) if isinstance(row, dict) else None
        if (not isinstance(fid, int) or isinstance(fid, bool) or fid in seen
                or kickoff is None or freeze is None or freeze >= kickoff
                or not isinstance(row.get("snapshot_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["snapshot_sha256"])
                or row.get("status") not in {
                    "UNRESOLVED", "MISSING_FROM_RESULT_SOURCE",
                    "KICKOFF_CHANGED_NOT_SETTLED", "NOT_STANDARD_FULL_TIME",
                    "INCOMPLETE_OR_CONFLICTING_SCORE", "SETTLED_FT",
                }):
            raise ValueError("Unsafe or duplicated pregame audit observation")
        seen.add(fid)
    contents = json.dumps(
        report, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    if len(contents) > MAX_BYTES:
        raise ValueError("Audit output unexpectedly large")
    path = f"{PREFIX}/{day}/{run_id}-attempt{attempt}.json"
    return path, contents


def archive(report, repo, run_id, attempt, gh="gh"):
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("GitHub repository must be explicit owner/name")
    prepared = prepare(report, run_id, attempt)
    if prepared is None:
        return {"status": "NO_PREMATCH_PROBABILITIES_TO_ARCHIVE", "path": None}
    if not os.getenv("GH_TOKEN"):
        raise RuntimeError("GH_TOKEN required for real append-only GitHub archive")
    path, raw = prepared
    url = f"repos/{repo}/contents/{path}"
    # If the exact run+attempt was uploaded already, only identical bytes are
    # acceptable. Never overwrite an earlier audit or tamper with the past.
    old = subprocess.run(
        [gh, "api", url], text=True, capture_output=True
    )
    if old.returncode == 0:
        existing = json.loads(old.stdout)
        blob = base64.b64decode(existing.get("content", "").replace("\n", ""))
        if blob != raw:
            raise ValueError("Conflicting existing append-only audit snapshot")
        return {"status": "ALREADY_ARCHIVED_IDENTICAL", "path": path}
    if "404" not in old.stderr:
        raise RuntimeError("Cannot verify archive destination: " + old.stderr[:350])
    request = {
        "message": "archive(kb21-shadow): independent forward audit " + report["date"],
        "branch": "main",
        "content": base64.b64encode(raw).decode("ascii"),
    }
    subprocess.run([gh, "api", "-X", "PUT", url, "--input", "-"],
                   input=json.dumps(request), text=True,
                   capture_output=True, check=True)
    return {"status": "ARCHIVED_NEW_APPEND_ONLY", "path": path,
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("report")
    a = p.parse_args()
    with open(a.report, encoding="utf-8") as file:
        report = json.load(file)
    result = archive(
        report, os.environ["GITHUB_REPOSITORY"],
        int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"]))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
