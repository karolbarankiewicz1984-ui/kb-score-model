"""Populate unsigned official-calendar review draft with direct organizer fixture facts.

Safely complements manually researched calendar inventory with LIVE public
Premier League FPL (380-match season) and optional DFL (one visible round).
Does not populate reviewer, confirmed zero-day, captured_at (manual source
attestation), full_day_checked or approval. Existing manually researched
fixture rows are never overwritten; contradictions are surfaced.
"""
import argparse
import copy
import json
from datetime import datetime
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team

INPUTS = {
    "eng.1": ("kb21-official-premier-league-fpl-v1", "season_full_380_catalogue"),
    "ger.1": ("kb21-official-bundesliga-media-v1", None),
    "esp.1": ("kb21-official-laliga-matchday-html-v1", None),
}


def _key(league, fixture):
    if not isinstance(fixture, dict):
        return None
    kick = _instant(fixture.get("kickoff"))
    home, away = _team(league, fixture.get("home")), _team(league, fixture.get("away"))
    if not home or not away or kick is None:
        return None
    return home, away, kick


def seed(draft, official_sources):
    if not isinstance(draft, dict) or not isinstance(draft.get("days"), dict):
        raise ValueError("Expected official calendar review draft")
    if draft.get("approval") is not None:
        raise ValueError("Refuse to change signed calendar")
    dates = sorted(draft["days"])
    if not 1 <= len(dates) <= 3:
        raise ValueError("Expected exactly 1–3 scoped days")
    for day in dates:
        datetime.fromisoformat(day)
        if not isinstance(draft["days"][day], dict):
            raise ValueError("Invalid review day")
        for entry in draft["days"][day].values():
            if not isinstance(entry, dict) or entry.get("reviewer") or entry.get("captured_at") or entry.get("full_day_checked"):
                raise ValueError("Pre-reviewed inventory must never be auto-overwritten")

    result = copy.deepcopy(draft)
    additions = {}
    conflicts = {}
    for league, source in official_sources.items():
        if league not in INPUTS:
            raise ValueError("Only approved organizer fixture source adapters")
        expected_schema, full_catalogue_flag = INPUTS[league]
        if (not isinstance(source, dict)
                or source.get("schema") != expected_schema
                or source.get("league_id") != league
                or set(source.get("days", [])) != set(dates)
                or not isinstance(source.get("by_day"), dict)):
            raise ValueError("Official source date/scope mismatch")
        # Incomplete PL season is diagnostic evidence but insufficient
        # to replace the blank inventory with purported full official list.
        complete_enough = (source.get(full_catalogue_flag) is True
                           if full_catalogue_flag else
                           source.get("status") in ("OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW",
                                                           "OFFICIAL_PARTIAL_MATCHDAY_WINDOW_FOR_REVIEW"))
        if not complete_enough:
            continue
        count = 0
        disagreement = 0
        for day in dates:
            rows = source["by_day"].get(day)
            if not isinstance(rows, list):
                raise ValueError("Missing day in organizer source")
            # Partial LaLiga round windows cannot certify a day with zero games.
            if league == "esp.1" and not rows:
                continue
            review_row = result["days"][day].get(league)
            if not isinstance(review_row, dict):
                raise ValueError("Missing league inventory field")
            official_facts = []
            for event in rows:
                time = event.get("kickoff_warsaw")
                row = {"home": event.get("home"), "away": event.get("away"),
                       "kickoff": time}
                if _key(league, row) is None:
                    raise ValueError("Invalid organizer fixture event")
                official_facts.append(row)
            if len({_key(league, x) for x in official_facts}) != len(official_facts):
                raise ValueError("Duplicate organizer event identity")
            existing = review_row.get("fixtures")
            if not isinstance(existing, list):
                raise ValueError("Invalid template official fixture list")
            if not existing:
                review_row["fixtures"] = official_facts
                count += len(official_facts)
            else:
                known = [_key(league, x) for x in existing]
                extra = []
                for item in official_facts:
                    key = _key(league, item)
                    if key is None or not any(
                        known_row is not None
                        and key[:2] == known_row[:2]
                        and abs((key[2] - known_row[2]).total_seconds()) <= 300
                        for known_row in known
                    ):
                        extra.append(item)
                missing_from_official = []
                for item in existing:
                    key = _key(league, item)
                    if key is not None and not any(
                        fkey[:2] == key[:2]
                        and abs((fkey[2] - key[2]).total_seconds()) <= 300
                        for fkey in {_key(league, f) for f in official_facts}
                    ):
                        missing_from_official.append(item)
                if extra or missing_from_official:
                    review_row["organizer_data_discrepancies"] = {
                        "additional_organizer_events": extra,
                        "research_entries_not_in_organizer_feed": missing_from_official,
                        "requires_manual_check": True,
                    }
                    disagreement += len(extra) + len(missing_from_official)
            review_row["organizer_facts_source"] = (
                source.get("official_fixture_endpoint") or source.get("official_url")
                or (rows[0].get("official_url") if rows else None))
            review_row["organizer_facts_capture_utc"] = source.get("captured_at_utc")
            review_row["organizer_source_catalogue_kind"] = (
                "FULL_SEASON_380_FPL" if league == "eng.1" else
                "PARTIAL_LALIGA_ROUND_WINDOW" if league == "esp.1" else
                "ONLY_VISIBLE_DFL_MATCHDAY")
            review_row["organizer_source_fixtures_count_for_day"] = len(rows)
            if league == "esp.1":
                review_row["organizer_source_fetch_issues"] = len(source.get("errors", []))
            review_row["full_day_checked"] = False
            review_row["captured_at"] = None
            review_row["reviewer"] = None
            review_row["confirmed_zero_matches"] = None
            review_row["needs_current_organizer_verification"] = True
        additions[league] = count
        conflicts[league] = disagreement
    result["calendar_gate"] = "BLOCKED"
    result["publication"] = "DIAGNOSTIC / NO PLAY"
    result["approval"] = None
    result["organizer_live_seed_summary"] = {
        "fixtures_prefilled": additions, "discrepancies_against_existing_research": conflicts,
    }
    result["organizer_live_seed_note"] = (
        "Official fixture sources supply observational facts, NOT a human's "
        "source review, attestation, verified empty date, complete organizer "
        "calendar, premarket freeze, scoring, P(model), or PLAY. Current "
        "FPL snapshots are more reliable for the Premier League than manual "
        "transcription; DFL page may show one matchday only; LaLiga covers sampled rounds."
    )
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft")
    p.add_argument("--fpl")
    p.add_argument("--dfl")
    p.add_argument("--laliga")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    sources = {}
    for league, filename in (("eng.1", args.fpl), ("ger.1", args.dfl),
                             ("esp.1", args.laliga)):
        if filename:
            sources[league] = json.loads(Path(filename).read_text(encoding="utf-8"))
    original = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    report = seed(original, sources)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["organizer_live_seed_summary"]
    print(f"KB21 official data research prefill: {summary['fixtures_prefilled']}; "
          f"research contradictions: {summary['discrepancies_against_existing_research']}; "
          "0 signed approvals, CALENDAR BLOCKED")


if __name__ == "__main__":
    main()
