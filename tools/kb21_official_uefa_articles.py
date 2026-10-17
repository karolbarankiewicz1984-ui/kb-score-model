"""Read UEFA's dated 2026/27 league-phase articles as PARTIAL fixture evidence.

An article can be corrected or a fixture postponed. The text says 'all times
CET' without a guaranteed zone for summer time, so this adapter intentionally
DOES NOT make timezone-aware kickoff claims or issue Calendar Gate approvals.
Only teams and the printed organizer-local calendar date are extracted.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from tools.kb21_official_press_fixtures import _lines

SOURCES = {
    "uefa.champions": (
        "https://www.uefa.com/uefachampionsleague/news/"
        "02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-champions-league-all-the-league-phase-fixtures-a/"
    ),
    "uefa.europa": (
        "https://www.uefa.com/uefaeuropaleague/news/"
        "02a8-2174cafa5bb6-82bbc20c9b92-1000--2026-27-europa-league-all-the-league-phase-fixtures/"
    ),
    "uefa.europa.conf": (
        "https://www.uefa.com/uefaconferenceleague/news/"
        "02a8-2174cb200f25-b94693ddff4e-1000--202627-conference-league-all-the-league-phase-fixtures/"
    ),
    "uefa.nations": (
        "https://www.uefa.com/uefanationsleague/news/"
        "02a2-1fea18abbcbc-456e846509e7-1000--2026-27-uefa-nations-league-all-the-league-phase-fixtures/"
    ),
}
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5,
    "June": 6, "July": 7, "August": 8, "September": 9, "October": 10,
    "November": 11, "December": 12,
}
DATE_RE = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"\s+(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(2026|2027)\s*$"
)
FIXTURE_RE = re.compile(r"^(.{2,85}?)\s+vs\s+(.{2,85}?)(?:\s+\((\d{1,2}:\d{2})\))?$")
MATCHDAY_RE = re.compile(r"^Matchday\s+(\d{1,2})$", re.IGNORECASE)
NATIONS_DATE_RE = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"\s+(\d{1,2})\s+(" + "|".join(MONTHS) + r")$"
)
NATIONS_FIXTURE_RE = re.compile(
    r"^([ABCD][1-4])\s+(.{2,85}?)\s+vs\s+(.{2,85}?)"
    r"(?:\s+\((\d{1,2}:\d{2})\))?$"
)
MAX_BYTES = 3_000_000


def parse(league, html):
    if league not in SOURCES:
        raise ValueError("Unsupported UEFA competition")
    if not isinstance(html, str):
        raise ValueError("Expected HTML")
    lines = _lines(html)
    is_nations = league == "uefa.nations"
    heading = ("League phase fixtures and results" if is_nations
               else "League phase fixtures by date")
    if (not any("2026/27" in x or "2026-27" in x for x in lines)
            or not any(heading in x for x in lines)):
        return [], ["OFFICIAL_LEAGUE_PHASE_HEADING_NOT_FOUND"]
    rows, errors, seen = [], [], set()
    matchday, active_day = None, None
    for line in lines:
        match = MATCHDAY_RE.fullmatch(line)
        if match:
            matchday = int(match.group(1))
            active_day = None
            continue
        if matchday is None:
            continue
        if "Selected for you" in line or line.startswith("©"):
            break
        date = (NATIONS_DATE_RE.fullmatch(line) if is_nations
                else DATE_RE.fullmatch(line))
        if date:
            try:
                if is_nations:
                    day, month = date.groups()
                    year = 2026  # source is explicitly 2026/27, league phase ends Nov 2026
                else:
                    day, month, year = date.groups()
                active_day = dt.date(int(year), MONTHS[month], int(day)).isoformat()
            except ValueError:
                errors.append("INVALID_OFFICIAL_DATE")
                active_day = None
            continue
        fixture = (NATIONS_FIXTURE_RE.fullmatch(line) if is_nations
                   else FIXTURE_RE.fullmatch(line))
        if not active_day or not fixture:
            continue
        if is_nations:
            _group, home, away, printed_time = fixture.groups()
        else:
            home, away, printed_time = fixture.groups()
        home, away = home.strip(), away.strip()
        if home.casefold() == away.casefold():
            errors.append("DUPLICATE_HOME_AWAY")
            continue
        key = (active_day, home.casefold(), away.casefold())
        if key in seen:
            errors.append("DUPLICATE_OFFICIAL_FIXTURE")
            continue
        seen.add(key)
        rows.append({
            "league_id": league, "date_printed": active_day,
            "home": home, "away": away, "matchday": matchday,
            "printed_kickoff": printed_time or (
                "20:45 (UEFA default)" if is_nations else "21:00 (UEFA default)"
            ),
            "kickoff_timezone_verified": False,
            "source_kind": ("UEFA_NATIONS_DATED_LEAGUE_PHASE_ARTICLE_PARTIAL"
                            if is_nations else "UEFA_DATED_LEAGUE_PHASE_ARTICLE_PARTIAL"),
        })
    if not rows:
        errors.append("NO_FUTURE_VS_FIXTURES_EXTRACTED")
    return rows, errors


def collect(league, days, opener=urlopen):
    if league not in SOURCES:
        raise ValueError("Unsupported UEFA competition")
    if (not isinstance(days, list) or not 1 <= len(days) <= 3
            or len(set(days)) != len(days)):
        raise ValueError("Expected 1-3 different Warsaw dates")
    days = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    source = SOURCES[league]
    rows, errors = [], []
    try:
        request = Request(source, headers={
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0 (KB21 unsigned official calendar diagnostic)",
        })
        with opener(request, timeout=20) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("UEFA article exceeds HTML limit")
        rows, errors = parse(league, payload.decode("utf-8"))
    except Exception as exc:
        errors = [f"FETCH_OR_PARSE_FAILED: {type(exc).__name__}: {exc}"]
    buckets = {day: [] for day in days}
    for row in rows:
        if row["date_printed"] in buckets:
            buckets[row["date_printed"]].append(row)
    return {
        "schema": "kb21-official-uefa-league-phase-v1", "league_id": league,
        "days": days, "by_day": buckets, "article_future_fixture_count": len(rows),
        "article_fixture_dates": sorted({row["date_printed"] for row in rows}),
        "official_url": source,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "errors": errors,
        "status": ("OFFICIAL_LEAGUE_PHASE_ARTICLE_PARTIAL_FOR_REVIEW"
                   if rows and not errors else "OFFICIAL_ARTICLE_UNVERIFIED"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "kickoff_timezone_verified": False, "reviewer_signed": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": (
            "UEFA article is for 2026/27 LEAGUE PHASE only; zero rows on a selected "
            "date NEVER confirm no UEFA fixtures. Kickoff times from CET text "
            "are not timezone-verified. This adapter only provides date/club "
            "evidence and cannot grant Calendar Gate PASS, PLAY, or write N."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True, choices=sorted(SOURCES))
    parser.add_argument("--days", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = collect(args.league, args.days)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"{args.league}: {report['status']}; "
          f"article future fixtures {report['article_future_fixture_count']}; "
          f"dates selected {sum(map(len, report['by_day'].values()))}; "
          f"errors {len(report['errors'])}; NO PLAY")


if __name__ == "__main__":
    main()
