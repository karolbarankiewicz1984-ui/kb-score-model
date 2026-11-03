"""Offline gate for optional upload. Capture completeness is not source readiness."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile

from .capture import _redact, read_provider_capture
from .full_pool import read_full_pool
from .planner import plan_report_dates, report_deadline
from .producer import SCHEMA, digest, immutable_json
from .source_manifest import instant

STAGES = ("prefetch", "scan", "enrich", "publish", "playable", "freeze", "pdf", "status")
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 1000


def inspect_bundle(root, *, start_date, as_of, source, recorder_sha):
    root = Path(root).resolve()
    dates = plan_report_dates(start_date)
    errors, strict, inventory, summaries, pools, raw = [], [], [], {}, {}, {}
    if not root.is_dir():
        errors.append("bundle_missing")
    paths = sorted(root.rglob("*")) if root.is_dir() else []
    files = [p for p in paths if p.is_file()]
    if len(files) > MAX_FILES or sum(p.stat().st_size for p in files) > MAX_BYTES:
        return {"status": "SOURCE_BLOCKED", "errors": ["bundle_size_limit"], "source_ready": False}
    for path in paths:
        relative = str(path.relative_to(root))
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append("bundle_symlink_or_escape")
            continue
        if not path.is_file():
            continue
        content = path.read_bytes()
        inventory.append({"path": relative, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        if path.suffix != ".json":
            if path.suffix != ".pdf" or not relative.startswith("native/"):
                errors.append("unexpected_bundle_file:" + relative)
            continue
        try:
            value = json.loads(content)
            if _redact(value) != value:
                raise ValueError("bundle_unredacted_secret")
            if relative.startswith("raw/"):
                value = read_provider_capture(path, as_of=as_of)
                if value["source"] != {k: source[k] for k in value["source"]}:
                    raise ValueError("bundle_raw_source_mismatch")
                if isinstance(value["response"], dict) and value["response"].get("errors"):
                    raise ValueError("provider_errors_recorded")
                raw[value["integrity"]["sha256"]] = value
            elif relative.startswith("full_pool/"):
                value = read_full_pool(path, as_of=as_of)
                if any(value["source"].get(k) != v for k, v in source.items()):
                    raise ValueError("bundle_pool_source_mismatch")
                if value["date"] not in dates or value["date"] in pools:
                    raise ValueError("bundle_duplicate_or_unexpected_pool_date")
                if not value["verification"]["full_pool_complete"]:
                    raise ValueError("bundle_incomplete_native_pool")
                if value["capture_mode"] != "forward" or value["candidate_decisions"] is None:
                    raise ValueError("bundle_forward_decisions_missing")
                if instant(value["recorded_at_utc"]) > instant(report_deadline(start_date)):
                    raise ValueError("bundle_after_report_cutoff")
                pools[value["date"]] = (relative, value)
                strict.extend(value["verification"]["blockers"])
            elif relative.startswith("producer/"):
                if (value.get("schema") != SCHEMA or value.get("sha256") != digest({k: v for k, v in value.items() if k != "sha256"})
                        or value.get("source") != source or value.get("recorder_sha") != recorder_sha):
                    raise ValueError("bundle_stage_digest_or_revision_mismatch")
                if value["date"] not in dates or value["stage"] not in STAGES:
                    raise ValueError("bundle_unexpected_stage")
                key = (value["date"], value["stage"])
                if key in summaries:
                    raise ValueError("bundle_duplicate_stage")
                if value["status"] != "CAPTURED" or value["native_ok"] is not True or value["errors"]:
                    raise ValueError("bundle_stage_failed")
                if relative != f"producer/{value['date']}/{value['stage']}.json":
                    raise ValueError("bundle_stage_path_mismatch")
                if any(not isinstance(value.get(k), list) or any(not isinstance(p, str) for p in value[k])
                       for k in ("raw_receipts", "full_pool", "outputs")):
                    raise ValueError("bundle_stage_file_lists_invalid")
                if (not isinstance(value.get("output_sha256"), dict)
                        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value["output_sha256"].items())
                        or type(value.get("api_calls")) is not int or value["api_calls"] < 0):
                    raise ValueError("bundle_stage_counts_or_hashes_invalid")
                if not instant(value["started_at"]) <= instant(value["completed_at"]) <= instant(as_of):
                    raise ValueError("bundle_stage_time_invalid")
                summaries[key] = (relative, value)
            elif relative.startswith("multiday_status/"):
                if (value.get("date") not in dates or relative != f"multiday_status/{value['date']}.json"
                        or value.get("status") != "ok"):
                    raise ValueError("native_day_status_incomplete")
            elif not relative.startswith("native/"):
                raise ValueError("unexpected_bundle_json")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(relative + ":" + str(exc))
    available = {x["path"] for x in inventory}
    hashes = {x["path"]: x["sha256"] for x in inventory}
    claimed = set()
    for day in dates:
        previous_end = None
        for stage in STAGES:
            entry = summaries.get((day, stage))
            if entry is None:
                errors.append(f"missing_stage:{day}:{stage}")
                continue
            name, summary = entry
            claimed.add(name)
            if previous_end is not None and instant(summary["started_at"]) < previous_end:
                errors.append("stage_order_mismatch:" + day)
            previous_end = instant(summary["completed_at"])
            if previous_end > instant(report_deadline(start_date)):
                errors.append("native_output_after_report_cutoff:" + name)
            for key in ("raw_receipts", "full_pool", "outputs"):
                for item in summary[key]:
                    if item not in available:
                        errors.append("missing_stage_file:" + item)
                    claimed.add(item)
            if set(summary["output_sha256"]) != set(summary["outputs"]) or any(
                    hashes.get(item) != sha for item, sha in summary["output_sha256"].items()):
                errors.append("native_output_digest_mismatch:" + name)
            if summary["api_calls"] != len(summary["raw_receipts"]):
                errors.append("raw_call_count_mismatch:" + name)
            if stage == "publish" and (day not in pools or summary["full_pool"] != [pools[day][0]]):
                errors.append("missing_published_full_pool:" + day)
            if stage not in ("prefetch",) and not summary["outputs"]:
                errors.append("missing_native_output:" + name)
        if day not in pools:
            errors.append("missing_native_pool:" + day)
            continue
        refs = pools[day][1]["source"].get("raw_quote_receipts") or []
        if not isinstance(refs, list) or any(not isinstance(r, dict) for r in refs):
            errors.append("raw_pool_references_invalid:" + day)
            refs = []
        if not refs or not any(r.get("endpoint") == "odds" for r in refs):
            # A genuinely empty scan can have no odds call. Distinguish it
            # from a nonempty candidate pool lacking quote receipts.
            if pools[day][1]["native_payload"]["background_candidates"]:
                errors.append("missing_original_odds_receipt:" + day)
        for ref in refs:
            receipt = raw.get(ref.get("envelope_sha256", ref.get("capture_sha256")))
            if (receipt is None or receipt["integrity"]["response_sha256"] != ref.get("response_sha256")
                    or receipt["received_at"] != ref.get("received_at")):
                errors.append("raw_pool_binding_mismatch:" + day)
    if available - claimed:
        errors.append("unclaimed_bundle_files")
    return {"schema": "multimodel-v2-upload-check-v1", "status": "SOURCE_BLOCKED" if errors else "CAPTURE_COMPLETE",
        "capture_complete": not errors, "source_ready": not errors and not strict,
        "dates": dates, "source": source, "recorder_sha": recorder_sha,
        "errors": sorted(set(errors)), "source_blockers": sorted(set(strict)),
        "files": inventory, "n_effect": 0, "full_shadow_passed": False}


def prepare_upload(root, *, enabled=False, **kwargs):
    if not enabled:
        return {"status": "DISABLED", "upload": False, "n_effect": 0}
    result = inspect_bundle(root, **kwargs)
    # A blocked source is useful technical evidence, but never a qualified
    # source. Preserve this distinction in the uploaded external manifest.
    result["upload"] = result.get("capture_complete", False)
    return result


def inspect_uploaded_bundle(archive, *, start_date, as_of, source, recorder_sha):
    """Recheck downloaded bytes from artifact_audit.read_artifact, same version.

    No unchecked ZIP extraction and no trusted COMPLETE flag. The expected
    recorder revision is supplied by the reviewer, never taken from the bundle.
    """
    from .repair_pipeline import _checked_files
    run = archive["run"]
    if (archive["artifact"].get("name") != "multimodel-v2-full-source"
            or str(run["id"]) != str(source["run_id"]) or run["head_sha"] != source["workflow_head_sha"]):
        raise ValueError("uploaded_bundle_run_mismatch")
    files = _checked_files(archive, run)
    if len(files) > MAX_FILES or sum(len(v) for v in files.values()) > MAX_BYTES:
        raise ValueError("uploaded_bundle_size_limit")
    with tempfile.TemporaryDirectory(prefix="multimodel-consumer-") as temporary:
        root = Path(temporary)
        for name, content in files.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name:
                raise ValueError("unsafe_uploaded_bundle_member")
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return inspect_bundle(root, start_date=start_date, as_of=as_of, source=source, recorder_sha=recorder_sha)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--recorder-sha", required=True)
    parser.add_argument("--enabled", action="store_true")
    args = parser.parse_args(argv)
    if args.manifest.resolve().is_relative_to(args.root.resolve()):
        parser.error("manifest_must_be_outside_bundle")
    result = prepare_upload(args.root, enabled=args.enabled, start_date=args.start_date,
        as_of=args.as_of, source=json.loads(args.source.read_text()), recorder_sha=args.recorder_sha)
    immutable_json(args.manifest.parent, args.manifest.name, result)
    print(json.dumps({k: result[k] for k in ("status", "upload")}))
    return 0 if result["upload"] or result["status"] == "DISABLED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
