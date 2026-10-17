"""Unsigned Belgium Jupiler Pro League current-round fixture evidence.

The organizer page provides a currently selected round, often without a date,
kickoff or season on each fixture. Such rows CANNOT be assigned to a Warsaw day.
A team-pair coincidence is NEVER a verified fixture calendar or zero-game day.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from tools.kb21_official_press_fixtures import _lines

SOURCE = "https://www.proleague.be/jpl-kalender"
MAX_HTML = 3_000_000
ROUND_MARK = re.compile(r"^Jupiler Pro League\s*[·•]\s*S(\d{1,2})$", re.I)


def parse(html):
    if not isinstance(html, str):
        raise ValueError("Expected organizer HTML")
    rows, errors = [], []
    lines = _lines(html)
    if not any("Jupiler Pro League" in line for line in lines):
        return [], ["JPL_PAGE_HEADING_MISSING"]
    rounds = set()
    for i, line in enumerate(lines):
        mark = ROUND_MARK.fullmatch(line)
        if not mark:
            continue
        if i + 2 >= len(lines):
            errors.append("INCOMPLETE_ROUND_CARD")
            continue
        home, away = lines[i + 1].strip(), lines[i + 2].strip()
        if (not home or not away or home.casefold() == away.casefold()
                or len(home) > 90 or len(away) > 90
                or ROUND_MARK.fullmatch(home) or ROUND_MARK.fullmatch(away)):
            errors.append("INVALID_ROUND_CLUB_PAIR")
            continue
        round_no = int(mark.group(1))
        rounds.add(round_no)
        rows.append({
            "home": home, "away": away, "selected_round": round_no,
            "date_warsaw": None, "kickoff_warsaw": None,
            "source_kind": "ORGANIZER_VISIBLE_SELECTED_ROUND_NO_DATES",
            "kickoff_timezone_verified": False,
        })
    keys = [(row["selected_round"], row["home"].casefold(), row["away"].casefold())
            for row in rows]
    if len(keys) != len(set(keys)):
        errors.append("DUPLICATE_SELECTED_ROUND_FIXTURE")
    if len(rounds) > 1:
        errors.append("MULTIPLE_SELECTED_ROUNDS_UNVERIFIED")
    if not rows:
        errors.append("NO_VISIBLE_FIXTURES_IN_SELECTED_ROUND")
    return rows, sorted(set(errors))


def collect(days, opener=urlopen):
    if (not isinstance(days, list) or not 1 <= len(days) <= 3
            or len(set(days)) != len(days)):
        raise ValueError("Expected 1-3 distinct Warsaw dates")
    days = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    rows, errors = [], []
    try:
        req = Request(SOURCE, headers={
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0 (KB21 unsigned organizer source audit)",
        })
        with opener(req, timeout=20) as response:
            payload = response.read(MAX_HTML + 1)
        if len(payload) > MAX_HTML:
            raise ValueError("JPL HTML exceeds maximum size")
        rows, errors = parse(payload.decode("utf-8"))
    except Exception as exc:
        errors = [f"FETCH_OR_PARSE_FAILED: {type(exc).__name__}: {exc}"]
    return {
        "schema": "kb21-official-belgium-selected-round-v1",
        "league_id": "bel.1", "days": days, "official_url": SOURCE,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "undated_fixtures": rows,
        # Empty by-day buckets mean DATE UNKNOWN, never verified zero.
        "by_day": {d: [] for d in days},
        "selected_rounds": sorted({row["selected_round"] for row in rows}),
        "errors": errors,
        "status": ("OFFICIAL_SELECTED_ROUND_UNDATED_FOR_REVIEW"
                   if rows and not errors else "UNVERIFIED_SELECTED_ROUND_SOURCE"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "kickoff_timezone_verified": False, "date_verified": False,
        "reviewer_signed": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("JPL organizer's visible current round has no reliably verified "
                 "date or timezone in this adapter. Selected round is not the "
                 "complete season/calendar, and an empty day is NOT a verified "
                 "zero. Never sign calendar, infer match dates or publish PLAY."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    report = collect(a.days)
    file = Path(a.output)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"Belgium JPL official selected rounds: {report['selected_rounds']}; "
          f"visible undated games: {len(report['undated_fixtures'])}; "
          f"errors: {len(report['errors'])}; no dates approved; CALENDAR BLOCKED")


if __name__ == "__main__":
    main()
