"""Strict, offline D/D+1/D+2 coverage and Warsaw deadline qualification.

The planner never runs a collector, changes a workflow or moves an existing
freeze. A late source can remain genuinely prematch while missing the 11:30
report. An intentional opposite DST slot is SKIPPED, never source-ready.

``validate_three_day_sources`` accepts one normalized evidence object per day:
date, status (``ok`` or the original dated status dict), run_id, head_sha,
code_sha (the actual checkout), artifact_name, artifact_digest,
digest_verified, generated_at_utc, frozen_at_utc, native_publication_id,
full_pool_complete, candidate_count, and rows (native candidate objects with
independently identified quotes; an explicit empty array preserves observed
absence and never creates a quote). An explicit publication dict can supply its
own id/captured_at_utc instead. These are supplied observations, not defaults.
``artifact_audit`` day summaries alone are insufficient because they omit rows
and independent quote evidence; published-only exports remain blocked.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
import re

from .source_audit import classify_run
from .source_manifest import WARSAW, _quote, identifier, instant, local_day, market_identity

WORKFLOW = ".github/workflows/api-market-multiday-experiment.yml"
SCAN_STEP = "Independent scan per date"
ARTIFACT = "api-market-multiday-experiment"
ALLOWED_ARTIFACTS = frozenset({ARTIFACT, "multimodel-v2-full-source"})


def _utc(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _fixture_fact(row):
    names = []
    for field in ("home", "away"):
        value = row.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("invalid_fixture_team_name")
        names.append(value)
    team_ids = tuple(identifier(row[field]) if row.get(field) is not None else None
                     for field in ("home_id", "away_id"))
    return identifier(row.get("fixture_id")), (_utc(instant(row.get("kickoff"))), *names, *team_ids)


def plan_report_dates(start_date, *, days=3):
    """Demand exactly three local calendar dates, including across DST."""
    start = local_day(start_date)
    if type(days) is not int or days != 3:
        raise ValueError("multimodel_requires_exactly_three_days")
    return [(start + timedelta(days=offset)).isoformat() for offset in range(3)]


def report_deadline(start_date):
    """The shared deadline for all three PDF dates, with Warsaw's real offset."""
    return datetime.combine(local_day(start_date), time(11, 30), tzinfo=WARSAW).isoformat()


def scheduled_slot(scheduled_date, cron_slot, *, event_name="schedule", actual_started_at=None):
    """Use the declared nominal UTC date/slot, never the delayed start hour.

    scheduled_date cannot be guessed from an execution that crossed midnight.
    Manual dispatch is separate and has no invented nominal slot.
    """
    if event_name == "workflow_dispatch":
        return {"status": "MANUAL", "execute": True, "nominal_at_utc": None,
                "nominal_at_warsaw": None, "delay_seconds": None}
    if event_name != "schedule":
        return {"status": "UNVERIFIED", "execute": False, "reason": "unsupported_or_missing_event"}
    if cron_slot not in ("0 8 * * *", "0 9 * * *") or scheduled_date is None:
        return {"status": "UNVERIFIED", "execute": False, "reason": "nominal_slot_evidence_missing"}
    day = local_day(scheduled_date)
    hour = 8 if cron_slot == "0 8 * * *" else 9
    nominal = datetime.combine(day, time(hour), tzinfo=timezone.utc)
    local = nominal.astimezone(WARSAW)
    result = {"status": "ACTIVE" if local.hour == 10 else "OPPOSITE_DST_SLOT",
              "execute": local.hour == 10, "nominal_at_utc": _utc(nominal),
              "nominal_at_warsaw": local.isoformat(), "delay_seconds": None}
    if actual_started_at is not None:
        delay = (instant(actual_started_at) - nominal).total_seconds()
        if delay < 0:
            result.update(status="UNVERIFIED", execute=False, reason="run_before_nominal_slot")
        result["delay_seconds"] = delay
    return result


def _live_artifacts(run, artifacts, issues):
    values = artifacts.get("artifacts") if isinstance(artifacts, dict) else artifacts
    if not isinstance(values, list) or any(not isinstance(a, dict) for a in values):
        issues.append("artifact_inventory_missing")
        return {}
    result = {}
    counts = Counter(a.get("name") for a in values if isinstance(a.get("name"), str))
    for artifact in values:
        name = artifact.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append("artifact_name_invalid")
            continue
        if name not in ALLOWED_ARTIFACTS:
            continue  # Other outputs from this run are not coverage evidence.
        origin = artifact.get("workflow_run") or {}
        if not isinstance(origin, dict):
            origin = {}
        if (counts[name] != 1 or artifact.get("expired") is not False
                or str(origin.get("id")) != str(run.get("id"))
                or origin.get("head_sha") != run.get("head_sha")
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact.get("digest")))):
            issues.append("artifact_unavailable_or_unbound")
            continue
        result[name] = artifact
    return result


