"""Fail-closed freshness gate for CURRENT MultiModel PDF recommendations.

Historical replay is a separate, explicitly named artifact and must never be
silently promoted to today's bookmaker-facing recommendations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
MAX_AGE = timedelta(hours=6)
MIN_LEAD = timedelta(minutes=5)


class StaleReportError(ValueError):
    """Source snapshot or requested matches are not eligible for today's report."""


def aware(value, label):
    if not isinstance(value, str):
        raise StaleReportError(label + "_missing")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StaleReportError(label + "_invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise StaleReportError(label + "_missing_timezone")
    return result.astimezone(timezone.utc)


def current_window(queue, market, *, now_utc=None):
    """Return only match IDs whose kickoffs remain safely in the future.

    Both source timestamps must belong to the same Warsaw calendar day as
    publication and must be within six hours. No old successful CI run can
    substitute for a new daily source. All time checks are offset-aware.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise StaleReportError("publication_time_missing_timezone")
    now = now.astimezone(timezone.utc)
    today = now.astimezone(WARSAW).date().isoformat()
    if not isinstance(queue, dict) or not isinstance(market, dict):
        raise StaleReportError("invalid_source_documents")
    generated = aware(queue.get("generated_at_utc"), "queue_generated_at_utc")
    quoted = aware(market.get("as_of_utc"), "market_as_of_utc")
    for name, source in (("queue", generated), ("market", quoted)):
        if source > now:
            raise StaleReportError(name + "_from_future")
        if source.astimezone(WARSAW).date().isoformat() != today:
            raise StaleReportError(name + "_not_today_warsaw")
        if now - source > MAX_AGE:
            raise StaleReportError(name + "_too_old")
    if quoted < generated:
        raise StaleReportError("odds_snapshot_before_queue")

    fixtures = queue.get("fixtures")
    if not isinstance(fixtures, list):
        raise StaleReportError("invalid_fixture_queue")
    available, excluded, seen = [], 0, set()
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not fixture.get("fixture_id"):
            raise StaleReportError("invalid_fixture_identity")
        fid = str(fixture["fixture_id"])
        if fid in seen:
            raise StaleReportError("duplicate_fixture_id")
        seen.add(fid)
        kickoff = aware(fixture.get("kickoff_utc"), "fixture_kickoff_utc")
        if kickoff.astimezone(WARSAW).date().isoformat() != today:
            continue
        if kickoff <= now + MIN_LEAD:
            excluded += 1
            continue
        available.append((fid, kickoff))
    if not available:
        raise StaleReportError("no_upcoming_fixtures_today")
    return {
        "schema": "multimodel-current-report-window-v1",
        "status": "CURRENT_VALIDATED",
        "day": today,
        "checked_at_utc": now.isoformat(),
        "queue_generated_at_utc": generated.isoformat(),
        "market_as_of_utc": quoted.isoformat(),
        "eligible_fixture_ids": [fid for fid, _ in available],
        "eligible_fixtures": len(available),
        "started_or_too_close": excluded,
        "earliest_kickoff_utc": min(dt for _, dt in available).isoformat(),
        "max_source_age_hours": MAX_AGE.total_seconds() / 3600,
        "min_lead_minutes": int(MIN_LEAD.total_seconds() / 60),
    }


def still_publishable(window, *, now_utc=None):
    """Reject a composed report if midnight or kickoffs passed during rendering."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise StaleReportError("publication_time_missing_timezone")
    now = now.astimezone(timezone.utc)
    if now.astimezone(WARSAW).date().isoformat() != window.get("day"):
        raise StaleReportError("day_changed_during_pdf_generation")
    if aware(window.get("earliest_kickoff_utc"), "earliest_kickoff_utc") <= now + MIN_LEAD:
        raise StaleReportError("kickoff_too_close_for_publication")
    if now - aware(window.get("queue_generated_at_utc"), "queue_generated_at_utc") > MAX_AGE:
        raise StaleReportError("queue_expired_during_pdf_generation")
    if now - aware(window.get("market_as_of_utc"), "market_as_of_utc") > MAX_AGE:
        raise StaleReportError("odds_expired_during_pdf_generation")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
        market = json.loads(Path(args.market).read_text(encoding="utf-8"))
        window = current_window(queue, market)
        if args.day != window["day"]:
            raise StaleReportError("requested_day_not_today")
    except (OSError, ValueError) as exc:
        print("::error::MULTIMODEL_CURRENT_PDF_BLOCKED: " + str(exc))
        print("An old PDF was NOT published as current recommendations.")
        raise SystemExit(2) from exc
    if args.output:
        Path(args.output).write_text(json.dumps(window, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    print("MULTIMODEL_CURRENT_PDF_OK " + json.dumps(
        {k: window[k] for k in ("day", "eligible_fixtures", "started_or_too_close")},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
