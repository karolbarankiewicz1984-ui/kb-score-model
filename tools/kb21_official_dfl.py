"""Extract dated Bundesliga fixture table from organizer-owned Bundesliga Media.

Uses the publicly published DFL/Bundesliga Media table with explicit UTC
kickoff column, NOT local 'CET' text which may mean CEST in October.
Default website often shows ONLY the selected matchday, so this snapshot can
NEVER certify an empty day or a complete season by itself. Diagnostic only.
"""
import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = "https://products.bundesliga.com/fixtures"
MAX_HTML = 2_500_000
WARSAW = ZoneInfo("Europe/Warsaw")


class MatchTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []
        elif tag in ("th", "td") and self.current_row is not None:
            self.current_cell = []

    def handle_data(self, text):
        if self.current_cell is not None:
            self.current_cell.append(text)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.current_row is not None and self.current_cell is not None:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None
            self.current_cell = None


def parse_table(html):
    if not isinstance(html, str):
        raise ValueError("Official DFL HTML must be text")
    parser = MatchTable()
    parser.feed(html)
    records = []
    headers_found = False
    invalid_rows = []
    seen = set()
    for row in parser.rows:
        low = [r.casefold() for r in row]
        if "matchday" in low and "home team" in low and "away team" in low:
            headers_found = True
            continue
        if not row or not re.fullmatch(r"\d{1,2}", row[0]):
            continue
        if len(row) < 8:
            invalid_rows.append({"reason": "INCOMPLETE_CELLS", "row": row[:9]})
            continue
        try:
            matchday = int(row[0])
            fixture_date = dt.datetime.strptime(row[2], "%d-%b-%Y").date()
            time_utc = dt.time.fromisoformat(row[4])
            kickoff = dt.datetime.combine(fixture_date, time_utc, dt.timezone.utc)
        except (ValueError, TypeError):
            invalid_rows.append({"reason": "INVALID_DATE_OR_UTC", "row": row[:9]})
            continue
        if not 1 <= matchday <= 34 or not row[5] or not row[6]:
            invalid_rows.append({"reason": "INVALID_MATCHDAY_OR_TEAMS", "row": row[:9]})
            continue
        key = (row[5], row[6], kickoff)
        if key in seen:
            invalid_rows.append({"reason": "DUPLICATE_FIXTURE", "row": row[:9]})
            continue
        seen.add(key)
        records.append({
            "league_id": "ger.1",
            "matchday": matchday,
            "home": row[5], "away": row[6],
            "kickoff_utc": kickoff.isoformat(),
            "kickoff_warsaw": kickoff.astimezone(WARSAW).isoformat(),
            "date_warsaw": kickoff.astimezone(WARSAW).date().isoformat(),
            "official_utc_cell": row[4],
            "media_edition_match_type": row[7],
            "organizer_source": SOURCE,
        })
    return {
        "headers_found": headers_found,
        "structure_diagnostics": {
            "html_chars": len(html),
            "literal_tr_count": html.lower().count("<tr"),
            "literal_table_count": html.lower().count("<table"),
            "html_contains_team_name": "Hamburger SV" in html,
            "html_contains_fixture_heading": "Matchday" in html,
            "html_contains_next_js_data": "__NEXT_DATA__" in html or "__next_f" in html,
        },
        "extracted_match_count": len(records),
        "invalid_rows": invalid_rows[:25],
        "fixtures": records,
    }


def convert(html, days, captured_at=None):
    if not isinstance(days, list) or not 1 <= len(days) <= 3 or len(set(days)) != len(days):
        raise ValueError("Expected 1–3 unique Warsaw dates")
    target = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    stamp = captured_at or dt.datetime.now(dt.timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Timestamp missing UTC offset")
    parsed = parse_table(html)
    buckets = {day: [] for day in target}
    for fixture in parsed["fixtures"]:
        day = fixture["date_warsaw"]
        if day in buckets:
            buckets[day].append(fixture)
    for day in buckets:
        buckets[day].sort(key=lambda f: (f["kickoff_utc"], f["home"]))
    return {
        "schema": "kb21-official-bundesliga-media-v1",
        "official_organizer": "Bundesliga Media / DFL",
        "official_url": SOURCE,
        "captured_at_utc": stamp.astimezone(dt.timezone.utc).isoformat(),
        "days": target,
        "league_id": "ger.1",
        "table_headers_detected": parsed["headers_found"],
        "structure_diagnostics": parsed["structure_diagnostics"],
        "page_fixture_rows": parsed["extracted_match_count"],
        "page_invalid_row_count": len(parsed["invalid_rows"]),
        "invalid_row_examples": parsed["invalid_rows"],
        "page_matchdays": sorted({f["matchday"] for f in parsed["fixtures"]}),
        "by_day": buckets,
        "status": ("OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW"
                   if parsed["headers_found"] and parsed["fixtures"] and not parsed["invalid_rows"]
                   else "OFFICIAL_TABLE_UNUSABLE_OR_INCOMPLETE"),
        "full_season_coverage_verified": False,
        "full_day_coverage_verified": False,
        "calendar_gate": "BLOCKED",
        "reviewer_signed": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": (
            "Official Bundesliga Media matchday table with UTC kickoff timestamps; "
            "page can show only the currently selected matchday and misses postponed "
            "matches elsewhere. A day with zero rows cannot prove no Bundesliga games. "
            "No Calendar Gate PASS or automatic betting PLAY.")
    }


def fetch(days, opener=urllib.request.urlopen, captured_at=None):
    req = urllib.request.Request(
        SOURCE, headers={"Accept": "text/html",
                         "User-Agent": "KBScore21CalendarAudit/1.0 (public DFL fixtures only)"})
    try:
        with opener(req, timeout=20) as response:
            body = response.read(MAX_HTML + 1)
            if len(body) > MAX_HTML:
                raise ValueError("Official matchday HTML exceeds safety limit")
            text = body.decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DFL matchday HTTP {exc.code}") from exc
    return convert(text, days, captured_at=captured_at)


def render(data):
    lines = [
        "# KB Score 2.1 — terminarz oficjalnego serwisu Bundesligi",
        "", "**Calendar Gate BLOCKED / NO PLAY**",
        f"Źródło: {SOURCE}", f"Odnotowano: {data['captured_at_utc']}",
        f"Wiersze odczytane: {data['page_fixture_rows']}; "
        f"stan: {data['status']}; kolejki: {data['page_matchdays']}",
        "", "| Dzień PL | Godzina PL | Gospodarze | Goście | Kolejka |",
        "|---|---|---|---|---:|",
    ]
    for day, rows in sorted(data["by_day"].items()):
        for f in rows:
            time = dt.datetime.fromisoformat(f["kickoff_warsaw"]).strftime("%H:%M")
            lines.append(f"| {day} | {time} | {f['home']} | {f['away']} | {f['matchday']} |")
    lines += ["", "UWAGA: strona może ograniczać się do jednej kolejki. "
              "Brak rekordu nie dowodzi braku meczu; przed PASS_MANUAL "
              "potrzebna pełna kontrola oficjalnego terminarza.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    result = fetch(args.days)
    for name, content in (
        (args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(result)),
    ):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Official DFL page: {result['page_fixture_rows']} rows, "
          f"{sum(len(x) for x in result['by_day'].values())} within requested scope, "
          f"status={result['status']}; structure={result['structure_diagnostics']}; "
          f"CALENDAR BLOCKED")


if __name__ == "__main__":
    main()