def _day_evidence(day, copies, run, live, checkout_sha, started, completed, cutoff, deadline):
    result = {"date": day, "status": "SOURCE_BLOCKED", "present": bool(copies),
              "source_complete": False, "prematch_valid": False,
              "available_before_deadline": False, "rows": None, "issues": []}
    issues = result["issues"]
    if len(copies) != 1:
        issues.append("missing_date" if not copies else "duplicate_date_evidence")
        return result
    evidence = copies[0]
    status = evidence.get("status")
    if isinstance(status, dict):
        if status.get("date") != day:
            issues.append("status_date_mismatch")
        status = status.get("status")
    if status != "ok":
        issues.append("date_status_not_ok")
    if evidence.get("file_date", day) != day:
        issues.append("file_date_mismatch")
    if (str(evidence.get("run_id")) != str(run.get("id"))
            or evidence.get("head_sha") != run.get("head_sha")):
        issues.append("date_run_binding_mismatch")
    if not _sha(checkout_sha) or evidence.get("code_sha") != checkout_sha:
        issues.append("date_checkout_sha_unverified")
    artifact_name = evidence.get("artifact_name")
    artifact = live.get(artifact_name) if isinstance(artifact_name, str) else None
    if artifact is None:
        issues.append("dated_artifact_missing")
    elif (evidence.get("digest_verified") is not True
          or evidence.get("artifact_digest") != artifact["digest"]):
        issues.append("dated_artifact_digest_unverified")
    publication = evidence.get("publication")
    publication = publication if isinstance(publication, dict) else {}
    native_id = evidence.get("native_publication_id", publication.get("id"))
    try:
        identifier(native_id)
    except ValueError:
        issues.append("native_publication_id_missing")
    if ("native_publication_id" in evidence and "id" in publication
            and str(evidence["native_publication_id"]) != str(publication["id"])):
        issues.append("conflicting_native_publication_id")
    frozen = None
    try:
        generated = instant(evidence.get("generated_at_utc"))
        frozen = instant(evidence.get("frozen_at_utc", publication.get("captured_at_utc")))
        if "frozen_at_utc" in evidence and "captured_at_utc" in publication:
            if frozen != instant(publication["captured_at_utc"]):
                issues.append("conflicting_freeze_timestamp")
        if not (started is not None and completed is not None
                and started <= generated <= frozen <= completed <= cutoff):
            issues.append("freeze_outside_verified_run")
        result["frozen_at_utc"] = _utc(frozen)
        result["available_before_deadline"] = frozen <= deadline and completed is not None and completed <= deadline
        if not result["available_before_deadline"]:
            issues.append("report_deadline_missed")
    except ValueError:
        issues.append("freeze_timestamp_missing_or_invalid")
    rows = evidence.get("rows")
    count = evidence.get("candidate_count")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or type(count) is not int or count < 0 or len(rows) != count):
        issues.append("full_candidate_rows_missing_or_count_mismatch")
        rows = []
    else:
        result["rows"] = len(rows)
    result["source_complete"] = (evidence.get("full_pool_complete") is True
                                 and evidence.get("published_only") is not True
                                 and result["rows"] is not None)
    if not result["source_complete"]:
        issues.append("full_pool_not_complete")
    identities = []
    fixture_facts = defaultdict(set)
    valid_rows = 0
    for index, row in enumerate(rows):
        try:
            key = market_identity(row)
            identities.append(key)
            kickoff = instant(row.get("kickoff"))
            fixture_id, facts = _fixture_fact(row)
            fixture_facts[fixture_id].add(facts)
            if kickoff.astimezone(WARSAW).date().isoformat() != day:
                raise ValueError("kickoff_date_mismatch")
            if frozen is None or frozen >= kickoff:
                raise ValueError("freeze_not_prematch")
            quotes = row.get("quotes")
            if not isinstance(quotes, list):
                raise ValueError("independent_quotes_missing")
            # No candidate identity is copied into a quote as synthetic proof.
            for quote in quotes:
                if not isinstance(quote, dict):
                    raise ValueError("invalid_quote")
                _quote(quote, key, frozen, kickoff)
            valid_rows += 1
        except ValueError as exc:
            issues.append(f"row:{index}:{exc}")
    if len(identities) != len(set(identities)):
        issues.append("duplicate_exact_market")
    if any(len(facts) > 1 for facts in fixture_facts.values()):
        issues.append("conflicting_fixture_facts")
    result["prematch_valid"] = (result["rows"] is not None and frozen is not None
                                and valid_rows == len(rows))
    result["issues"] = sorted(set(issues))
    if not result["issues"]:
        result["status"] = "READY"
    return result


