"""Shared qualification of the four isolated repairs, without source calls.

Only full native capsules actually present in a verified artifact can qualify
the API planner. Register rows are never promoted to formal picks. Readiness
for a replay is distinct from a completed mathematical shadow or a new pick.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .adapters import adapt_pitchapi, load_json, match_pitchapi
from .artifact_audit import read_artifact
from .capture import SCHEMA as RAW_SCHEMA, verify_provider_capture
from .formal_freeze import inspect_historical_register, read_forward_freeze, verify_formal_freeze
from .full_pool import SCHEMA as POOL_SCHEMA, verify_full_pool
from .planner import plan_report_dates, report_deadline, validate_three_day_sources
from .settlement import build_native_settlements
from .source_manifest import instant, market_identity


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_files(archive, run):
    artifact, manifest = archive["artifact"], archive["manifest"]
    origin = artifact.get("workflow_run") or {}
    if (manifest.get("digest_verified") is not True
            or artifact.get("expired") is not False
            or str(origin.get("id")) != str(run.get("id"))
            or origin.get("head_sha") != run.get("head_sha")
            or artifact.get("digest") != "sha256:" + str(manifest.get("zip_sha256"))):
        raise ValueError("unverified_artifact_transport")
    entries = {e["path"]: e for e in manifest["entries"]}
    if len(entries) != len(manifest["entries"]) or set(entries) != set(archive["files"]):
        raise ValueError("artifact_member_inventory_mismatch")
    for name, raw in archive["files"].items():
        if entries[name]["sha256"] != _digest(raw) or entries[name]["size"] != len(raw):
            raise ValueError("artifact_member_changed_after_verification")
    return archive["files"]


def _fact(row):
    def name(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("fixture_names_missing")
        return unicodedata.normalize("NFC", value).strip().casefold()
    return name(row.get("home")), name(row.get("away")), instant(row.get("kickoff"))


def _formal_summary(result):
    return {k: deepcopy(v) for k, v in result.items() if k not in (
        "original_rows", "original_payload", "verified_picks", "current_formal_picks")}


def assess_repair_sources(start_date, run, jobs, archives, formal_captures, pitch_captures, *,
                          as_of, checkout_sha, scheduled_date=None, cron_slot=None,
                          event_name=None, job_log="", outcomes=None):
    """archives are read_artifact results; native capsules live in full_pool/.

    formal_captures maps kb21/consensus to original capture wrappers. Existing
    Sheets captures are accepted only as explicitly blocked historical reads.
    No supplied boolean bypasses a capsule digest, row or original-time check.
    """
    dates = plan_report_dates(start_date)
    outcomes = [] if outcomes is None else outcomes
    cutoff = report_deadline(start_date)
    instant(as_of)
    if (not isinstance(archives, list) or not isinstance(formal_captures, dict)
            or not isinstance(pitch_captures, list)
            or any(not isinstance(formal_captures.get(s, []), list) for s in ("kb21", "consensus"))):
        raise ValueError("repair_source_lists_required")
    artifacts, statuses, capsules, issues = [], {}, [], []
    raw_receipts = {}
    for archive in archives:
        try:
            files = _checked_files(archive, run)
            artifacts.append(deepcopy(archive["artifact"]))
            for name, raw in files.items():
                status_match = re.fullmatch(r"multiday_status/(\d{4}-\d{2}-\d{2})\.json", name)
                if status_match:
                    statuses.setdefault(status_match[1], []).append(json.loads(raw))
                pool_match = re.fullmatch(r"full_pool/(\d{4}-\d{2}-\d{2})/[^/]+\.json", name)
                if pool_match:
                    envelope = json.loads(raw)
                    if not isinstance(envelope, dict) or envelope.get("schema") != POOL_SCHEMA or envelope.get("date") != pool_match[1]:
                        raise ValueError("full_pool_member_date_or_schema_mismatch")
                    verified = verify_full_pool(envelope, as_of=as_of)
                    source = envelope["source"]
                    if (str(source.get("run_id")) != str(run.get("id"))
                            or source.get("workflow_head_sha") != run.get("head_sha")
                            or source.get("code_checkout_sha") != checkout_sha
                            or source.get("workflow_path") != run.get("path")):
                        raise ValueError("full_pool_transport_lineage_mismatch")
                    capsules.append({"envelope": envelope, "verified": verified,
                                     "artifact": archive["artifact"], "member_sha256": _digest(raw)})
                if re.fullmatch(r"raw/\d{4}-\d{2}-\d{2}/[^/]+\.json", name):
                    receipt = verify_provider_capture(json.loads(raw), as_of=as_of)
                    raw_receipts.setdefault(receipt["integrity"]["sha256"], []).append(receipt)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            issues.append(str(exc))
    evidence, by_date = [], {}
    for capsule in capsules:
        envelope, verified = capsule["envelope"], capsule["verified"]
        native, artifact = envelope["native_payload"], capsule["artifact"]
        for reference in envelope["source"].get("raw_quote_receipts") or []:
            matched = raw_receipts.get(reference.get("envelope_sha256", reference.get("capture_sha256")), [])
            if len(matched) != 1:
                issues.append("raw_quote_receipt_missing_or_ambiguous")
                continue
            receipt = matched[0]
            if (reference.get("response_sha256") != receipt["integrity"]["response_sha256"]
                    or instant(reference.get("received_at")) != instant(receipt["received_at"])
                    or str(receipt["source"]["run_id"]) != str(envelope["source"]["run_id"])
                    or receipt["source"]["workflow_head_sha"] != envelope["source"]["workflow_head_sha"]
                    or receipt["source"]["code_checkout_sha"] != checkout_sha
                    or any(k in reference and reference[k] != receipt[k] for k in ("provider", "endpoint"))):
                issues.append("raw_quote_receipt_binding_mismatch")
        day = envelope["date"]
        copies = statuses.get(day, [])
        status = copies[0] if copies and len({json.dumps(c, sort_keys=True) for c in copies}) == 1 else None
        rows = []
        for original in native["background_candidates"]:
            row = deepcopy(original)
            if row.get("market_scope") == "match":
                row["team_id"] = None
            market = row.get("market_data")
            if isinstance(market, dict) and "quotes" in market:
                row["quotes"] = deepcopy(market["quotes"])
            rows.append(row)
        evidence.append({"date": day, "file_date": day, "status": status,
            "run_id": envelope["source"]["run_id"], "head_sha": envelope["source"]["workflow_head_sha"],
            "code_sha": envelope["source"]["code_checkout_sha"], "artifact_name": artifact["name"],
            "artifact_digest": artifact["digest"], "digest_verified": True,
            "generated_at_utc": native.get("generated_at_utc"), "publication": deepcopy(native.get("publication")),
            "full_pool_complete": verified["source_eligible"], "candidate_count": len(rows), "rows": rows})
        by_date.setdefault(day, []).append(capsule)
    plan = validate_three_day_sources(start_date, run, jobs, {"artifacts": artifacts}, evidence, as_of=as_of,
            scheduled_date=scheduled_date, cron_slot=cron_slot, checkout_sha=checkout_sha,
            event_name=event_name, job_log=job_log)
    pitch = []
    for capture in pitch_captures:
        try:
            if not isinstance(capture, dict) or not isinstance(capture.get("payload"), dict):
                raise ValueError("pitch_capture_wrapper_invalid")
            pitch.append(adapt_pitchapi(capture))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            issues.append("pitch:" + str(exc))
    reports = []
    for day in dates:
        original_pool = by_date.get(day, [])
        capsule = original_pool[0] if len(original_pool) == 1 else None
        native = capsule["envelope"]["native_payload"] if capsule else None
        source_rows = native["background_candidates"] if native else []
        formal, verified_formal = {}, {}
        for system in ("kb21", "consensus"):
            captures = formal_captures.get(system, [])
            captures = [c for c in captures if isinstance(c, dict) and isinstance(c.get("payload"), dict)]
            matching = [c for c in captures if c.get("payload", {}).get("system") == system
                        and c["payload"].get("date") == day]
            if len(matching) == 1:
                result = verify_formal_freeze(matching[0], report_date=day, as_of=as_of,
                                              system=system, report_cutoff=cutoff)
                verified_formal[system] = result
            elif matching:
                result = {"status": "SOURCE_BLOCKED", "missing_fields": [],
                          "rejections": [{"reason": "ambiguous_native_formal_publication"}]}
            else:
                registers = [c for c in captures if "metadata" in c.get("payload", {})]
                if len(registers) == 1:
                    try:
                        result = inspect_historical_register(registers[0], system, report_date=day, as_of=as_of)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        result = {"status": "SOURCE_BLOCKED", "missing_fields": ["valid_register_capture"],
                                  "rejections": [{"reason": str(exc)}]}
                else:
                    result = {"status": "SOURCE_BLOCKED", "missing_fields": ["original_formal_publication"],
                              "rejections": [{"reason": "native_formal_publication_missing"}]}
            formal[system] = _formal_summary(result)
        common, comparison_issues, required_fixtures = [], [], []
        if native and all(verified_formal.get(s, {}).get("status") == "READY" for s in ("kb21", "consensus")):
            formal_rows = {s: verified_formal[s]["verified_picks"] for s in ("kb21", "consensus")}
            api_cutoff = instant(native["publication"]["captured_at_utc"])
            context_cutoff = min([api_cutoff] + [
                instant(verified_formal[s]["original_payload"]["publication"]["captured_at_utc"]) for s in formal_rows])
            available = True
            for system in formal_rows:
                published = instant(verified_formal[system]["original_payload"]["publication"]["published_at_utc"])
                if published > api_cutoff:
                    available = False
                    comparison_issues.append("formal_publication_after_original_api_freeze:" + system)
            fixtures = {}
            for row in source_rows:
                fixtures.setdefault(str(row.get("fixture_id")), row)
            required_fixtures = sorted(fixtures)
            for fixture, row in fixtures.items():
                try:
                    if not available:
                        continue
                    matched = {}
                    for system in formal_rows:
                        peers = [p for p in formal_rows[system] if str(p.get("fixture_id")) == fixture and _fact(p) == _fact(row)]
                        if not peers:
                            comparison_issues.append("formal_fixture_not_covered:" + system + ":" + fixture)
                            continue
                        ids_match = all(row.get(k) is not None and
                                        all(str(p.get(k)) == str(row[k]) for p in peers) for k in ("home_id", "away_id"))
                        if not ids_match:
                            comparison_issues.append("cross_source_native_team_ids_unverified:" + system + ":" + fixture)
                        else:
                            matched[system] = peers
                    if len(matched) != 2:
                        continue
                    context = match_pitchapi(row, pitch, as_of=context_cutoff.isoformat())
                    if context:
                        common.append({"fixture_id": fixture, "pitch_fixture_id": context["native_fixture_id"],
                                       "api_freeze_cutoff": api_cutoff.isoformat(),
                                       "context_cutoff": context_cutoff.isoformat(),
                                       "native_exact_markets_verified_independently": True})
                    else:
                        comparison_issues.append("pitch_fixture_not_covered_at_original_cutoff:" + fixture)
                except ValueError:
                    comparison_issues.append("cross_source_fixture_evidence_invalid:" + fixture)
        plan_day = next(d for d in plan["days"] if d["date"] == day)
        ready = bool(not issues and plan_day["status"] == "READY" and not comparison_issues
                     and capsule and capsule["verified"]["source_eligible"] and required_fixtures
                     and len(common) == len(required_fixtures)
                     and all(v["status"] == "READY" for v in formal.values()))
        settlements = build_native_settlements(native, outcomes, as_of=as_of,
                full_pool_verification=capsule["verified"]) if native else None
        reports.append({"date": day, "formal_sources": formal, "common_fixtures_at_original_cutoff": common,
            "required_api_fixture_ids": required_fixtures, "comparison_scope": "all_original_api_fixtures_independent_native_market_cohorts",
            "comparison_blockers": sorted(set(comparison_issues)),
            "native_pool": {"status": capsule["verified"]["status"],
                            "blockers": capsule["verified"]["blockers"],
                            "counts": capsule["envelope"]["counts"],
                            "member_sha256": capsule["member_sha256"]} if capsule else None,
            "settlements": {"status": settlements["status"], "native_publication_id": settlements["native_publication_id"],
                "cohorts": {name: {k: v for k, v in group.items() if k != "rows"}
                            for name, group in settlements["cohorts"].items()},
                "rejection_counts": dict(Counter(r["reason"] for r in settlements["rejections"]))} if settlements else None,
            "ready_for_frozen_parallel_test": ready,
            "ready_for_new_prematch_report": ready and instant(as_of) <= instant(cutoff)
                and all(verified_formal[s]["current_ready"] for s in verified_formal)
                and all(instant(r["kickoff"]) > instant(as_of) for r in native.get("top_positions", []))})
    ready = plan["source_ready"] and not issues and all(d["ready_for_frozen_parallel_test"] for d in reports)
    return {"schema": "multimodel-v2-repair-qualification-v1", "start_date": start_date, "as_of": as_of,
            "planner": plan, "days": reports, "issues": sorted(set(issues)),
            "ready_for_parallel_1_to_1": ready, "full_shadow_passed": False,
            "status": "READY_FOR_PARALLEL_TEST" if ready else "SOURCE_BLOCKED",
            "models_executed": False, "paid_api_calls": 0, "register_writes": False, "n_effect": 0}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args(argv)
    config = load_json(args.manifest)["payload"]
    run = load_json(config["run"])["payload"]
    archives = []
    for item in config["artifacts"]:
        metadata = load_json(item["metadata"])["payload"]["artifacts"]
        matches = [a for a in metadata if str(a["id"]) == str(item["artifact_id"])]
        if len(matches) != 1:
            raise ValueError("missing_or_ambiguous_artifact_id")
        archives.append(read_artifact(item["zip"], run, matches[0]))
    def formal(path):
        capture = load_json(path)
        return read_forward_freeze(path) if capture["payload"].get("schema") == "multimodel-v2-forward-freeze-receipt-v1" else capture
    result = assess_repair_sources(args.start, run, load_json(config["jobs"])["payload"], archives,
        {s: [formal(p) for p in config.get("formal", {}).get(s, [])] for s in ("kb21", "consensus")},
        [load_json(p) for p in config.get("pitch", [])], as_of=args.as_of,
        checkout_sha=config.get("checkout_sha"), scheduled_date=config.get("scheduled_date"),
        cron_slot=config.get("cron_slot"), event_name=config.get("event_name"),
        job_log=load_json(config["job_log"])["payload"]["content"] if config.get("job_log") else "",
        outcomes=load_json(config["outcomes"])["payload"] if config.get("outcomes") else [])
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
