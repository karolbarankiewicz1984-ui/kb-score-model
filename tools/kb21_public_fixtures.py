"""Fetch a public football fixture feed as UNVERIFIED candidate data.

No API key, no xG, no paid source. A third-party feed is NOT an official
competition calendar. Output must never pass Calendar Gate automatically.
Usage: python -m tools.kb21_public_fixtures 2026-10-16 --output reports/kb21_legacy/public-fixtures.json
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

FEED = "https://www.espn.com/soccer/scoreboard/_/date/{date}"


def fetch(date):
    # HTML source discovery only. Do not parse dynamic site markup into invented matches.
    datetime.strptime(date, "%Y-%m-%d")
    url = FEED.format(date=date.replace("-", ""))
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 KB21-calendar-audit/1.0"})
    with urlopen(request, timeout=20) as response:
        body = response.read(2_000_000).decode("utf-8", errors="replace")
        status = response.status
    return {"date": date, "retrieved_at": datetime.now(ZoneInfo("Europe/Warsaw")).isoformat(),
            "source_url": url, "http_status": status, "bytes_received": len(body),
            "status": "UNVERIFIED_SOURCE_ONLY", "fixtures": [],
            "reason": "Page reachable does not prove fixture extraction or full calendar coverage. Official competition sources and independent match-by-match comparison still required."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        data = fetch(args.date)
    except Exception as exc:
        data = {"date": args.date, "status": "SOURCE_UNAVAILABLE", "fixtures": [],
                "error": f"{type(exc).__name__}: {exc}"}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(data["status"])


if __name__ == "__main__":
    main()
