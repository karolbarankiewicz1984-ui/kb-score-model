"""Direct unsigned Turkish Football Federation (TFF) Super Lig fixture capture.

The official site displays a selected league matchweek. It is NOT a signed
full-season or complete daily calendar. Never approve empty days or LIVE PLAY.
"""
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE = "https://www.tff.org/?pageID=198"
MAX_BYTES = 3_000_000
ISTANBUL = ZoneInfo("Europe/Istanbul")
WARSAW = ZoneInfo("Europe/Warsaw")
DATE_TIME = re.compile(
    r"^(\d{2})\.(\d{2})\.(\d{4})(?:\s+([01]?\d|2[0-3]):([0-5]\d))?$")
CLOCK = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
CLUBS = (
    "ARCA ÇORUM FK", "ÇAYKUR RİZESPOR A.Ş.", "ERZURUMSPOR FK", "EYÜPSPOR",
    "AMED SPORTİF FAALİYETLER", "TÜMOSAN KONYASPOR", "GENÇLERBİRLİĞİ",
    "GALATASARAY A.Ş.", "FENERBAHÇE A.Ş.", "CORENDON ALANYASPOR",
    "KASIMPAŞA A.Ş.", "SAMSUNSPOR A.Ş.", "KOCAELİSPOR", "GÖZTEPE A.Ş.",
    "İSTANBUL BAŞAKŞEHİR FK", "GAZİANTEP FUTBOL KULÜBÜ A.Ş.",
    "TRABZONSPOR A.Ş.", "BEŞİKTAŞ A.Ş.",
)
CLUB_LOOKUP = {" ".join(name.split()).casefold(): name for name in CLUBS}


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "head", "svg", "template"):
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, value):
        if not self.hidden:
            item = " ".join(value.split())
            if item:
                self.tokens.append(item)


def _club(tokens, index):
    for length in range(5, 0, -1):
        name = " ".join(tokens[index:index+length]).casefold()
        if name in CLUB_LOOKUP:
            return CLUB_LOOKUP[name], length
    return None, 0


def parse_html(html):
    if not isinstance(html, str):
        raise ValueError("TFF source must be HTML")
    parser = Visible()
    parser.feed(html)
    tokens = parser.tokens
    start = [i for i, part in enumerate(tokens)
             if "trendyol süper lig" in part.casefold()
             and "sezonu fikstürü" in part.casefold()]
    if not start:
        return {"heading_found": False, "fixtures": [],
                "issues": ["NO_FIRST_DIVISION_FIXTURE_HEADING"], "dates_found": []}
    i = start[-1] + 1
    dates, fixtures, issues, seen = set(), [], [], set()
    while i < len(tokens):
        item = tokens[i].casefold()
        if "sezonu puan cetveli" in item or "sezonu fikstür listesi" in item:
            break
        match = DATE_TIME.fullmatch(tokens[i])
        if not match:
            i += 1
            continue
        date = dt.date(int(match[3]), int(match[2]), int(match[1]))
        time = (int(match[4]), int(match[5])) if match[4] is not None else None
        pos = i + 1
        if time is None and pos < len(tokens):
            clock = CLOCK.fullmatch(tokens[pos])
            if clock:
                time = (int(clock[1]), int(clock[2]))
                pos += 1
        if time is None:
            issues.append("DATE_WITHOUT_TIME:" + str(date))
            i += 1
            continue
        dates.add(date.isoformat())
        pairs = []
        for home_pos in range(pos, min(pos+4, len(tokens))):
            home, count = _club(tokens, home_pos)
            if not home:
                continue
            for away_pos in range(home_pos+count, min(home_pos+count+6, len(tokens))):
                if DATE_TIME.fullmatch(tokens[away_pos]):
                    break
                away, away_count = _club(tokens, away_pos)
                if away and away != home:
                    pairs.append((home, away, away_pos+away_count))
                    break
            if pairs:
                break
        if not pairs:
            issues.append("DATE_WITHOUT_TEAM_PAIR:" + str(date))
            i = pos
            continue
        if len(pairs) > 1:
            issues.append("AMBIGUOUS_TEAM_PAIR:" + str(date))
            i = pos
            continue
        home, away, end = pairs[0]
        kickoff = dt.datetime(date.year, date.month, date.day, *time, tzinfo=ISTANBUL)
        local = kickoff.astimezone(WARSAW)
        key = (date.isoformat(), home, away)
        if key in seen:
            issues.append("DUPLICATE_GAME:" + str(key))
        else:
            seen.add(key)
            fixtures.append({
                "league_id": "tur.1", "home": home, "away": away,
                "date_warsaw": local.date().isoformat(),
                "kickoff_warsaw": local.isoformat(),
                "kickoff_utc": kickoff.astimezone(dt.timezone.utc).isoformat(),
                "official_url": SOURCE,
            })
        i = end
    return {"heading_found": True, "fixtures": fixtures, "issues": issues,
            "dates_found": sorted(dates)}


def collect(days, opener=urlopen):
    if (not isinstance(days, list) or not 1 <= len(days) <= 3
            or len(set(days)) != len(days)):
        raise ValueError("Expected 1–3 unique dates")
    days = sorted(dt.date.fromisoformat(d).isoformat() for d in days)
    errors = []
    parsed = {"heading_found": False, "fixtures": [], "dates_found": [], "issues": []}
    try:
        req = Request(SOURCE, headers={
            "Accept": "text/html", "User-Agent": "Mozilla/5.0 KB21-source-review"})
        with opener(req, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
            charset = (response.headers.get_content_charset()
                       if hasattr(response, "headers") else None)
        if len(raw) > MAX_BYTES:
            raise ValueError("Official TFF page exceeds safety cap")
        if charset and charset.lower() not in ("utf-8", "iso-8859-9", "windows-1254"):
            raise ValueError("Unsupported TFF charset: " + charset)
        parsed = parse_html(raw.decode(charset or "utf-8"))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    errors.extend(parsed["issues"])
    if not parsed["fixtures"]:
        errors.append("NO_PARSEABLE_CURRENT_TFF_MATCHWEEK")
    if parsed["fixtures"] and len(parsed["fixtures"]) != 9:
        errors.append(f"INCOMPLETE_VISIBLE_MATCHWEEK:{len(parsed['fixtures'])}/9")
    buckets = {day: [] for day in days}
    for row in parsed["fixtures"]:
        if row["date_warsaw"] in buckets:
            buckets[row["date_warsaw"]].append(row)
    for rows in buckets.values():
        rows.sort(key=lambda row: (row["kickoff_utc"], row["home"]))
    return {
        "schema": "kb21-official-tff-superlig-v1", "league_id": "tur.1",
        "official_url": SOURCE, "days": days,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "page_dates_found": parsed["dates_found"],
        "unconfirmed_zero_dates": [d for d in days if d not in parsed["dates_found"]],
        "page_fixture_count": len(parsed["fixtures"]),
        "by_day": buckets, "errors": errors,
        "status": ("OFFICIAL_TFF_MATCHWEEK_PARTIAL_FOR_REVIEW"
                   if not errors else "OFFICIAL_TFF_UNAVAILABLE_OR_INCOMPLETE"),
        "calendar_gate": "BLOCKED", "full_calendar_verified": False,
        "reviewer_signed": False, "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("TFF currently selected matchweek is not a complete day or season "
                 "catalogue. Cannot certify empty days, pre-match freeze or PLAY."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    data = collect(a.days)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf8")
    print("TFF Super Lig", sum(map(len, data["by_day"].values())),
          "scoped games;", len(data["errors"]), "errors; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
