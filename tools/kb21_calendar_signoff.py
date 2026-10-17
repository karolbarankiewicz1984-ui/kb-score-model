"""Validate documented, HUMAN-REVIEWED official KB21 fixture inventories.

A reviewed source is manual attestation, not cryptographic source verification.
A PASS is allowed only for an explicit 14-competition, same-day signed-off
inventory reconciled with ESPN's independent fixtures. Never authorizes PLAY,
P(model), historical N or LIVE PDFs by itself.

Input inventory: {"days": {"YYYY-MM-DD": {"eng.1": {
  "organizer_url": official schedule URL, "captured_at": timezone ISO,
  "reviewer": name, "full_day_checked": true,
  "confirmed_zero_matches": false, "fixtures": [
    {"home": "...", "away": "...", "kickoff": timezone ISO}
  ]}, ...}},
  "approval": {"reviewer": name, "approved_at": timezone ISO,
               "attests_independent_official_review": true}}
No missing league or unreviewed empty schedule is silently accepted.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team
from tools.kb21_calendar_conflict_evidence import _api_match
from tools.kb21_official_review import OFFICIAL_PAGES
from tools.kb21_calendar_coverage import SCOPE


def _identity(match, league):
    if not isinstance(match, dict):
        return None
    home, away = _team(league, match.get("home")), _team(league, match.get("away"))
    kickoff = _instant(match.get("kickoff"))
    if not home or not away or kickoff is None:
        return None
    return home, away, kickoff


def _recorded_third_source(league, day, official_key, candidate, resolution, snapshot):
    """A reviewer's explicit mismatch decision must agree with an actual prematch snapshot."""
    if not isinstance(resolution, dict) or not isinstance(snapshot, dict):
        return False
    if (resolution.get("fixture_id") != candidate.get("fixture_id")
            or not isinstance(resolution.get("reviewer"), str)
            or not resolution["reviewer"].strip()
            or not isinstance(resolution.get("reason"), str)
            or len(resolution["reason"].strip()) < 15):
        return False
    if (snapshot.get("source") != "API-Football" or snapshot.get("date") != day
            or not isinstance(snapshot.get("candidates"), list)):
        return False
    approved = [r for r in snapshot["candidates"]
                if isinstance(r, dict)
                and str(r.get("fixture_id")) == str(resolution.get("third_source_fixture_id"))
                and _api_match(league, {
                    "home": candidate.get("fixture", "").split(" - ", 1)[0],
                    "away": candidate.get("fixture", "").split(" - ", 1)[1]
                    if " - " in candidate.get("fixture", "") else "",
                    "kickoff": official_key[2].isoformat()}, r)]
    if len(approved) != 1:
        return False
    observed = _instant(approved[0].get("snapshot_utc") or snapshot.get("snapshot_utc"))
    independent = _instant(candidate.get("kickoff"))
    if observed is None or independent is None:
        return False
    return observed < min(official_key[2], independent)


