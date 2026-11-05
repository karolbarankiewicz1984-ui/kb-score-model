"""Bind an existing native publication to Git/run/log evidence, read only.

Git-persisted output is distinct from an Actions upload artifact. No network,
checkout, commit, scanner, price reconstruction or archive writes occur here.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re
import subprocess

from .source_manifest import instant, local_day

WORKFLOW = ".github/workflows/api-market-scan.yml"
BINDING_FIELDS = {"run_id", "head_sha", "source_kind", "source_ref"}


def payload_digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def normalized_payload(payload):
    result = deepcopy(payload)
    for field in ("background_candidates", "top_positions"):
        for row in result.get(field, []):
            if row.get("market_scope") == "match":
                row["team_id"] = None
    return result


def _runtime_lines(log):
    result = []
    for line in log.splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        try:
            stamp = instant(parts[0])
        except ValueError:
            continue
        # Workflow source echoed in a group is never execution evidence.
        if parts[1].lstrip().startswith(("echo ", "printf ", "##[command]", "##[group]")):
            continue
        result.append((stamp, parts[1], line))
    return result


def validate_receipt(receipt, run, *, payload=None):
    """Validate supplied observed metadata; hashes do not replace its origin."""
    if (receipt.get("schema") != "multimodel-v2-git-publication-v1"
            or receipt.get("source_kind") != "git_publication"
            or run.get("path") != WORKFLOW
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or str(receipt.get("run_id")) != str(run.get("id"))
            or receipt.get("run_head_sha") != run.get("head_sha")):
        raise ValueError("git_run_binding_mismatch")
    for field in ("publish_commit", "parent_commit", "blob_oid"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get(field))):
            raise ValueError("invalid_git_object")
    if receipt["parent_commit"] != run["head_sha"]:
        raise ValueError("git_parent_not_run_head")
    day = local_day(receipt.get("date")).isoformat()
    publication_id = receipt.get("publication_id")
    if not isinstance(publication_id, str) or not re.fullmatch(r"[0-9]+-[0-9a-f]+", publication_id):
        raise ValueError("invalid_native_publication_id")
    path = f"data/api_football/predictions/{day}/{publication_id}.json"
    if receipt.get("path") != path or receipt.get("source_ref") != f"git:{receipt['publish_commit']}:{path}":
        raise ValueError("git_source_path_mismatch")
    for field in ("capture_sha256", "native_payload_sha256", "normalized_payload_sha256", "job_log_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(field))):
            raise ValueError("invalid_git_evidence_hash")
    start, end = instant(run.get("run_started_at")), instant(run.get("updated_at"))
    generated, captured, committed = [instant(receipt.get(k)) for k in (
        "generated_at_utc", "captured_at_utc", "committed_at")]
    if not start <= generated <= captured <= committed <= end:
        raise ValueError("git_publication_outside_run")
    job = receipt.get("job") or {}
    if (str(job.get("run_id")) != str(run["id"]) or not job.get("id")
            or job.get("status") != "completed" or job.get("conclusion") != "success"):
        raise ValueError("git_job_mismatch")
    steps = {s.get("name"): s.get("conclusion") for s in job.get("steps", [])}
    if any(steps.get(n) != "success" for n in (
            "Freeze and publish unlimited API ranking", "Commit scan output, data cache and PDF")):
        raise ValueError("git_publication_step_not_successful")
    proof = _runtime_lines("\n".join(receipt.get("proof_lines", [])))
    if len(proof) != 4 or any(not start <= t <= end for t, _, _ in proof):
        raise ValueError("git_runtime_proof_missing")
    summary = []
    for stamp, body, _ in proof:
        try:
            data = json.loads(body)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("prediction_id") == publication_id:
            summary.append((stamp, data))
    if len(summary) != 1 or summary[0][1] != receipt.get("native_summary"):
        raise ValueError("git_publication_summary_mismatch")
    short = receipt["publish_commit"][:7]
    bodies = [body for _, body, _ in proof]
    if (not any(re.fullmatch(r"\[[^\] ]+ " + short + r"\] report: API Market Scan v3", b) for b in bodies)
            or not any(b.strip() == "create mode 100644 " + path for b in bodies)
            or not any(re.fullmatch(r"\s*" + run["head_sha"][:7] + r"\.\." + short + r"\s+HEAD -> [^ ]+", b) for b in bodies)):
        raise ValueError("git_publish_log_mismatch")
    if payload is not None:
        native = {k: v for k, v in payload.items() if k not in BINDING_FIELDS}
        if payload_digest(native) != receipt["normalized_payload_sha256"]:
            raise ValueError("git_snapshot_payload_mismatch")
        pub = native.get("publication") or {}
        if (pub.get("id") != publication_id or pub.get("code_revision") != run["head_sha"]
                or pub.get("provenance") != "live_pre_match"
                or pub.get("captured_at_utc") != receipt["captured_at_utc"]
                or native.get("date") != day or native.get("generated_at_utc") != receipt["generated_at_utc"]):
            raise ValueError("git_native_publication_mismatch")
        observed = summary[0][1]
        if (observed.get("background") != len(native.get("background_candidates", []))
                or observed.get("published") != len(native.get("top_positions", []))
                or observed.get("date") != day):
            raise ValueError("git_native_counts_mismatch")
    return receipt["source_ref"]


def read_git_publication(repo, capture, run, job, log, publish_commit):
    """Verify immutable Git blob bytes against a retrieved job and native ID.

    Requires the historical commit to be present locally. Never fetches it or
    infers a binding from SHA/time proximity alone.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", str(publish_commit)):
        raise ValueError("invalid_publish_commit")
    pub = capture["payload"].get("publication") or {}
    day = local_day(capture["payload"].get("date")).isoformat()
    native_id = pub.get("id")
    if not isinstance(native_id, str) or not re.fullmatch(r"[0-9]+-[0-9a-f]+", native_id):
        raise ValueError("invalid_native_publication_id")
    path = str(PurePosixPath("data/api_football/predictions") / day / (native_id + ".json"))
    def git(*args):
        return subprocess.run(["git", "--no-pager", "-C", str(repo), *args],
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    raw = git("cat-file", "blob", publish_commit + ":" + path)
    if hashlib.sha256(raw).hexdigest() != capture["capture_sha256"] or json.loads(raw) != capture["payload"]:
        raise ValueError("git_blob_capture_mismatch")
    sha, parents, committed = git("show", "-s", "--format=%H%n%P%n%cI", publish_commit).decode().strip().splitlines()
    if len(parents.split()) != 1:
        raise ValueError("git_publication_parent_ambiguous")
    lines = _runtime_lines(log)
    proof = []
    summary = None
    for _, body, line in lines:
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("prediction_id") == native_id:
            summary = data
            proof.append(line)
        elif (re.fullmatch(r"\[[^\] ]+ " + sha[:7] + r"\] report: API Market Scan v3", body)
              or body.strip() == "create mode 100644 " + path
              or re.fullmatch(r"\s*" + parents[:7] + r"\.\." + sha[:7] + r"\s+HEAD -> [^ ]+", body)):
            proof.append(line)
    receipt = {"schema": "multimodel-v2-git-publication-v1", "source_kind": "git_publication",
               "source_ref": f"git:{sha}:{path}", "run_id": run["id"], "run_head_sha": run["head_sha"],
               "job": {k: deepcopy(job.get(k)) for k in ("id", "run_id", "status", "conclusion", "steps")},
               "publish_commit": sha, "parent_commit": parents, "committed_at": committed,
               "blob_oid": git("rev-parse", publish_commit + ":" + path).decode().strip(),
               "path": path, "date": day, "publication_id": native_id,
               "generated_at_utc": capture["payload"].get("generated_at_utc"),
               "captured_at_utc": pub.get("captured_at_utc"),
               "capture_sha256": capture["capture_sha256"],
               "native_payload_sha256": payload_digest(capture["payload"]),
               "normalized_payload_sha256": payload_digest(normalized_payload(capture["payload"])),
               "job_log_sha256": hashlib.sha256(log.encode()).hexdigest(),
               "native_summary": summary, "proof_lines": proof}
    validate_receipt(receipt, run, payload=normalized_payload(capture["payload"]))
    return receipt
