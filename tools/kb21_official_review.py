"""Official-organizer Calendar Gate review checklist, never automatic approval.

This is an AUDIT WORKSHEET, not an HTML scraper. URLs are official entry points
found via manual research, NOT evidence that any specific day's matches have
been retrieved or verified. A reviewer must compare actual organizer schedules
to a full day/competition snapshot; every row remains PENDING.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from tools.kb21_calendar_coverage import CORE, SCOPE

# Individually discovered official schedule pages. No invented URLs.
# Sites with dynamic schedules still need day-specific manual verification.
OFFICIAL_PAGES = {
    "eng.1": "https://www.premierleague.com/en/matches/premier-league/2026-27?cl=-1&co=8",
    "esp.1": "https://www.laliga.com/laliga-easports/calendario",
    "ita.1": "https://www.legaseriea.it/serie-a/calendario-risultati",
    "ger.1": "https://products.bundesliga.com/fixtures",
    "fra.1": "https://ligue1.com/en/calendar/ligue1",
    "por.1": "https://www.ligaportugal.pt/competition/911/liga-portugal-betclic/round/20262027",
    "ned.1": "https://eredivisie.com/competition/fixtures/",
    "bel.1": "https://www.proleague.be/jpl-kalender",
    "tur.1": "https://www.tff.org/?pageID=198",
    "uefa.champions": "https://www.uefa.com/uefachampionsleague/fixtures-results/",
    "uefa.europa": "https://www.uefa.com/uefaeuropaleague/news/02a8-2174cafa5bb6-82bbc20c9b92-1000--2026-27-europa-league-all-the-league-phase-fixtures/",
    "uefa.europa.conf": "https://www.uefa.com/uefaconferenceleague/fixtures-results/",
    "uefa.nations": "https://www.uefa.com/uefanationsleague/fixtures-results/",
    "fifa.worldq.uefa": "https://www.uefa.com/european-qualifiers/fixtures-results/",
}


def build(coverage):
    if not isinstance(coverage, dict) or not isinstance(coverage.get("days"), dict):
        raise ValueError("Expected KB21 calendar coverage with days dictionary")
    days = {}
    for date, report in sorted(coverage["days"].items()):
        if not isinstance(report, dict):
            raise ValueError("Daily coverage must be an object")
        known = {r["league_id"]: r for r in report.get("core_leagues", [])
                 + report.get("other_competitions", [])}
        rows = []
        for code, label in SCOPE.items():
            evidence = known.get(code) or {}
            url = OFFICIAL_PAGES.get(code)
            if url and (urlsplit(url).scheme != "https" or not urlsplit(url).hostname):
                raise ValueError(f"Invalid organizer URL for {code}")
            status = evidence.get("status", "NO_PROVIDER_COVERAGE_AUDIT")
            candidates = evidence.get("espn_candidates")
            second = evidence.get("independent_provider_candidates")
            row = {
                "league_id": code, "competition": label, "mandatory_core": code in CORE,
                "organizer_entry_url": url,
                "organizer_fixture_capture": None,
                "organizer_fixture_count": None,
                "organizer_fixture_ids": [],
                "confirmed_no_games_by_organizer": None,
                "independent_providers_compared": ["ESPN", "football-data.org"],
                "espn_candidates": candidates,
                "independent_candidates": second,
                "two_provider_crossmatched": evidence.get("crossmatched", 0),
                "provider_status": status,
                "official_schedule_checked": False,
                "full_match_list_compared": False,
                "reviewer": None,
                "calendar_gate": "BLOCKED",
                "needs_manual_official_review": True,
                "review_priority": (
                    "SOURCE_URL_MISSING" if url is None else
                    "PROVIDER_MISMATCH_OR_COVERAGE_GAP" if status != "TWO_PROVIDER_CANDIDATE_AGREEMENT_REVIEW"
                    else "VERIFY_ORGANIZER_COMPLETE_LIST"
                ),
            }
            rows.append(row)
        days[date] = {
            "core_leagues_checked": 0,
            "organizer_verified_leagues": 0,
            "total_competitions_to_review": len(rows),
            "rows": rows,
            "calendar_gate": "BLOCKED",
        }
    return {
        "schema": "kb21-official-review-v1",
        "status": "OFFICIAL_MANUAL_AUDIT_PENDING",
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "all_days_organizer_verified": False,
        "days": days,
        "note": (
            "A published official URL is not proof a specific match or full card was checked. "
            "Empty API results are never proof of no games. All rows require independent "
            "organizer inventory with retrieval time plus review, before Calendar Gate can pass."
        ),
    }


def render(review):
    out = [
        "# KB Score 2.1 — oficjalny audyt terminarza", "",
        "**NIEZATWIERDZONE — Calendar Gate BLOCKED. Zebrane linki to punkty kontroli, nie dowody kompletności.**",
        "W każdej rozgrywce trzeba sprawdzić pełen terminarz organizatora, godzinę PL, "
        "brakujące mecze i zapisać czas odczytu. Brak meczu u jednego dostawcy nie "
        "dowodzi braku spotkania.", "",
    ]
    for date, data in review["days"].items():
        out.extend([f"## {date} — do sprawdzenia {data['total_competitions_to_review']} rozgrywek", "",
                    "| Rozgrywki | Oficjalny terminarz | ESPN | 2. źródło | Zgodne | Co sprawdzić |",
                    "|---|---|---:|---:|---:|---|"])
        for row in data["rows"]:
            link = f"[Otwórz]({row['organizer_entry_url']})" if row["organizer_entry_url"] else "**BRAK LINKU**"
            right = row["independent_candidates"]
            out.append(f"| {row['competition']} | {link} | {row['espn_candidates']} | "
                       f"{right if right is not None else 'BRAK'} | {row['two_provider_crossmatched']} | "
                       f"{row['review_priority']} |")
        out.extend(["", "**Wynik:** żadna liga nie jest automatycznie zatwierdzona. "
                    "Wymagany zapis listy oficjalnych meczów lub potwierdzenie "
                    "braku spotkań na podstawie źródła organizatora.", ""])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("calendar_coverage")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.calendar_coverage).read_text(encoding="utf-8"))
    review = build(data)
    for filename, content in (
        (args.output_json, json.dumps(review, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(review)),
    ):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"KB21 official calendars to review: {len(review['days'])} days, "
          f"{sum(d['total_competitions_to_review'] for d in review['days'].values())} checks; NO PASS")


if __name__ == "__main__":
    main()