def validate(queue, inventory, third_party_snapshots=None):
    if not isinstance(queue, dict) or not isinstance(queue.get("days"), list) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue with days and fixtures")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("days"), dict):
        raise ValueError("Expected manually reviewed calendar inventory with days")
    requested = queue["days"]
    if (not 1 <= len(requested) <= 3 or len(set(requested)) != len(requested)
            or any(not isinstance(d, str) for d in requested)):
        raise ValueError("Expected 1-3 distinct Warsaw calendar days")
    for day in requested:
        try:
            if datetime.fromisoformat(day).date().isoformat() != day:
                raise ValueError("Non-canonical date")
        except ValueError:
            raise ValueError("Invalid Warsaw calendar day")
    result = {"status": "BLOCKED", "calendar_gate": "BLOCKED",
              "publication": "DIAGNOSTIC / NO PLAY", "days": {},
              "manual_source_attestation": False, "safe_to_publish_play": False}
    all_errors = []
    # The dashboard already reports candidate fixtures outside the 14-league
    # scope. Enforce the SAME condition at the actual signoff boundary: a
    # pristine, manually signed inventory cannot silently ignore extra games.
    day_fixture_issues = {day: [] for day in requested}
    seen_ids = set()
    for fixture in queue["fixtures"]:
        if not isinstance(fixture, dict):
            all_errors.append("INVALID_CANDIDATE_RECORD")
            continue
        date = fixture.get("date_warsaw")
        fid = fixture.get("fixture_id")
        if date not in day_fixture_issues:
            all_errors.append("CANDIDATE_OUTSIDE_REQUESTED_CALENDAR_DATES")
            continue
        if not isinstance(fid, str) or ":" not in fid or not fid.split(":", 1)[1]:
            day_fixture_issues[date].append("INVALID_CANDIDATE_FIXTURE_ID")
            continue
        league = fid.split(":", 1)[0]
        if league not in SCOPE:
            day_fixture_issues[date].append(
                "UNREVIEWED_COMPETITION_OUTSIDE_SCOPE: " + league
            )
        if fid in seen_ids:
            day_fixture_issues[date].append(
                "DUPLICATE_INDEPENDENT_FIXTURE_ID: " + fid
            )
        seen_ids.add(fid)
    # A corrupt global queue or inventory scope must not expose seemingly
    # approved individual days while the overall three-day gate is blocked.
    requested_dates_match = set(inventory["days"]) == set(requested)
    if not requested_dates_match:
        all_errors.append("INVENTORY_DAYS_DO_NOT_MATCH_REQUEST")
    global_input_errors = tuple(all_errors)
    third_party_snapshots = third_party_snapshots or {}
    daily_approvals = inventory.get("daily_approvals") or {}
    if not isinstance(daily_approvals, dict):
        raise ValueError("daily_approvals must be a day-keyed object")
    global_approval = inventory.get("approval")
    approved_day_count = 0
    pending_approval_count = 0
    for day in sorted(set(queue["days"])):
        official_day = inventory["days"].get(day)
        day_errors = list(day_fixture_issues[day])
        if global_input_errors:
            day_errors.append("GLOBAL_CALENDAR_INPUT_INTEGRITY_FAILURE")
        capture_times = []
        first_kickoffs = []
        rows = []
        league_sources = {x.get("league"): x for x in queue.get("source_status", {}).get(day, [])
                          if isinstance(x, dict)}
        for code, name in SCOPE.items():
            entry = official_day.get(code) if isinstance(official_day, dict) else None
            errors = []
            expected = [f for f in queue["fixtures"]
                        if isinstance(f, dict)
                        and f.get("date_warsaw") == day
                        and isinstance(f.get("fixture_id"), str)
                        and f["fixture_id"].split(":", 1)[0] == code]
            if not isinstance(entry, dict):
                errors.append("MISSING_ORGANIZER_INVENTORY")
                entry = {}
            official_url = OFFICIAL_PAGES.get(code)
            if entry.get("organizer_url") != official_url or not official_url:
                errors.append("MISSING_OR_DIFFERENT_OFFICIAL_SOURCE_URL")
            captured = _instant(entry.get("captured_at"))
            if captured is None:
                errors.append("MISSING_TIMESTAMPED_ORGANIZER_CAPTURE")
            else:
                capture_times.append(captured)
            try:
                target_date = datetime.fromisoformat(day).date()
            except ValueError:
                raise ValueError("Invalid requested calendar date")
            if captured is not None and captured.astimezone(ZoneInfo("Europe/Warsaw")).date() > target_date:
                errors.append("RETROACTIVE_ORGANIZER_CAPTURE")
            if not isinstance(entry.get("reviewer"), str) or not entry["reviewer"].strip():
                errors.append("MISSING_INDEPENDENT_REVIEWER")
            if entry.get("full_day_checked") is not True:
                errors.append("OFFICIAL_DAY_NOT_VERIFIED_COMPLETE")
            reported = entry.get("fixtures")
            if not isinstance(reported, list):
                errors.append("MISSING_ORGANIZER_FIXTURE_LIST")
                reported = []
            source = league_sources.get(code)
            if not source or source.get("status") != "OK":
                errors.append("INDEPENDENT_ESPN_SOURCE_NOT_HEALTHY")
            if not reported and entry.get("confirmed_zero_matches") is not True:
                errors.append("ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER")
            if reported and entry.get("confirmed_zero_matches") is True:
                errors.append("INCONSISTENT_ZERO_MATCH_FLAG")
            if len(reported) != len(expected):
                errors.append("OFFICIAL_VS_INDEPENDENT_FIXTURE_COUNT_DIFFERENCE")

            official_keys = [_identity(f, code) for f in reported]
            espn_keys = [_identity({
                "home": f.get("fixture", "").split(" - ", 1)[0],
                "away": f.get("fixture", "").split(" - ", 1)[1]
                if " - " in f.get("fixture", "") else "",
                "kickoff": f.get("kickoff"),
            }, code) for f in expected]
            for key in official_keys + espn_keys:
                if key is not None:
                    first_kickoffs.append(key[2])
            if any(x is None for x in official_keys + espn_keys):
                errors.append("INVALID_MATCH_IDENTITY_OR_TIMEZONE")
            else:
                if len(set(official_keys)) != len(official_keys):
                    errors.append("DUPLICATE_OFFICIAL_FIXTURE")
                remaining = list(zip(expected, espn_keys))
                resolutions = entry.get("time_discrepancies") or []
                if not isinstance(resolutions, list):
                    errors.append("INVALID_TIME_DISCREPANCY_DECISIONS")
                    resolutions = []
                used_resolutions = set()
                for key in official_keys:
                    exact = [i for i, (_, candidate) in enumerate(remaining)
                             if candidate[0:2] == key[0:2]
                             and abs((candidate[2] - key[2]).total_seconds()) <= 300]
                    if len(exact) == 1:
                        remaining.pop(exact[0])
                        continue
                    if len(exact) > 1:
                        errors.append("AMBIGUOUS_INDEPENDENT_MATCHES")
                        continue
                    same_teams = [i for i, (_, candidate) in enumerate(remaining)
                                  if candidate[0:2] == key[0:2]]
                    if len(same_teams) != 1:
                        errors.append("MATCH_IDENTITY_OR_TIME_DISAGREEMENT")
                        continue
                    index = same_teams[0]
                    candidate = remaining[index][0]
                    matching_resolutions = [i for i, decision in enumerate(resolutions)
                                            if isinstance(decision, dict)
                                            and decision.get("fixture_id") == candidate.get("fixture_id")]
                    if (len(matching_resolutions) != 1
                            or not _recorded_third_source(
                                code, day, key, candidate,
                                resolutions[matching_resolutions[0]] if matching_resolutions else None,
                                third_party_snapshots.get(day))):
                        errors.append("KICKOFF_CONFLICT_REQUIRES_PREMATCH_THIRD_SOURCE_AND_MANUAL_REVIEW")
                    else:
                        used_resolutions.add(matching_resolutions[0])
                        remaining.pop(index)
                if remaining:
                    errors.append("INDEPENDENT_MATCHES_UNEXPLAINED")
                if len(used_resolutions) != len(resolutions):
                    errors.append("UNUSED_OR_DUPLICATE_KICKOFF_RESOLUTIONS")
            if captured is not None and official_keys and all(x is not None for x in official_keys):
                if captured >= min(x[2] for x in official_keys):
                    errors.append("OFFICIAL_CAPTURE_NOT_PREMATCH")
            row = {"league_id": code, "competition": name, "calendar_status":
                   "MANUAL_MATCHED_FOR_SIGNOFF" if not errors else "BLOCKED",
                   "official_fixture_count": len(reported),
                   "independent_fixture_count": len(expected),
                   "errors": sorted(set(errors))}
            rows.append(row)
            for error in row["errors"]:
                day_errors.append(f"{code}: {error}")
        # A delayed/unresolved calendar on Saturday must never prevent
        # correctly reviewed Sunday from being approved on its own.
        approval = daily_approvals.get(day) or global_approval
        signoff_ok = (
            isinstance(approval, dict)
            and isinstance(approval.get("reviewer"), str)
            and bool(approval["reviewer"].strip())
            and _instant(approval.get("approved_at")) is not None
            and approval.get("attests_independent_official_review") is True
        )
        approved_time = _instant(approval.get("approved_at")) if isinstance(approval, dict) else None
        if signoff_ok and approved_time is not None:
            if capture_times and approved_time < max(capture_times):
                day_errors.append("FINAL_APPROVAL_PREDATES_OFFICIAL_SOURCE_CAPTURE")
            if first_kickoffs and approved_time >= min(first_kickoffs):
                day_errors.append("FINAL_APPROVAL_AFTER_FIRST_KICKOFF")
        ready = not day_errors
        if not signoff_ok:
            pending_approval_count += 1
        if ready and signoff_ok:
            status = "MANUALLY_APPROVED_CALENDAR"
            approved_day_count += 1
        elif ready:
            status = "READY_FOR_MANUAL_APPROVAL"
        else:
            status = "BLOCKED"
        result["days"][day] = {
            "status": status,
            "calendar_gate": "PASS_MANUAL" if status == "MANUALLY_APPROVED_CALENDAR" else "BLOCKED",
            "all_organizers_reviewed": ready,
            "approval_recorded": signoff_ok,
            "competitions": rows, "errors": day_errors,
        }
        all_errors += [f"{day}: {error}" for error in day_errors]
    result["ready_for_approval"] = not all_errors
    result["approved_days"] = approved_day_count
    result["pending_approval_days"] = pending_approval_count
    if not all_errors and approved_day_count == len(queue["days"]) and queue["days"]:
        result["status"] = "MANUALLY_APPROVED_CALENDAR"
        result["calendar_gate"] = "PASS_MANUAL"
        result["manual_source_attestation"] = True
    elif not all_errors and approved_day_count < len(queue["days"]):
        result["status"] = "READY_FOR_MANUAL_APPROVAL"
    else:
        result["status"] = ("PARTIALLY_APPROVED_CALENDAR"
                            if approved_day_count and requested_dates_match else "BLOCKED")
    if pending_approval_count:
        result["approval_missing"] = True
    result["errors"] = all_errors
    result["note"] = (
        "PASS_MANUAL means the analyst attests to independent checking of ALL listed organizer "
        "schedules. Code validates the inventory and timestamps but cannot authenticate web "
        "page contents. Even PASS_MANUAL never authorizes PLAY without original KB21 "
        "sport score, pre-price P(model), lineup/data/market controls and frozen records."
    )
    return result


