"""Official KNVB RESULTS-page pairs: POST-START diagnostic, NOT fixture proof.

The 'programma' page can drop a fixture after kickoff while 'uitslagen'
lists the team pair under its date. The latter does not prove prematch
kickoff/time, full day coverage, a score, or Calendar Gate PASS.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from tools.kb21_official_knvb import (
    MAX_BYTES, MONTHS, SOURCE as SCHEDULE_SOURCE, VisibleText, _club,
)

SOURCE = "https://www.knvb.nl/competities/eredivisie/uitslagen"
DATE_RE = re.compile(
    r"^(?:(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag) )?"
    r"(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})$", re.I)
SCORE_RE = re.compile(r"^(?:-|–|—|\d{1,2}\s*[-–:]\s*\d{1,2})$")


def _result_date(tokens, start):
    for count in (4, 3, 2, 1):
        phrase = " ".join(tokens[start:start + count])
        match = DATE_RE.fullmatch(phrase)
        if match:
            day, month, year = match.groups()
            try:
                return dt.date(int(year), MONTHS[month.casefold()], int(day)), count
            except ValueError:
                return None, 0
    return None, 0


def parse_html(html):
    if not isinstance(html, str):
        raise ValueError("Expected KNVB result page HTML")
    p = VisibleText()
    p.feed(html)
    tokens = p.tokens
    headings = [i for i, word in enumerate(tokens)
                if word.casefold() == "uitslagen eredivisie"]
    if not headings:
        return {"heading_found": False, "dates_found": [],
                "pairs": [], "issues": ["MISSING_RESULTS_HEADING"]}
    i, active, pairs, seen, dates, issues = headings[-1] + 1, None, [], set(), set(), []
    while i < len(tokens):
        current, consumed = _result_date(tokens, i)
        if consumed:
            active = current
            dates.add(active.isoformat())
            i += consumed
            continue
        if active is None:
            i += 1
            continue
        home, hlen = _club(tokens, i)
        if home is None:
            i += 1
            continue
        found = None
        for score_idx in range(i + hlen, min(i + hlen + 5, len(tokens))):
            if not SCORE_RE.fullmatch(tokens[score_idx]):
                continue
            for away_idx in range(score_idx + 1, min(score_idx + 5, len(tokens))):
                away, alen = _club(tokens, away_idx)
                if away and away != home:
                    found = (away, away_idx + alen)
                    break
            if found:
                break
        if found:
            away, next_i = found
            pair = (active.isoformat(), home.casefold(), away.casefold())
            if pair in seen:
                issues.append("DUPLICATE_RESULTS_PAIR")
            else:
                seen.add(pair)
                pairs.append({
                    "home": home, "away": away, "date_printed": active.isoformat(),
                    "league_id": "ned.1", "source": SOURCE,
                    "kickoff_utc": None, "kickoff_time_verified": False,
                    "match_result_verified": False,
                    "source_kind": "KNVB_RESULTS_DATE_AND_TEAMS_ONLY",
                })
            i = next_i
        else:
            i += hlen
    if not pairs:
        issues.append("NO_RESULTS_PAIRS_EXTRACTED")
    return {
        "heading_found": True, "dates_found": sorted(dates),
        "pairs": pairs, "issues": sorted(set(issues)),
    }


def collect(days, opener=urlopen):
    if (not isinstance(days, list) or not 1 <= len(days) <= 3
            or len(set(days)) != len(days)):
        raise ValueError("Expected 1-3 distinct Warsaw dates")
    days = sorted(dt.date.fromisoformat(day).isoformat() for day in days)
    parsed = {"dates_found": [], "pairs": [], "issues": []}
    errors = []
    try:
        req = Request(SOURCE, headers={
            "Accept": "text/html", "User-Agent": "Mozilla/5.0 KB21 unsigned results diagnostic",
        })
        with opener(req, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Results page exceeds maximum payload")
        parsed = parse_html(raw.decode("utf-8"))
    except Exception as exc:
        errors.append("RESULT_PAGE_FETCH_FAILED: " + type(exc).__name__ + ": " + str(exc))
    errors.extend(parsed["issues"])
    buckets = {day: [] for day in days}
    for pair in parsed["pairs"]:
        if pair["date_printed"] in buckets:
            buckets[pair["date_printed"]].append(pair)
    return {
        "schema": "kb21-knvb-results-date-pair-v1",
        "league_id": "ned.1", "official_url": SOURCE,
        "schedule_url": SCHEDULE_SOURCE,
        "days": days, "by_day": buckets,
        "page_dates_found": parsed["dates_found"],
        "page_pairs_visible": len(parsed["pairs"]),
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "errors": errors,
        "status": ("KNVB_RESULTS_DATE_PAIRS_PARTIAL"
                   if parsed["pairs"] and not errors else "KNVB_RESULTS_UNVERIFIED"),
        "calendar_gate": "BLOCKED", "prematch_calendar_verified": False,
        "official_kickoff_verified": False, "full_day_verified": False,
        "reviewer_signed": False, "confirmed_zero_matches": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("Results page can include matches that have started or are completed, "
                 "as well as undetermined scores. Pair/date only: cannot validate "
                 "earlier kickoff, prove complete prematch fixture card, allow PLAY "
                 "or backfill historical betting observations."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = collect(a.days)
    file = Path(a.output)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"KNVB results {out['status']}, {out['page_pairs_visible']} visible, "
          f"selected dates {sum(len(x) for x in out['by_day'].values())}; "
          "unverified kickoff and NO PLAY")


if __name__ == "__main__":
    main()
