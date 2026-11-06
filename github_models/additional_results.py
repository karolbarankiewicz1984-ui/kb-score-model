"""Observed scores from football-data.co.uk's additional country CSV feeds.

These files have a different schema from the ``mmz4281`` division files. They
provide final scores and odds, but no corners, cards or fouls. Only final scores
are imported; their first observation time is never inferred from match dates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re


# Reviewed against the actual country pages and downloaded CSVs. Generic raw
# labels receive distinct country-specific canonical names so ratings cannot
# pool Austrian/German Bundesliga or Brazilian/Italian Serie A observations.
ADDITIONAL_SOURCES = {
    "ARG": dict(country="Argentina", source_league="Liga Profesional", league="Liga Profesional", country_code="ARG"),
    "AUT": dict(country="Austria", source_league="Bundesliga", league="Austrian Bundesliga", country_code="AUT"),
    "BRA": dict(country="Brazil", source_league="Serie A", league="Brazilian Serie A", country_code="BRA"),
    "DNK": dict(country="Denmark", source_league="Superliga", league="Danish Superliga", country_code="DNK"),
    "JPN": dict(country="Japan", source_league="J1 League", league="J1 League", country_code="JPN"),
    "MEX": dict(country="Mexico", source_league="Liga MX", league="Liga MX", country_code="MEX"),
    "POL": dict(country="Poland", source_league="Ekstraklasa", league="Ekstraklasa", country_code="POL"),
    "ROU": dict(country="Romania", source_league="Superliga", league="Romanian Superliga", country_code="ROU"),
    "RUS": dict(country="Russia", source_league="Premier League", league="Russian Premier League", country_code="RUS"),
    "SWE": dict(country="Sweden", source_league="Allsvenskan", league="Allsvenskan", country_code="SWE"),
    "USA": dict(country="USA", source_league="MLS", league="MLS", country_code="USA"),
    "CHN": dict(country="China", source_league="Super League", league="Chinese Super League", country_code="CHN"),
    "FIN": dict(country="Finland", source_league="Veikkausliiga", league="Veikkausliiga", country_code="FIN"),
    "IRL": dict(country="Ireland", source_league="Premier Division", league="Irish Premier Division", country_code="IRL"),
    "NOR": dict(country="Norway", source_league="Eliteserien", league="Eliteserien", country_code="NOR"),
    "SWZ": dict(country="Switzerland", source_league="Super League", league="Swiss Super League", country_code="CHE",
                additional_leagues={"Challenge League": "Swiss Challenge League"}),
}
REQUIRED = ("Country", "League", "Season", "Date", "Home", "Away", "HG", "AG", "Res")


def source_url(source_code):
    if source_code not in ADDITIONAL_SOURCES:
        raise ValueError("unsupported_additional_source")
    return "https://www.football-data.co.uk/new/" + source_code + ".csv"


def _observed(value):
    if not isinstance(value, str):
        raise ValueError("observed_at_utc_required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at_utc_invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("observed_at_timezone_required")
    return result.astimezone(timezone.utc)


def audit_additional_csv(text, *, source_code, observed_at_utc, min_season_year=2023):
    """Validate country, league, final score and actual observation availability.

    ``completed_at_utc`` is a conservative match-date + two days bound, not an
    exact final-whistle timestamp. Whitespace is trimmed, aliases and odds are
    never used to create results. Missing or contradictory final scores remain
    rejected. The report accounts for every input record, including duplicates.
    """
    url = source_url(source_code)
    source = ADDITIONAL_SOURCES[source_code]
    league_names = {source["source_league"]: source["league"], **source.get("additional_leagues", {})}
    observed = _observed(observed_at_utc)
    if type(min_season_year) is not int or not 1 <= min_season_year <= 9999:
        raise ValueError("invalid_min_season_year")
    if not isinstance(text, str):
        raise ValueError("additional_csv_text_required")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    headers = reader.fieldnames or []
    # Real files repeat empty trailing odds headers. Required identity/score
    # headers must occur exactly once, preventing silent DictReader overwrite.
    if any(headers.count(field) != 1 for field in REQUIRED):
        raise ValueError("missing_or_duplicate_additional_headers")
    rejected = Counter()
    grouped = defaultdict(list)
    records = 0
    for line, raw in enumerate(reader, start=2):
        records += 1
        try:
            if any(not isinstance(raw.get(key), str) for key in REQUIRED):
                raise ValueError("missing_required_value")
            row = {key: raw[key].strip() for key in REQUIRED}
            if row["Country"] != source["country"]:
                raise ValueError("source_country_conflict")
            if row["League"] not in league_names:
                raise ValueError("unsupported_source_league")
            season = re.fullmatch(r"([0-9]{4})(?:/([0-9]{4}))?", row["Season"])
            if season is None:
                raise ValueError("invalid_season")
            start = int(season[1])
            end = int(season[2]) if season[2] is not None else start
            if not 1 <= start <= end <= 9999 or end - start > 1:
                raise ValueError("invalid_season")
            if start < min_season_year:
                raise ValueError("season_before_requested_scope")
            try:
                day = datetime.strptime(row["Date"], "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError("invalid_match_date") from exc
            if day.year not in (start, end):
                raise ValueError("match_date_outside_declared_season")
            completed = day + timedelta(days=2)
            if completed >= observed:
                raise ValueError("completion_not_verified_before_observation")
            home, away = row["Home"], row["Away"]
            if not home or not away or home == away:
                raise ValueError("invalid_team_identity")
            if not re.fullmatch(r"[0-9]+", row["HG"]) or not re.fullmatch(r"[0-9]+", row["AG"]):
                raise ValueError("missing_or_invalid_final_score")
            try:
                hg, ag = int(row["HG"]), int(row["AG"])
            except ValueError as exc:
                raise ValueError("missing_or_invalid_final_score") from exc
            expected_result = "H" if hg > ag else "A" if hg < ag else "D"
            if row["Res"] not in ("H", "D", "A"):
                raise ValueError("final_result_status_missing_or_invalid")
            if row["Res"] != expected_result:
                raise ValueError("final_result_score_conflict")
            fixture_id = f"fdco:new:{source_code}:{day.date()}:{home}:{away}"
            result = dict(fixture_id=fixture_id, league=league_names[row["League"]],
                          league_code="new:" + source_code, country_code=source["country_code"],
                          season=row["Season"], match_date=day.date().isoformat(),
                          home=home, away=away, home_goals=hg, away_goals=ag, status="FINISHED",
                          completed_at_utc=completed.isoformat().replace("+00:00", "Z"),
                          published_at_utc=observed_at_utc, source_provider="football-data.co.uk",
                          source_record_id=f"new:{source_code}:{line}", source_url=url)
            grouped[fixture_id].append(result)
        except (ValueError, OverflowError) as exc:
            rejected[str(exc)] += 1
    accepted = []
    for candidates in grouped.values():
        facts = {(row["league"], row["season"], row["home_goals"], row["away_goals"]) for row in candidates}
        if len(facts) != 1:
            rejected["conflicting_duplicate_fixture"] += len(candidates)
        else:
            accepted.append(candidates[0])
            rejected["duplicate_fixture"] += len(candidates) - 1
    reasons = {key: value for key, value in sorted(rejected.items()) if value}
    if len(accepted) + sum(reasons.values()) != records:
        raise ValueError("additional_record_accounting_mismatch")
    return dict(schema="github-models-additional-results-audit-v1", source_code=source_code,
                source_url=url, observed_at_utc=observed_at_utc, min_season_year=min_season_year,
                accepted=accepted, accepted_count=len(accepted), input_records=records,
                rejected_count=sum(reasons.values()), rejection_reasons=reasons,
                completion_timestamp="conservative_match_date_plus_two_days_bound",
                event_statistics_available=False, odds_imported=False)


def parse_additional_csv(text, *, source_code, observed_at_utc, min_season_year=2023):
    """Return only validated score rows; use the audit function for blockers."""
    return audit_additional_csv(text, source_code=source_code,
                                observed_at_utc=observed_at_utc,
                                min_season_year=min_season_year)["accepted"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--source-code", required=True, choices=sorted(ADDITIONAL_SOURCES))
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-season-year", type=int, default=2023)
    args = parser.parse_args()
    result = audit_additional_csv(Path(args.input).read_text(encoding="utf-8-sig"),
                                  source_code=args.source_code, observed_at_utc=args.observed_at,
                                  min_season_year=args.min_season_year)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("source_code", "accepted_count", "rejected_count")}))


if __name__ == "__main__":
    main()
