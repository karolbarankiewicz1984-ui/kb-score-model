"""Official UEFA 2026 World Cup European Qualifiers CYCLE status, NOT fixtures.

The organizer says this historical 2026 WC qualification edition concluded
on 2026-03-31. Do NOT infer that other European Qualifiers editions, friendlies,
or postponed matches cannot exist. Even for an out-of-edition day, zero games
needs an independently signed day-specific organizer inventory. No auto-PASS.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.request import Request, urlopen

from tools.kb21_official_press_fixtures import _lines

SOURCE = (
    "https://www.uefa.com/european-qualifiers/news/"
    "0294-1c916a81655d-47c1bac26fb9-1000--/"
)
EDITION = "FIFA_WORLD_CUP_2026_EUROPEAN_QUALIFIERS"
LAST_FINAL_DAY = dt.date(2026, 3, 31)
MAX_BYTES = 3_000_000

MARKERS = (
    "European Qualifiers for 2026 World Cup: All the results",
    "European Qualifiers for the 2026 FIFA World Cup ran from March to November 2025",
    "play-offs for the remaining finals places taking place in March 2026",
    "Tuesday 31 March 2026",
    "Play-off finals",
)


def parse(html):
    if not isinstance(html, str):
        raise ValueError("Official UEFA article must be HTML text")
    page = "\n".join(_lines(html))
    missing = [text for text in MARKERS if text.casefold() not in page.casefold()]
    if missing:
        return False, ["HISTORICAL_2026_CYCLE_EVIDENCE_INCOMPLETE"]
    return True, []


def collect(days, opener=urlopen):
    if (not isinstance(days, list) or not 1 <= len(days) <= 3
            or len(set(days)) != len(days)):
        raise ValueError("Expected 1-3 distinct calendar dates")
    requested = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    source_ok, errors = False, []
    try:
        req = Request(SOURCE, headers={
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0 (KB21 calendar diagnostic, no automatic signoff)",
        })
        with opener(req, timeout=20) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("UEFA article larger than safety limit")
        source_ok, errors = parse(payload.decode("utf-8"))
    except Exception as exc:
        errors = [f"UEFA_CYCLE_SOURCE_UNAVAILABLE: {type(exc).__name__}: {exc}"]
    statuses = {
        day: ("AFTER_DOCUMENTED_WORLD_CUP_2026_QUALIFICATION_CYCLE"
              if source_ok and dt.date.fromisoformat(day) > LAST_FINAL_DAY
              else "HISTORICAL_CYCLE_DOCUMENTED_BUT_DAY_NOT_ATTESTED"
              if source_ok else "ORGANIZER_CYCLE_SOURCE_UNVERIFIED")
        for day in requested
    }
    return {
        "schema": "kb21-official-uefa-2026-qualifiers-cycle-v1",
        "league_id": "fifa.worldq.uefa", "edition": EDITION,
        "days": requested, "official_url": SOURCE,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "documented_last_playoff_day": LAST_FINAL_DAY.isoformat() if source_ok else None,
        "by_day": {day: [] for day in requested},
        "day_cycle_status": statuses,
        "errors": errors,
        "status": ("DOCUMENTED_HISTORICAL_CYCLE_ONLY" if source_ok
                   else "OFFICIAL_CYCLE_SOURCE_UNVERIFIED"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "date_verified": False, "kickoff_timezone_verified": False,
        "reviewer_signed": False, "confirmed_zero_matches": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": (
            "UEFA 2026 World Cup qualifiers historical cycle evidence only. "
            "The last play-off was 2026-03-31, but this does NOT certify "
            "zero matches on any requested date, another edition or all "
            "postponements. A candidate after that date needs edition review. "
            "Manual full-day organizer checking remains required before PASS."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    report = collect(a.days)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"UEFA 2026 European Qualifiers cycle: {report['status']}; "
          f"last official playoff {report['documented_last_playoff_day']}; "
          f"errors {report['errors']}; Calendar Gate BLOCKED / NO PLAY")


if __name__ == "__main__":
    main()
