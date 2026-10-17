"""Unsigned, conservative KNVB Eredivisie fixture capture.

KNVB runs the competition, but a public page does not certify all postponed
games or approve the full daily KB21 calendar. No key, paid API or N writes.
"""
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE = "https://www.knvb.nl/competities/eredivisie/programma"
MONTHS = {name: i for i, name in enumerate((
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december"), 1)}
DUTCH_DAY = r"(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)"
DATE_PATTERN = re.compile(
    rf"^{DUTCH_DAY}\s+(\d{{1,2}})\s+({'|'.join(MONTHS)})\s+(\d{{4}})$", re.I)
TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_BYTES = 3_000_000
AMSTERDAM = ZoneInfo("Europe/Amsterdam")
WARSAW = ZoneInfo("Europe/Warsaw")
# Explicit season 2026/27 top-division club identities from the KNVB schedule.
# This protects against interpreting unrelated page navigation as a fixture.
CLUBS = (
    "ADO Den Haag", "PSV", "Telstar", "Feyenoord", "Sparta Rotterdam",
    "Willem II", "PEC Zwolle", "Go Ahead Eagles", "SC Cambuur", "AZ",
    "FC Groningen", "Ajax", "N.E.C.", "Fortuna Sittard", "FC Twente",
    "FC Utrecht", "Excelsior", "Excelsior Rotterdam", "sc Heerenveen",
)
CLUB_LOOKUP = {re.sub(r"\s+", " ", name).casefold(): name for name in CLUBS}


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "head", "template"):
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data):
        if not self.hidden:
            item = " ".join(data.split())
            if item:
                self.tokens.append(item)


def _date(tokens, i):
    for count in range(1, 5):
        match = DATE_PATTERN.fullmatch(" ".join(tokens[i:i+count]))
        if match:
            day, month, year = match.groups()
            return dt.date(int(year), MONTHS[month.casefold()], int(day)), count
    return None, 0


def _club(tokens, i):
    for count in range(4, 0, -1):
        phrase = " ".join(tokens[i:i+count]).casefold()
        if phrase in CLUB_LOOKUP:
            return CLUB_LOOKUP[phrase], count
    return None, 0


def parse_html(html):
    if not isinstance(html, str):
        raise ValueError("KNVB page must be HTML text")
    parser = VisibleText()
    parser.feed(html)
    tokens = parser.tokens
    starts = [i for i, item in enumerate(tokens)
              if item.casefold() == "programma eredivisie"]
    if not starts:
        return {"heading_found": False, "dates_found": [],
                "fixtures": [], "issues": ["MISSING_PROGRAM_HEADING"]}
    i = starts[-1] + 1
    date = None
    dates = set()
    fixtures, issues, seen = [], [], set()
    while i < len(tokens):
        new_date, used = _date(tokens, i)
        if used:
            date = new_date
            dates.add(new_date.isoformat())
            i += used
            continue
        if date is None:
            i += 1
            continue
        home, hc = _club(tokens, i)
        if home is None:
            i += 1
            continue
        found = None
        for time_pos in range(i+hc, min(i+hc+5, len(tokens))):
            clock = TIME_PATTERN.fullmatch(tokens[time_pos])
            if not clock:
                continue
            for away_pos in range(time_pos+1, min(time_pos+5, len(tokens))):
                away, ac = _club(tokens, away_pos)
                if away and away != home:
                    found = (clock, away, away_pos+ac)
                    break
            if found:
                break
        if found:
            clock, away, next_idx = found
            instant = dt.datetime(date.year, date.month, date.day,
                                  int(clock[1]), int(clock[2]), tzinfo=AMSTERDAM)
            local = instant.astimezone(WARSAW)
            key = (date.isoformat(), home, away, instant.isoformat())
            if key in seen:
                issues.append(f"DUPLICATE_OFFICIAL_PAIR:{home}/{away}/{date}")
            else:
                seen.add(key)
                fixtures.append({
                    "league_id": "ned.1", "home": home, "away": away,
                    "kickoff_warsaw": local.isoformat(),
                    "kickoff_utc": instant.astimezone(dt.timezone.utc).isoformat(),
                    "date_warsaw": local.date().isoformat(),
                    "official_url": SOURCE,
                })
            i = next_idx
        else:
            i += hc
    return {"heading_found": True, "dates_found": sorted(dates),
            "fixtures": fixtures, "issues": issues}


def collect(days, opener=urlopen):
    if not isinstance(days, list) or not 1 <= len(days) <= 3 or len(set(days)) != len(days):
        raise ValueError("Expected 1–3 unique dates")
    days = sorted(dt.date.fromisoformat(d).isoformat() for d in days)
    errors = []
    parsed = {"heading_found": False, "dates_found": [], "fixtures": [], "issues": []}
    try:
        req = Request(SOURCE, headers={
            "User-Agent": "Mozilla/5.0 KB21 calendar audit", "Accept": "text/html"})
        with opener(req, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("KNVB page exceeds response safety cap")
        parsed = parse_html(raw.decode("utf-8"))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    errors.extend(parsed["issues"])
    if not parsed["fixtures"]:
        errors.append("NO_PARSEABLE_KNVB_FIXTURES")
    buckets = {day: [] for day in days}
    for event in parsed["fixtures"]:
        if event["date_warsaw"] in buckets:
            buckets[event["date_warsaw"]].append(event)
    for rows in buckets.values():
        rows.sort(key=lambda row: (row["kickoff_utc"], row["home"]))
    uncovered = [day for day in days if day not in parsed["dates_found"]]
    return {
        "schema": "kb21-official-knvb-eredivisie-v1", "league_id": "ned.1",
        "official_url": SOURCE, "days": days,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "page_dates_found": parsed["dates_found"],
        "page_fixture_count": len(parsed["fixtures"]),
        "unconfirmed_zero_dates": uncovered,
        "by_day": buckets, "errors": errors,
        "status": ("OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW"
                   if parsed["fixtures"] and not errors
                   else "OFFICIAL_KNVB_UNAVAILABLE_OR_UNREADABLE"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "reviewer_signed": False, "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("KNVB public fixture list may omit postponed or unannounced games. "
                 "A missing date never proves zero league matches. "
                 "No sporting score, human signoff, historical N or PLAY."),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="+", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = collect(args.days)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"KNVB Eredivisie {sum(map(len, data['by_day'].values()))} scoped games / "
          f"{data['page_fixture_count']} visible; {len(data['errors'])} errors; "
          "Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
