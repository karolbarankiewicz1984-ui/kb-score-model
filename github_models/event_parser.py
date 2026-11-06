"""Parse observed event totals from football-data.co.uk CSV."""
import csv
import io
from datetime import datetime, timedelta, timezone
from github_models.public_results import COUNTRIES, LEAGUES

COLUMNS = {"corners": ("HC", "AC"), "cards": ("HY", "AY"), "fouls": ("HF", "AF")}

def parse_events(csv_text, league, observed_at_utc, *, league_code=None, season=None):
    if league_code is not None:
        if league_code not in LEAGUES:
            raise ValueError("unsupported_football_data_division")
        if LEAGUES[league_code] != league:
            raise ValueError("football_data_league_code_conflict")
    observed = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timezone_required")
    result = []
    for line, row in enumerate(csv.DictReader(io.StringIO(csv_text)), start=2):
        try:
            if league_code is not None and row.get("Div") != league_code:
                continue
            try:
                day = datetime.strptime(row["Date"].strip(), "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                day = datetime.strptime(row["Date"].strip(), "%d/%m/%y").replace(tzinfo=timezone.utc)
            completed = day + timedelta(days=2)
            if completed >= observed:
                continue
            home, away = row["HomeTeam"].strip(), row["AwayTeam"].strip()
            if not home or not away or home == away:
                continue
            events = {}
            for market, (home_column, away_column) in COLUMNS.items():
                try:
                    values = [int(row[home_column]), int(row[away_column])]
                    if min(values) >= 0:
                        events[market] = values
                except (KeyError, ValueError, TypeError):
                    pass
            if events:
                result.append({"league": league, "home": home, "away": away,
                    "match_date": day.date().isoformat(),
                    "source_provider": "football-data.co.uk",
                    "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
                    "published_at_utc": observed_at_utc, "events": events})
                if league_code is not None:
                    result[-1].update(league_code=league_code, country_code=COUNTRIES[league_code])
                    if season is not None:
                        result[-1].update(
                            fixture_id=f"fdco:{season}:{league_code}:{day.date()}:{home}:{away}",
                            source_record_id=f"{season}:{league_code}:{line}")
        except (KeyError, ValueError, AttributeError, TypeError):
            continue
    return result
