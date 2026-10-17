"""Read public *official Premier League Fantasy* team and fixture JSON.

This is league-owned competition fixture evidence, not a third-party calendar.
No login, paid API, HTML scraping or model writes. The FPL game covers the
Premier League only; API JSON correctness cannot certify FULL organizer
schedule, latest broadcast updates, other competitions or human signoff.
All outputs: DIAGNOSTIC / NO PLAY, Calendar Gate BLOCKED.
"""
import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://fantasy.premierleague.com/api/"
TEAM_ENDPOINT = BASE + "bootstrap-static/"
FIXTURE_ENDPOINT = BASE + "fixtures/"
WARSAW = ZoneInfo("Europe/Warsaw")
MAX_BYTES = 4_000_000


def _get_json(url, opener=urllib.request.urlopen):
    if url not in (TEAM_ENDPOINT, FIXTURE_ENDPOINT):
        raise ValueError("Only vetted official FPL JSON URLs")
    request = urllib.request.Request(
        url, headers={
            "Accept": "application/json",
            "User-Agent": "KBScore21CalendarAudit/1.0 (fixture verification only)",
        })
    try:
        with opener(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Official fixture payload exceeds safety limit")
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Official FPL HTTP {exc.code}") from exc
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid public official fixture JSON") from exc


def _moment(value):
    if not isinstance(value, str):
        return None
    try:
        item = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if item.tzinfo is None or item.utcoffset() is None:
        return None
    return item


def convert(bootstrap, fixtures, days, captured_at=None):
    """Parse entire-season FPL fixtures, then select precisely Warsaw-local days.

    Wrong season/incomplete catalogue yields explicit warning, NEVER empty-day
    confirmation. A fixture missing kickoff remains in unknown count; cannot
    prove no games in any requested calendar day.
    """
    if not isinstance(bootstrap, dict) or not isinstance(bootstrap.get("teams"), list):
        raise ValueError("Official FPL bootstrap missing team mapping")
    if not isinstance(fixtures, list):
        raise ValueError("Official FPL fixtures must be an array")
    if not isinstance(days, list) or not 1 <= len(days) <= 3 or len(days) != len(set(days)):
        raise ValueError("Requested scope must contain 1–3 unique dates")
    target = {dt.date.fromisoformat(day).isoformat() for day in days}
    team_rows = bootstrap["teams"]
    teams = {}
    for team in team_rows:
        if not isinstance(team, dict) or isinstance(team.get("id"), bool):
            raise ValueError("Invalid FPL team data")
        if not isinstance(team.get("id"), int) or not isinstance(team.get("name"), str):
            raise ValueError("Invalid FPL team identity")
        if team["id"] in teams or not team["name"].strip():
            raise ValueError("Ambiguous FPL team ID")
        teams[team["id"]] = team["name"].strip()
    if len(teams) != 20:
        raise ValueError(f"Expected 20 Premier League FPL teams, got {len(teams)}")
    captured = captured_at or dt.datetime.now(dt.timezone.utc)
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("Capture timestamp must be timezone aware")
    found = {}
    result_by_day = {day: [] for day in sorted(target)}
    missing_time = []
    invalid = []
    for record in fixtures:
        if not isinstance(record, dict) or isinstance(record.get("id"), bool):
            raise ValueError("Malformed official FPL fixture")
        ident = record.get("id")
        if not isinstance(ident, int) or ident in found:
            raise ValueError("Duplicate/invalid official FPL match ID")
        found[ident] = True
        h, a = record.get("team_h"), record.get("team_a")
        if h not in teams or a not in teams or h == a:
            raise ValueError("Official FPL fixture has unknown/identical teams")
        if record.get("provisional_start_time") is True:
            invalid.append(ident)  # provisional times cannot certify a full kickoff catalogue
        moment = _moment(record.get("kickoff_time"))
        if moment is None:
            missing_time.append(ident)
            continue
        day = moment.astimezone(WARSAW).date().isoformat()
        if day not in target:
            continue
        if not isinstance(record.get("started"), bool) or not isinstance(record.get("finished"), bool):
            invalid.append(ident)
            continue
        fixture = {
            "fixture_id": ident, "league_id": "eng.1",
            "home": teams[h], "away": teams[a],
            "home_team_id": h, "away_team_id": a,
            "kickoff_utc": moment.astimezone(dt.timezone.utc).isoformat(),
            "kickoff_warsaw": moment.astimezone(WARSAW).isoformat(),
            "date_warsaw": day,
            "gameweek": record.get("event"),
            "started": record["started"], "finished": record["finished"],
            "provisional_start_time": record.get("provisional_start_time", False),
            "fixture_source": FIXTURE_ENDPOINT,
        }
        fixture["kickoff_provisional"] = fixture["provisional_start_time"] is True
        result_by_day[day].append(fixture)
    # Note: result_by_day is created before processing; never infer verified no games.
    for day in result_by_day:
        result_by_day[day].sort(key=lambda row: (row["kickoff_utc"], row["fixture_id"]))
    complete_catalogue = len(fixtures) == 380 and not missing_time and not invalid
    return {
        "schema": "kb21-official-premier-league-fpl-v1",
        "official_organizer": "Premier League / Fantasy Premier League",
        "official_owned_domain": "fantasy.premierleague.com",
        "official_fixture_endpoint": FIXTURE_ENDPOINT,
        "official_teams_endpoint": TEAM_ENDPOINT,
        "captured_at_utc": captured.astimezone(dt.timezone.utc).isoformat(),
        "days": sorted(target),
        "league_id": "eng.1",
        "season_fixture_count": len(fixtures),
        "season_team_count": len(teams),
        "season_full_380_catalogue": complete_catalogue,
        "fixtures_missing_kickoff_count": len(missing_time),
        "fixtures_missing_kickoff_ids": missing_time[:30],
        "invalid_or_provisional_fixture_ids": invalid[:30],
        "by_day": result_by_day,
        "calendar_gate": "BLOCKED",
        "full_calendar_verified": False,
        "reviewer_signed": False,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": ("Direct public organizer-owned FPL fixture data; useful for match IDs and "
                 "kickoffs but cannot automatically certify all league updates, "
                 "postponements, other competitions, or official manual signoff. "
                 "In particular a blank day is not a verified no-game day "
                 "unless catalogue is complete and formally reviewed."),
    }