def inventory_template(review):
    """Empty auditable source inventory; organizer URLs are NOT themselves approval."""
    if not isinstance(review, dict) or not isinstance(review.get("days"), dict):
        raise ValueError("Expected official calendar review with days dictionary")
    days = {}
    for day, data in review["days"].items():
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            raise ValueError("Official review day requires rows")
        days[day] = {
            row["league_id"]: {
                "organizer_url": row["organizer_entry_url"],
                "captured_at": None,
                "reviewer": None,
                "full_day_checked": False,
                "confirmed_zero_matches": None,
                "fixtures": [],
            }
            for row in data["rows"]
        }
    return {
        "schema": "kb21-human-calendar-inventory-v1",
        "days": days,
        "daily_approvals": {day: None for day in days},
        "approval": None,
        "note": (
            "Template only. Enter real organizer fixture list and capture timestamp "
            "for EACH competition/day; explicitly confirm zero fixtures when applicable. "
            "Only independent human attestation can approve the gate.")
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official_inventory", nargs="?")
    p.add_argument("--prepare-template", action="store_true")
    p.add_argument("--output", required=True)
    p.add_argument("--api-snapshots-dir", default=None,
                   help="Optional stored API-Football snapshots for signed time-conflict resolution")
    args = p.parse_args()
    source = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    if args.prepare_template:
        if args.official_inventory is not None:
            p.error("--prepare-template accepts only the official-review source")
        result = inventory_template(source)
    else:
        if args.official_inventory is None:
            p.error("Provide the signed official inventory or use --prepare-template")
        snapshots = {}
        if args.api_snapshots_dir:
            for day in source.get("days", []):
                path = Path(args.api_snapshots_dir) / (day + ".json")
                if path.is_file():
                    snapshots[day] = json.loads(path.read_text(encoding="utf-8"))
        result = validate(source,
                          json.loads(Path(args.official_inventory).read_text(encoding="utf-8")),
                          third_party_snapshots=snapshots)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.prepare_template:
        print(f"KB21 manual organizer inventory template: {len(result['days'])} days; no fixtures certified")
    else:
        pending = sum(row["calendar_status"] == "BLOCKED"
                      for day in result["days"].values() for row in day["competitions"])
        print(f"KB21 calendar validation: {result['calendar_gate']} — "
              f"{pending} competition/day reviews pending, "
              f"{len(result['errors'])} detailed missing-evidence reasons; no auto-PLAY")


if __name__ == "__main__":
    main()
