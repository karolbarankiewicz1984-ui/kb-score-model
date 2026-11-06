"""Parse observed event totals from football-data.co.uk CSV."""
import csv
import io
from datetime import datetime, timedelta, timezone

COLUMNS = {"corners": ("HC", "AC"), "cards": ("HY", "AY"), "fouls": ("HF", "AF")}

def parse_events(csv_text, league, observed_at_utc):
    observed = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    result = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            try:
                day = datetime.strptime(row["Date"], "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                day = datetime.strptime(row["Date"], "%d/%m/%y").replace(tzinfo=timezone.utc)
            completed = day + timedelta(days=2)
            if completed >= observed:
                continue
            events = {}
            for market, (home, away) in COLUMNS.items():
                try:
                    values = [int(row[home]), int(row[away])]
                    if min(values) >= 0:
                        events[market] = values
                except (KeyError, ValueError, TypeError):
                    pass
            if events:
                result.append({"league": league, "home": row["HomeTeam"], "away": row["AwayTeam"],
                    "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
                    "published_at_utc": observed_at_utc, "events": events})
        except (KeyError, ValueError, TypeError):
            continue
    return result