def fetch(days, opener=urllib.request.urlopen, captured_at=None):
    bootstrap = _get_json(TEAM_ENDPOINT, opener)
    fixtures = _get_json(FIXTURE_ENDPOINT, opener)
    return convert(bootstrap, fixtures, days, captured_at=captured_at)


def render(report):
    lines = [
        "# KB Score 2.1 — oficjalne dane Premier League (Fantasy)",
        "", "**Calendar Gate BLOCKED — DIAGNOSTYKA / NO PLAY**", "",
        f"Odczyt UTC: {report['captured_at_utc']}",
        f"Sezon: {report['season_fixture_count']} meczów; "
        f"{report['season_team_count']} klubów; "
        f"komplet katalogu i godzin: {'TAK' if report['season_full_380_catalogue'] else 'NIE'}",
        f"Spotkania bez godziny w źródle: {report['fixtures_missing_kickoff_count']}",
        "", "| Dzień (Polska) | Godzina | Gospodarze | Goście | FPL ID | Status |",
        "|---|---|---|---|---:|---|",
    ]
    for day, rows in sorted(report["by_day"].items()):
        for fixture in rows:
            local = dt.datetime.fromisoformat(fixture["kickoff_warsaw"])
            stat = ("ROZEGRANY" if fixture["finished"]
                    else "ROZPOCZĘTY" if fixture["started"]
                    else "GODZINA WSTĘPNA" if fixture["kickoff_provisional"]
                    else "PLANOWANY")
            lines.append(
                f"| {day} | {local:%H:%M} | {fixture['home']} | "
                f"{fixture['away']} | {fixture['fixture_id']} | {stat} |"
            )
    lines.extend(["", "Źródło: " + report["official_fixture_endpoint"],
                  "Zapisana lista nie zastępuje niezależnej ręcznej kontroli "
                  "pełnego terminarza ani zatwierdzenia pozostałych 13 rozgrywek.", ""])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", nargs="+", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    report = fetch(args.days)
    for filename, content in (
        (args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(report)),
    ):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Official FPL: {report['season_fixture_count']} season fixtures, "
          f"{sum(len(x) for x in report['by_day'].values())} on 3 requested dates; "
          f"catalogue complete={report['season_full_380_catalogue']}; CALENDAR BLOCKED")


if __name__ == "__main__":
    main()