def validate_three_day_sources(start_date, run, jobs, artifacts, date_evidence, *, as_of,
                               scheduled_date=None, cron_slot=None, checkout_sha=None,
                               event_name=None, job_log=""):
    """Qualify the whole report without inferring missing source evidence.

    Source readiness requires all three dates, completed successful scan, a
    correctly executed slot, verified byte digest, actual checkout lineage,
    explicit complete pools and independent prematch quotes. ``as_of`` may be
    later for a historical audit; the original deadline is never shifted.
    """
    dates = plan_report_dates(start_date)
    cutoff = instant(as_of)
    deadline = instant(report_deadline(start_date))
    if not isinstance(run, dict) or not isinstance(date_evidence, list):
        raise ValueError("run_and_date_evidence_required")
    issues = []
    event = event_name if event_name is not None else run.get("event")
    try:
        schedule = scheduled_slot(scheduled_date, cron_slot, event_name=event,
                                  actual_started_at=run.get("run_started_at"))
    except ValueError:
        schedule = {"status": "UNVERIFIED", "execute": False, "reason": "invalid_schedule_timestamp"}
    started = completed = None
    try:
        started, completed = instant(run.get("run_started_at")), instant(run.get("updated_at"))
        if not started <= completed <= cutoff:
            issues.append("run_outside_as_of")
    except ValueError:
        issues.append("run_timestamps_missing_or_invalid")
    if run.get("path") != WORKFLOW or not _sha(run.get("head_sha")):
        issues.append("run_workflow_or_head_sha_unverified")
    try:
        identifier(run.get("id"))
    except ValueError:
        issues.append("run_identity_missing")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        issues.append("run_not_successful")
    wrapper = artifacts if isinstance(artifacts, dict) else {"artifacts": artifacts}
    try:
        execution = classify_run(run, jobs, wrapper, scan_step=SCAN_STEP, job_log=job_log)
    except (ValueError, TypeError, AttributeError):
        execution = {"status": "UNVERIFIED", "scan_executed_successfully": False,
                     "reason": "scan_step_evidence_missing"}
    opposite = schedule["status"] == "OPPOSITE_DST_SLOT"
    confirmed_skip = (opposite and execution.get("status") == "SKIPPED"
                      and execution.get("cause") == "opposite_dst_slot_confirmed"
                      and any(line.endswith("##[notice]Opposite DST slot skipped by design: " + str(cron_slot))
                              for line in job_log.splitlines()))
    if not schedule.get("execute") and not confirmed_skip:
        issues.append("schedule_not_qualified")
    if schedule.get("execute") and not execution.get("scan_executed_successfully"):
        issues.append("scan_not_executed_successfully")
    if opposite and execution.get("scan_executed_successfully"):
        issues.append("scan_executed_on_opposite_dst_slot")
    if not confirmed_skip and not _sha(checkout_sha):
        issues.append("actual_checkout_sha_missing")
    live = _live_artifacts(run, artifacts, issues) if not confirmed_skip else {}
    grouped = {day: [] for day in dates}
    unexpected = []
    for evidence in date_evidence:
        if not isinstance(evidence, dict):
            issues.append("invalid_date_evidence")
        else:
            day = evidence.get("date")
            try:
                local_day(day)
            except ValueError:
                issues.append("invalid_date_evidence")
                continue
            if day in grouped:
                grouped[day].append(evidence)
            else:
                unexpected.append(day)
    days = [_day_evidence(day, grouped[day], run, live, checkout_sha, started, completed, cutoff, deadline)
            for day in dates]
    across_dates = defaultdict(lambda: defaultdict(set))
    for day, copies in grouped.items():
        for evidence in copies:
            rows = evidence.get("rows")
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                try:
                    fixture_id, facts = _fixture_fact(row)
                    across_dates[fixture_id][day].add(facts)
                except ValueError:
                    pass  # Detailed row errors are already included above.
    if any(len(by_day) > 1 and len(set().union(*by_day.values())) > 1 for by_day in across_dates.values()):
        issues.append("conflicting_fixture_across_report_dates")
    ready = not issues and not confirmed_skip and all(day["status"] == "READY" for day in days)
    return {"schema": "multimodel-v2-three-day-qualification-v1", "start_date": start_date,
            "dates": dates, "timezone": "Europe/Warsaw", "deadline_at": report_deadline(start_date),
            "as_of": _utc(cutoff), "schedule": schedule, "execution": execution,
            "workflow_head_sha": run.get("head_sha"), "actual_checkout_sha": checkout_sha,
            "days": days, "unexpected_dates": unexpected, "issues": sorted(set(issues)),
            "deadline_met": completed is not None and completed <= deadline and all(d["available_before_deadline"] for d in days),
            "original_prematch_valid": all(d["prematch_valid"] for d in days),
            "source_ready": ready, "status": "READY" if ready else "SKIPPED" if confirmed_skip else "SOURCE_BLOCKED",
            "paid_api_calls": 0, "register_writes": False, "n_effect": 0}
