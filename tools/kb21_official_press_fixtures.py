"""Extract fixture evidence from two directly published organizer announcements.

Evidence is PARTIAL and ROUND-SCOPED even when every visible match is parsed.
It never signs Calendar Gate, calculates predictions, or touches historical N.

Serie A: official Lega Serie A referee assignment for matchday 7.
Ligue 1: official LFP matchday 7/8 television scheduling announcement.
These are dated announcements, not evergreen endpoints. For future dates the
status explicitly remains out-of-window until a newer official source is added.
"""
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCES = {
    "ita.1": ("https://en.legaseriea.it/serie-a/news/the-referees-for-the-7th-round-x8311",
              "Europe/Rome"),
    "fra.1": ("https://ligue1.com/fr/articles/l1_article_5797-", "Europe/Paris"),
}
MAX_BYTES = 2_000_000
EXPECTED_ARTICLE_FIXTURES = {"ita.1": 10, "fra.1": 18}
MONTHS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12,
}


class ArticleText(HTMLParser):
    """Extract visible paragraphs while discarding scripts and navigation links."""
    BREAKS = {"p", "br", "h1", "h2", "h3", "h4", "li", "tr", "section"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = []
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.suppressed.append(tag)
        if tag in self.BREAKS and not self.suppressed:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if self.suppressed and tag == self.suppressed[-1]:
            self.suppressed.pop()
        if tag in self.BREAKS and not self.suppressed:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def _lines(html):
    parser = ArticleText()
    parser.feed(html)
    return [" ".join(row.split()) for row in "".join(parser.parts).splitlines()
            if row.strip()]


ITALIAN_MATCH = re.compile(
    r"^([A-Z][A-Z .'\-]{1,55})\s+[–—-]\s+([A-Z][A-Z .'\-]{1,55})\s+"
    r"(\d{1,2})/(\d{1,2})\s+h\.\s*(\d{1,2})\.(\d{2})$"
)
FR_DATE = re.compile(
    r"^(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+"
    r"(\d{1,2})\s+([^\s]+)\s+(\d{4})\s+à\s+(\d{1,2})h(\d{2})\b",
    re.IGNORECASE,
)
FR_TEAMS = re.compile(r"^(.{2,75}?)\s+[–—]\s+(.{2,75})$")


def _record(league, home, away, local, url):
    if not home.strip() or not away.strip() or home.strip() == away.strip():
        raise ValueError("Missing or identical organizer clubs")
    local = local.replace(tzinfo=ZoneInfo(SOURCES[league][1]))
    warsaw = local.astimezone(ZoneInfo("Europe/Warsaw"))
    return {
        "league_id": league, "home": home.strip(), "away": away.strip(),
        "date_warsaw": warsaw.date().isoformat(),
        "kickoff_warsaw": warsaw.isoformat(),
        "kickoff_utc": warsaw.astimezone(dt.timezone.utc).isoformat(),
        "official_url": url, "source_kind": "DATED_ORGANIZER_PRESS_RELEASE",
    }


def parse(league, html):
    if league not in SOURCES:
        raise ValueError("Unsupported organizer")
    if not isinstance(html, str):
        raise ValueError("HTML must be text")
    url = SOURCES[league][0]
    lines = _lines(html)
    matches = []
    if league == "ita.1":
        # Only accept a Serie A referee announcement with explicit year context.
        if not any("2026/2027" in row for row in lines) or not any(
                "referees" in row.casefold() for row in lines):
            return []
        for line in lines:
            found = ITALIAN_MATCH.fullmatch(line)
            if found:
                h, a, day, month, hour, minute = found.groups()
                local = dt.datetime(2026, int(month), int(day), int(hour), int(minute))
                matches.append(_record(league, h.title(), a.title(), local, url))
    else:
        if not any("Programmations TV" in line for line in lines):
            return []
        current = None
        in_schedule = False
        for line in lines:
            if re.match(r"^\d+[eè]?\s+journée de Ligue 1", line, re.IGNORECASE):
                in_schedule = True
                current = None
                continue
            if line.startswith("Langue du site"):
                break
            if not in_schedule:
                continue
            when = FR_DATE.search(line)
            if when:
                day, month, year, hour, minute = when.groups()
                month = MONTHS.get(month.lower())
                current = (dt.datetime(int(year), month, int(day), int(hour), int(minute))
                           if month is not None else None)
                continue
            teams = FR_TEAMS.fullmatch(line)
            if current is not None and teams:
                matches.append(_record(league, teams[1], teams[2], current, url))
    # Preserve conflicting duplicated identities in diagnostics as an error.
    return matches


def collect(league, days, opener=urlopen):
    if league not in SOURCES:
        raise ValueError("Unsupported organizer")
    days = sorted(set(dt.date.fromisoformat(d).isoformat() for d in days))
    if not 1 <= len(days) <= 3:
        raise ValueError("Expected 1–3 unique days")
    url = SOURCES[league][0]
    errors, records = [], []
    try:
        request = Request(url, headers={"Accept": "text/html",
                                        "User-Agent": "Mozilla/5.0 KB21-calendar-review/1.0"})
        with opener(request, timeout=20) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("Official announcement too large")
        records = parse(league, payload.decode("utf-8"))
        if not records:
            errors.append("No parseable official match entries in dated announcement")
        if len(records) != EXPECTED_ARTICLE_FIXTURES[league]:
            errors.append(
                f"Incomplete organizer article: expected {EXPECTED_ARTICLE_FIXTURES[league]} "
                f"fixtures, parsed {len(records)}"
            )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    article_days = sorted({r["date_warsaw"] for r in records})
    selected = {d: [] for d in days}
    for row in records:
        if row["date_warsaw"] in selected:
            selected[row["date_warsaw"]].append(row)
    for rows in selected.values():
        rows.sort(key=lambda x: (x["kickoff_utc"], x["home"]))
    keys = [(r["home"], r["away"], r["kickoff_utc"]) for r in records]
    if len(keys) != len(set(keys)):
        errors.append("Duplicate organizer fixture identity")
    outside = [d for d in days if not article_days
               or d < article_days[0] or d > article_days[-1]]
    unlisted_days = [day for day in days if day not in article_days]
    return {
        "schema": "kb21-official-press-fixtures-v1", "league_id": league,
        "days": days, "official_url": url,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "article_fixture_dates": article_days, "days_outside_article_range": outside,
        "days_without_article_fixture_evidence": unlisted_days,
        "expected_article_fixture_count": EXPECTED_ARTICLE_FIXTURES[league],
        "parsed_article_fixture_count": len(records),
        "by_day": selected, "errors": errors,
        "status": ("OFFICIAL_DATED_ARTICLE_PARTIAL_FOR_REVIEW"
                   if records and not errors else "UNVERIFIED_SOURCE_OR_PARSER_ERROR"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "reviewer_signed": False, "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("Dated official announcement, not an evergreen full-season or all-round "
                 "calendar. Missing days and postponed matches never count as verified "
                 "zero. New announcements need new source review. No predictions or PLAY."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", choices=sorted(SOURCES), required=True)
    parser.add_argument("--days", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = collect(args.league, args.days)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(args.league, result["status"], "rows:",
          sum(len(rows) for rows in result["by_day"].values()),
          "errors:", len(result["errors"]), "Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
