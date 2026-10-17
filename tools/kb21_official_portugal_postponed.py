"""Official club evidence for one postponed Portuguese league fixture.

Gil Vicente publishes a dated *local-time* kickoff announcement for the
2026-10-19 SC Braga–Gil Vicente match. The SC Braga site separately displays
a kickoff clock without specifying its timezone. NEVER silently interpret that
display as Lisbon-local time or label two clocks a confirmed time conflict.

This is one club fixture, NOT a complete Portuguese league calendar.
No API key, xG, Sport Score, LIVE PLAY, signoff or historical N writes.
"""
import argparse
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GIL_NEWS = "https://gilvicentefc.pt/data-e-hora-do-jogo-em-atraso-com-o-sc-braga/"
BRAGA_PROGRAM = "https://scbraga.pt/"
MAX_BYTES = 3_000_000
LISBON = ZoneInfo("Europe/Lisbon")
WARSAW = ZoneInfo("Europe/Warsaw")


class Readable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "head", "template"):
            self.skip.append(tag)
        elif tag in ("p", "div", "section", "article", "h1", "h2", "h3", "br", "li"):
            if not self.skip:
                self.parts.append(" ")
    def handle_endtag(self, tag):
        if self.skip and self.skip[-1] == tag:
            self.skip.pop()
        elif tag in ("p", "div", "section", "article", "h1", "h2", "h3", "br", "li"):
            if not self.skip:
                self.parts.append(" ")
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _text(html):
    if not isinstance(html, str):
        raise ValueError("Club website must be text")
    parser = Readable()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def parse_gil_article(html):
    """Dated October 2026 reschedule confirmation, NOT a reusable feed."""
    text = _text(html)
    head = re.search(r"DATA E HORA DO JOGO EM ATRASO COM O SC BRAGA", text, re.I)
    if not head:
        return None
    # Limit to its actual article, not unrelated forthcoming fixtures.
    block = text[head.end():head.end()+1000]
    if not re.search(r"Outubro\s+1,\s*2026", block, re.I):
        return None
    confirmation = re.search(
        r"O jogo em atraso da jornada dois na Liga Portugal,.{0,240}?"
        r"19 de outubro no Estádio Municipal de Braga\."
        r".{0,90}?20h15", block, re.I
    )
    if not confirmation or not all(re.search(name, confirmation[0], re.I)
                                    for name in ("Gil Vicente FC", "SC Braga")):
        return None
    kickoff = dt.datetime(2026, 10, 19, 20, 15, tzinfo=LISBON)
    return {
        "home": "SC Braga", "away": "Gil Vicente FC",
        "date_warsaw": kickoff.astimezone(WARSAW).date().isoformat(),
        "kickoff_warsaw": kickoff.astimezone(WARSAW).isoformat(),
        "kickoff_utc": kickoff.astimezone(dt.timezone.utc).isoformat(),
        "gil_local_clock": "20:15", "gil_timezone": "Europe/Lisbon",
        "source_url": GIL_NEWS, "article_published": "2026-10-01",
        "evidence_type": "OFFICIAL_GIL_VICENTE_DATED_ARTICLE",
    }


def parse_braga_display(html):
    """Extract raw visible kickoff clock; timezone deliberately unresolved."""
    text = _text(html)
    match = re.search(
        r"SC Braga vs Gil Vicente FC.{0,200}?"
        r"Oct\s+19,\s*2026,\s*([01]?\d|2[0-3]):([0-5]\d)", text, re.I
    )
    if not match:
        return None
    return {"home": "SC Braga", "away": "Gil Vicente FC", "day": "2026-10-19",
            "display_clock": f"{int(match[1]):02}:{match[2]}",
            "display_timezone": None, "timezone_known": False,
            "source_url": BRAGA_PROGRAM}


def _fetch(url, opener):
    if url not in (GIL_NEWS, BRAGA_PROGRAM):
        raise ValueError("Unapproved club URL")
    req = Request(url, headers={"Accept": "text/html",
                                "User-Agent": "Mozilla/5.0 KB21-fixture-source-review"})
    with opener(req, timeout=20) as response:
        raw = response.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Club website response too large")
    return raw.decode("utf-8")


def collect(days, opener=urlopen):
    if not isinstance(days, list) or not 1 <= len(days) <= 3 or len(set(days)) != len(days):
        raise ValueError("Expected 1–3 unique dates")
    days = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    errors, gil, braga = [], None, None
    try:
        gil = parse_gil_article(_fetch(GIL_NEWS, opener))
        if gil is None:
            errors.append("GIL_OFFICIAL_ARTICLE_NO_EXACT_FIXTURE")
    except Exception as exc:
        errors.append(f"GIL_FETCH:{type(exc).__name__}: {exc}")
    try:
        braga = parse_braga_display(_fetch(BRAGA_PROGRAM, opener))
        if braga is None:
            errors.append("BRAGA_SITE_NO_EXACT_VISIBLE_FIXTURE")
    except Exception as exc:
        errors.append(f"BRAGA_FETCH:{type(exc).__name__}: {exc}")
    status = ("CLUB_ARTICLE_PARTIAL_FOR_REVIEW" if gil is not None
              else "NO_AUTHENTICATED_CLUB_FIXTURE")
    comparison = (
        "DISPLAY_TIMEZONE_NOT_STATED" if gil and braga and
        gil["gil_local_clock"] != braga["display_clock"]
        else "SAME_UNZONED_CLOCK_NOT_TIMEZONE_VERIFIED" if gil and braga
        else "BRAGA_DISPLAY_UNAVAILABLE" if gil else "GIL_ARTICLE_UNAVAILABLE"
    )
    by_day = {day: [] for day in days}
    if gil and gil["date_warsaw"] in by_day:
        by_day[gil["date_warsaw"]].append({
            "league_id": "por.1", "home": gil["home"], "away": gil["away"],
            "kickoff_warsaw": gil["kickoff_warsaw"], "kickoff_utc": gil["kickoff_utc"],
            "date_warsaw": gil["date_warsaw"], "official_url": gil["source_url"],
            "postponed_round": 2,
        })
    return {
        "schema": "kb21-official-portugal-club-postponement-v1",
        "league_id": "por.1", "days": days,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status, "by_day": by_day, "gil_official_article": gil,
        "braga_visible_display": braga, "source_comparison": comparison,
        "source_errors": errors, "errors": errors,
        "unconfirmed_zero_dates": [d for d in days if not by_day[d]],
        "official_url": GIL_NEWS,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False, "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("Gil Vicente's published 20:15 is Lisbon local time; SC Braga's "
                 "raw 19:15 display lacks explicit timezone and may be UTC. "
                 "Never treat unzoned clocks as proof of conflict or agreement. "
                 "One postponed match DOES NOT certify complete Portuguese calendar, "
                 "other postponed matches, or zero-fixture days."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    report = collect(a.days)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print("Portugal club official postponed match:",
          sum(map(len, report["by_day"].values())),
          "scoped games;", report["source_comparison"],
          "Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
