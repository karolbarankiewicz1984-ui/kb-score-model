"""Official LaLiga matchday HTML as unsigned calendar evidence; NEVER approves PLAY."""
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://www.laliga.com/laliga-easports/resultados/{season}/jornada-{round}"
DATE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
TIME = re.compile(r"\b([01]\d|2[0-3]):([0-5]\d)\b")
MADRID, WARSAW = ZoneInfo("Europe/Madrid"), ZoneInfo("Europe/Warsaw")


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell, self.ignore = [], None, None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg"):
            self.ignore += 1
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None and not self.ignore:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg"):
            self.ignore = max(0, self.ignore - 1)
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_html(html, round, season="2026-27", days=None):
    parser = Tables()
    parser.feed(html)
    fixtures, recognized, parsed_rows = [], False, 0
    for table in parser.tables:
        if not table or not any("FECHA" in x.upper() for x in table[0]) or not any("PARTIDO" in x.upper() for x in table[0]):
            continue
        recognized = True
        for cells in table[1:]:
            date = next((m for x in cells if (m := DATE.search(x))), None)
            time = next((m for x in cells if (m := TIME.search(x))), None)
            pair = None
            for cell in cells:
                halves = re.split(r"\s+VS\s+|\s+\d{1,2}\s*-\s*\d{1,2}(?:\s+DIRECTO)?\s+", cell, maxsplit=1, flags=re.I)
                if len(halves) == 2 and all(2 <= len(h.strip()) <= 85 for h in halves):
                    pair = [h.strip() for h in halves]
                    break
            if not date or not time or not pair:
                continue
            local = dt.datetime(int(date[3]), int(date[2]), int(date[1]), int(time[1]), int(time[2]), tzinfo=MADRID)
            warsaw = local.astimezone(WARSAW)
            parsed_rows += 1
            day = warsaw.date().isoformat()
            if days is not None and day not in days:
                continue
            fixtures.append({"league_id": "esp.1", "round": round, "home": pair[0], "away": pair[1],
                             "date_warsaw": day, "kickoff_warsaw": warsaw.isoformat(),
                             "kickoff_utc": warsaw.astimezone(dt.timezone.utc).isoformat(),
                             "official_url": URL.format(season=season, round=round)})
    return {"table_recognized": recognized, "parsed_rows": parsed_rows, "fixtures": fixtures}


def collect(days, rounds=None, opener=urlopen):
    days = sorted(set(dt.date.fromisoformat(day).isoformat() for day in days))
    if not 1 <= len(days) <= 3:
        raise ValueError("Select 1-3 dates")
    first = dt.date.fromisoformat(days[0])
    startyear = first.year if first.month >= 8 else first.year - 1
    season = f"{startyear}-{(startyear + 1) % 100:02}"
    estimate = 1 + max(0, (first - dt.date(startyear, 8, 22)).days // 7)
    rounds = sorted(set(rounds if rounds is not None else range(max(1, estimate-3), min(38, estimate+3)+1)))
    if not 1 <= len(rounds) <= 12 or any(not isinstance(r, int) or isinstance(r, bool) or r < 1 or r > 38 for r in rounds):
        raise ValueError("Invalid 1-12 matchday scan")
    by_day, sources, errors, seen = {day: [] for day in days}, [], [], set()
    for round in rounds:
        url = URL.format(season=season, round=round)
        try:
            req = Request(url, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"})
            with opener(req, timeout=15) as response:
                raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError("Organizer page too large")
            parsed = parse_html(raw.decode("utf-8"), round, season, days)
            status = "PARSED_MATCHDAY" if parsed["table_recognized"] and parsed["parsed_rows"] else "UNREADABLE_OR_EMPTY_MATCHDAY"
            if status != "PARSED_MATCHDAY":
                errors.append({"url": url, "reason": "No parseable official fixture table"})
            for row in parsed["fixtures"]:
                key = (row["home"], row["away"], row["kickoff_utc"])
                if key not in seen:
                    seen.add(key)
                    by_day[row["date_warsaw"]].append(row)
            sources.append({"round": round, "url": url, "status": status, "parsed_rows": parsed["parsed_rows"]})
        except Exception as exc:
            errors.append({"url": url, "reason": f"{type(exc).__name__}: {exc}"})
            sources.append({"round": round, "url": url, "status": "FETCH_ERROR"})
    for rows in by_day.values():
        rows.sort(key=lambda r: (r["kickoff_utc"], r["home"]))
    return {"schema": "kb21-official-laliga-matchday-html-v1", "league_id": "esp.1",
            "days": days, "season": season, "rounds_scanned": rounds,
            "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sources": sources, "errors": errors, "by_day": by_day,
            "status": "OFFICIAL_PARTIAL_MATCHDAY_WINDOW_FOR_REVIEW" if any(by_day.values()) else "NO_USABLE_OFFICIAL_MATCHES",
            "calendar_gate": "BLOCKED", "full_calendar_verified": False,
            "reviewer_signed": False, "publication": "DIAGNOSTIC / NO PLAY",
            "note": "Only a sample of LaLiga organizer matchdays. Missing dates and postponed matches are NOT proof of no games. This is not the complete human-signed Calendar Gate."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--matchdays", nargs="+", type=int)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    report = collect(args.days, args.matchdays)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Official LaLiga:", sum(map(len, report["by_day"].values())), "fixtures,",
          len(report["errors"]), "source errors; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
