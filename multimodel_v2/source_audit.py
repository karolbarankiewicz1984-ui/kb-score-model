"""Offline source diagnostics and a conservative recovery policy.

All actions here are classifications. No provider or workflow is invoked.
"""
import re

from .git_publication import validate_receipt
from .source_manifest import instant


def classify_run(run, jobs, artifacts, *, scan_step, job_log="", git_receipt=None):
    rows = jobs.get("jobs")
    outputs = artifacts.get("artifacts")
    if (not isinstance(rows, list) or not isinstance(outputs, list)
            or not rows or any(str(j.get("run_id")) != str(run.get("id")) for j in rows)
            or jobs.get("total_count", len(rows)) != len(rows)):
        raise ValueError("incomplete_or_mismatched_run_diagnostics")
    result = {"run_id": str(run["id"]), "run_conclusion": run.get("conclusion"),
              "status": "SOURCE_BLOCKED", "scan_executed_successfully": False,
              "source_eligible": False, "artifact_count": len(outputs), "paid_scan_started": False}
    if run.get("status") != "completed":
        return dict(result, reason="run_not_completed", cause="not_yet_known")
    if run.get("conclusion") != "success":
        before = all(j.get("steps") == [] and j.get("runner_id") == 0 for j in rows)
        return dict(result, reason="failed_before_recorded_steps" if before else "run_failed",
                    cause="unconfirmed_requires_original_annotations_or_logs")
    steps = [s for j in rows for s in (j.get("steps") or []) if s.get("name") == scan_step]
    if len(steps) != 1:
        return dict(result, reason="scan_step_not_uniquely_observed", cause="missing_step_evidence")
    if steps[0].get("conclusion") == "skipped":
        notice = False
        for line in job_log.splitlines():
            match = re.fullmatch(r"(\S+) ##\[notice\]Opposite DST slot skipped by design: (0 [89] \* \* \*)", line)
            if match:
                stamp = instant(match[1])
                notice = instant(run["run_started_at"]) <= stamp <= instant(run["updated_at"])
        return dict(result, status="SKIPPED", reason="scan_skipped_no_new_source",
                    cause="opposite_dst_slot_confirmed" if notice else "skip_cause_unconfirmed")
    if steps[0].get("conclusion") != "success":
        return dict(result, reason="scan_step_not_successful", cause="scan_failed_or_cancelled")
    result["scan_executed_successfully"] = True
    if git_receipt is not None:
        ref = validate_receipt(git_receipt, run)
        return dict(result, status="RECORDED_SOURCE_LINKED", reason="native_git_output_verified",
                    cause="git_persistence_not_actions_upload", source_ref=ref)
    live = [a for a in outputs if a.get("expired") is False]
    return dict(result, reason="dated_payload_validation_required" if live else "no_available_output_evidence",
                cause="artifact_metadata_alone_is_not_complete_source")


def recovery_policy(*, as_of, report_freeze, evidence_kind, original_available,
                    original_captured_at=None, kickoff=None, paid_scan=False):
    """Never turn a current retrieval into an old pre-match prediction.

    Reading original, already recorded evidence is always distinct from issuing
    a forecast. Unknown freeze/kickoff remains unknown even for future dates.
    """
    now, freeze = instant(as_of), instant(report_freeze)
    if evidence_kind not in {"metadata", "forecast", "quote", "context", "result"}:
        raise ValueError("unknown_evidence_kind")
    if paid_scan:
        return {"status": "FORBIDDEN_PAID_SCAN", "read_existing_only": True, "eligible_for_original_freeze": False}
    if evidence_kind == "metadata":
        return {"status": "SAFE_READ_METADATA", "read_existing_only": True, "eligible_for_original_freeze": False}
    if evidence_kind == "result":
        return {"status": "HISTORICAL_SETTLEMENT_ONLY", "read_existing_only": True, "eligible_for_original_freeze": False}
    if original_available:
        if original_captured_at is None or kickoff is None:
            status, eligible = "HISTORICAL_ONLY_UNVERIFIED_TIMING", False
        else:
            captured, ko = instant(original_captured_at), instant(kickoff)
            if captured > now:
                raise ValueError("original_not_yet_available")
            eligible = captured <= freeze and captured < ko
            status = ("SAFE_READ_ORIGINAL_TIMING_ELIGIBLE" if eligible else
                      "HISTORICAL_ONLY_AFTER_KICKOFF" if captured >= ko else "LATER_EDITION_ONLY")
        return {"status": status, "read_existing_only": True, "eligible_for_original_freeze": eligible,
                "other_provenance_checks_required": True}
    ko = instant(kickoff) if kickoff is not None else None
    status = ("FORBIDDEN_RETROSPECTIVE_PREMATCH" if now >= freeze or (ko is not None and now >= ko)
              else "WAIT_FOR_PROSPECTIVE_ORIGINAL_SOURCE")
    return {"status": status, "read_existing_only": True, "eligible_for_original_freeze": False}
