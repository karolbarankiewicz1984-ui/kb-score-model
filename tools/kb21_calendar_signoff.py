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
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.kb21_fixture_crosscheck import _canonical, _instant
from tools.kb21_official_review import OFFICIAL_PAGES
from tools.kb21_calendar_coverage import SCOPE


def _identity(match):
    if not isinstance(match, dict):
        return None
    home, away = _canonical(match.get("home")), _canonical(match.get("away"))
    kickoff = _instant(match.get("kickoff"))
    if not home or not away or kickoff is None:
        return None
    return home, away, kickoff


def validate(queue, inventory):
    if not isinstance(queue, dict) or not isinstance(queue.get("days"), list) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue with days and fixtures")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("days"), dict):
        raise ValueError("Expected manually reviewed calendar inventory with days")
    result = {"status": "BLOCKED", "calendar_gate": "BLOCKED",
              "publication": "DIAGNOSTIC / NO PLAY", "days": {},
              "manual_source_attestation": False, "safe_to_publish_play": False}
    all_errors = []
    for day in sorted(set(queue["days"])):
        official_day = inventory["days"].get(day)
        day_errors = []
        rows = []
        league_sources = {x.get("league"): x for x in queue.get("source_status", {}).get(day, [])
                          if isinstance(x, dict)}
        for code, name in SCOPE.items():
            entry = official_day.get(code) if isinstance(official_day, dict) else None
            errors = []
            expected = [f for f in queue["fixtures"]
                        if f.get("date_warsaw") == day and f.get("fixture_id", "").split(":")[0] == code]
            if not isinstance(entry, dict):
                errors.append("MISSING_ORGANIZER_INVENTORY")
                entry = {}
            official_url = OFFICIAL_PAGES.get(code)
            if entry.get("organizer_url") != official_url or not official_url:
                errors.append("MISSING_OR_DIFFERENT_OFFICIAL_SOURCE_URL")
            captured = _instant(entry.get("captured_at"))
            if captured is None:
                errors.append("MISSING_TIMESTAMPED_ORGANIZER_CAPTURE")
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

            official_keys = [_identity(f) for f in reported]
            espn_keys = [_identity({"home": f.get("fixture", "").split(" - ", 1)[0],
                                    "away": f.get("fixture", "").split(" - ", 1)[1]
                                    if " - " in f.get("fixture", "") else "",
                                    "kickoff": f.get("kickoff")}) for f in expected]
            if any(x is None for x in official_keys + espn_keys):
                errors.append("INVALID_MATCH_IDENTITY_OR_TIMEZONE")
            else:
                if len(set(official_keys)) != len(official_keys):
                    errors.append("DUPLICATE_OFFICIAL_FIXTURE")
                remaining = list(espn_keys)
                for key in official_keys:
                    matches = [i for i, candidate in enumerate(remaining)
                               if (candidate[0:2] == key[0:2]
                                   and abs((candidate[2] - key[2]).total_seconds()) <= 300)]
                    if len(matches) != 1:
                        errors.append("MATCH_IDENTITY_OR_TIME_DISAGREEMENT")
                        break
                    remaining.pop(matches[0])
                if remaining:
                    errors.append("INDEPENDENT_MATCHES_UNEXPLAINED")
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
        result["days"][day] = {
            "status": "READY_FOR_MANUAL_APPROVAL" if not day_errors else "BLOCKED",
            "all_organizers_reviewed": not day_errors,
            "competitions": rows, "errors": day_errors,
        }
        all_errors += [f"{day}: {error}" for error in day_errors]
    if set(inventory["days"]) != set(queue["days"]):
        all_errors.append("INVENTORY_DAYS_DO_NOT_MATCH_REQUEST")
    approval = inventory.get("approval")
    signoff_ok = (
        isinstance(approval, dict)
        and isinstance(approval.get("reviewer"), str)
        and bool(approval["reviewer"].strip())
        and _instant(approval.get("approved_at")) is not None
        and approval.get("attests_independent_official_review") is True
    )
    result["ready_for_approval"] = not all_errors
    if not all_errors and signoff_ok:
        result["status"] = "MANUALLY_APPROVED_CALENDAR"
        result["calendar_gate"] = "PASS_MANUAL"
        result["manual_source_attestation"] = True
    elif not all_errors:
        result["status"] = "READY_FOR_MANUAL_APPROVAL"
    elif not signoff_ok:
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
    args = p.parse_args()
    source = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    if args.prepare_template:
        if args.official_inventory is not None:
            p.error("--prepare-template accepts only the official-review source")
        result = inventory_template(source)
    else:
        if args.official_inventory is None:
            p.error("Provide the signed official inventory or use --prepare-template")
        result = validate(source, json.loads(Path(args.official_inventory).read_text(encoding="utf-8")))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.prepare_template:
        print(f"KB21 manual organizer inventory template: {len(result['days'])} days; no fixtures certified")
    else:
        print(f"KB21 calendar validation: {result['calendar_gate']} — "
              f"{len(result['errors'])} missing/disputed official checks; no auto-PLAY")


if __name__ == "__main__":
    main()
