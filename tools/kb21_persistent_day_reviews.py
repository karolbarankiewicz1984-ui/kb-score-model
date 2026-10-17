"""Persist one ACTUALLY human-reviewed KB21 calendar date across rolling windows.

Daily files (committed by a real independent reviewer) live at:
  data/kb21_calendar_reviews/YYYY-MM-DD.json

A reviewed 2026-10-19 day is independent from the 3-day window in which it
was produced, so tomorrow's 18-20 -> 19-21 rollover cannot lose its review.

This bridge never creates reviewers, captures, verified zeros or approval
timestamps, and NEVER submits the unsigned working forms for approval.
Every supplied dated signed review MUST pass the existing strict KB21
calendar signoff validator against TODAY'S independent fixture queue.
An outdated match, source error, changed kickoff or missed signing deadline
fails closed. A legitimate single-day PASS does not open the 3-day global gate.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.kb21_calendar_signoff import validate
from tools.kb21_calendar_coverage import SCOPE
from tools.kb21_fixture_crosscheck import _instant

SCHEMA = "kb21-manual-one-day-calendar-review-v1"
WARSAW = ZoneInfo("Europe/Warsaw")


def _scope(queue, draft):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)
            or not isinstance(draft, dict) or not isinstance(draft.get("days"), dict)):
        raise ValueError("Invalid independent queue or prepared organizer draft")
    days = queue["days"]
    if (not 1 <= len(days) <= 3 or len(days) != len(set(days))
            or set(draft["days"]) != set(days)
            or draft.get("approval") is not None
            or (not isinstance(draft.get("daily_approvals"), dict))
            or set(draft["daily_approvals"]) != set(days)
            or any(v is not None for v in draft["daily_approvals"].values())):
        raise ValueError("Only an unsigned exact 1-3 day organizer draft is supported")
    for day in days:
        if datetime.fromisoformat(day).date().isoformat() != day:
            raise ValueError("Unrecognized calendar date")
        rows = draft["days"][day]
        if not isinstance(rows, dict) or set(rows) != set(SCOPE):
            raise ValueError("All 14 organizer records required on each day")
        for code in SCOPE:
            item = rows[code]
            if (not isinstance(item, dict)
                    or item.get("reviewer") is not None
                    or item.get("captured_at") is not None
                    or item.get("full_day_checked") is not False
                    or item.get("confirmed_zero_matches") is not None
                    or not isinstance(item.get("fixtures"), list)):
                raise ValueError("Draft already contains a human review claim")
    return days


def _now(now=None):
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("Current time must have a timezone")
    return clock.astimezone(timezone.utc)


def _deadline(day, queue):
    matches = [f for f in queue["fixtures"]
               if isinstance(f, dict) and f.get("date_warsaw") == day]
    times = [_instant(f.get("kickoff")) for f in matches]
    if any(when is None for when in times):
        return None, "UNKNOWN_CANDIDATE_KICKOFF"
    if times:
        return min(times), "FIRST_KICKOFF_OF_ALL_14_LEAGUES"
    # No games has no kickoff. A manual empty-day attest must be signed
    # BEFORE the date begins in Warsaw, never after the fact.
    cutoff = datetime.fromisoformat(day).replace(tzinfo=WARSAW)
    return cutoff.astimezone(timezone.utc), "ZERO_CANDIDATES_DATE_START"


def prepare(queue, unsigned_draft, now=None):
    """Human fillable, still UNSIGNED exact organizer inventory by date."""
    days = _scope(queue, unsigned_draft)
    clock = _now(now)
    forms = {}
    for day in days:
        cutoff, kind = _deadline(day, queue)
        forms[day] = {
            "schema": SCHEMA, "day": day,
            "competitions": deepcopy(unsigned_draft["days"][day]),
            "approval": None,
            "review_instructions": (
                "UNSIGNED working form; NEVER sign automatically. "
                "A real independent analyst must inspect the complete live "
                "official schedule for all 14 leagues on the exact Warsaw day "
                "and reconcile fixture names/timezones with the ESPN candidates. "
                "Fill each competition's real captured_at, reviewer, full_day_checked, "
                "confirmed_zero_matches (true only after VERIFYING full organizer "
                "no-game schedule), and correct fixtures. After every source "
                "is checked BEFORE cutoff, fill approval: reviewer, approved_at "
                "and attests_independent_official_review=true. "
                "Commit the completed form to data/kb21_calendar_reviews/"
                + day + ".json. Any changed fixture/late approval is rejected."
            ),
            "independent_candidate_count": sum(
                isinstance(f, dict) and f.get("date_warsaw") == day
                for f in queue["fixtures"]),
            "review_cutoff_utc": cutoff.isoformat() if cutoff else None,
            "cutoff_kind": kind,
            "signoff_window_open_at_generation":
                cutoff is not None and clock < cutoff,
            "human_signoff_provided": False,
            "calendar_gate": "BLOCKED",
            "safe_to_publish_play": False,
        }
    return forms


def apply(queue, unsigned_draft, reviews_dir, now=None):
    """Accept only committed signed date files that pass strict real gate."""
    days = _scope(queue, unsigned_draft)
    clock = _now(now)
    out = deepcopy(unsigned_draft)
    directory = Path(reviews_dir)
    applied = []
    for day in days:
        target = directory / (day + ".json")
        if not target.is_file():
            continue
        supplied = json.loads(target.read_text(encoding="utf-8"))
        if (not isinstance(supplied, dict)
                or supplied.get("schema") != SCHEMA
                or supplied.get("day") != day
                or not isinstance(supplied.get("competitions"), dict)
                or set(supplied["competitions"]) != set(SCOPE)
                or not isinstance(supplied.get("approval"), dict)):
            raise ValueError("Invalid dated manual review: " + day)
        approval = supplied["approval"]
        approved_at = _instant(approval.get("approved_at"))
        if (approved_at is None or approved_at > clock
                or approval.get("attests_independent_official_review") is not True
                or not isinstance(approval.get("reviewer"), str)
                or not approval["reviewer"].strip()):
            raise ValueError("Absent, future or invalid genuine manual approval for " + day)
        # Prevent backdating unsigned-form machine metadata into an attestation.
        for league, source in supplied["competitions"].items():
            stamp = _instant(source.get("captured_at")) if isinstance(source, dict) else None
            if stamp is None or stamp > clock:
                raise ValueError("Missing or future human source capture: " + day + " " + league)
            if (not isinstance(source.get("reviewer"), str)
                    or not source["reviewer"].strip()
                    or source.get("full_day_checked") is not True
                    or not isinstance(source.get("fixtures"), list)):
                raise ValueError("Incomplete independent reviewer attestation: " + day + " " + league)
        cutoff, cutoff_kind = _deadline(day, queue)
        if cutoff is None or approved_at >= cutoff:
            raise ValueError("Manual signoff not strictly before " + cutoff_kind + ": " + day)
        if any(_instant(s["captured_at"]) >= cutoff
               for s in supplied["competitions"].values()):
            raise ValueError("Manual calendar capture after whole-day cutoff: " + day)

        day_queue = {
            "days": [day],
            "fixtures": [f for f in queue["fixtures"]
                         if isinstance(f, dict) and f.get("date_warsaw") == day],
            "source_status": {day: queue.get("source_status", {}).get(day, [])},
        }
        day_inventory = {
            "days": {day: supplied["competitions"]},
            "daily_approvals": {day: approval},
            "approval": None,
        }
        checked = validate(day_queue, day_inventory)
        if (checked.get("calendar_gate") != "PASS_MANUAL"
                or checked.get("approved_days") != 1
                or checked.get("safe_to_publish_play") is not False):
            raise ValueError(
                "Dated human review conflicts with current independent calendar: "
                + day + "; " + repr(checked.get("errors", [])[:6]))
        out["days"][day] = deepcopy(supplied["competitions"])
        out["daily_approvals"][day] = deepcopy(approval)
        applied.append(day)
    # Apply does not decide global PASS; main validator runs on the combined
    # current source queue and must explicitly produce the per-day states.
    return out, {
        "schema": "kb21-persistent-daily-review-load-v1",
        "dates_requested": list(days),
        "manual_days_reused": applied,
        "pending_days": [day for day in days if day not in applied],
        "persisted_review_files_are_user_supplied": True,
        "automated_signoffs_created": 0,
        "calendar_gate": "BLOCKED_UNTIL_FINAL_VALIDATION",
        "safe_to_publish_play": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("unsigned_draft")
    p.add_argument("--forms-dir", required=True)
    p.add_argument("--reviews-dir", default="data/kb21_calendar_reviews")
    p.add_argument("--output", required=True)
    p.add_argument("--status-output", required=True)
    a = p.parse_args()
    q, draft = [
        json.loads(Path(src).read_text(encoding="utf-8"))
        for src in (a.queue, a.unsigned_draft)
    ]
    forms = prepare(q, draft)
    formdir = Path(a.forms_dir)
    formdir.mkdir(parents=True, exist_ok=True)
    for day, form in forms.items():
        file = formdir / (day + ".json")
        file.write_text(json.dumps(form, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    result, status = apply(q, draft, a.reviews_dir)
    for filename, document in (
        (a.output, result), (a.status_output, status)
    ):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print("KB21 persistent human calendar files:", status["manual_days_reused"],
          "pending:", status["pending_days"],
          "automatic signatures: 0; final validator still mandatory")


if __name__ == "__main__":
    main()
