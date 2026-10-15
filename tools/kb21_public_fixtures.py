"""Fetch public ESPN soccer scoreboard JSON for a selected date.

Candidate feed only. ESPN is NOT the official organizer; these fixtures must
be compared against official schedules before the KB21 Calendar Gate opens.
No keys, paid APIs, xG, or historical observations are touched.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ENDPOINT = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date}&limit=300"
LEAGUES = ("eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "por.1", "ned.1", "bel.1", "tur.1", "uefa.champions", "uefa.europa", "uefa.europa.conf", "uefa.nations", "fifa.worldq.uefa")


def parse_events(data, league):
    fixtures = []
    for event in data.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away or not event.get("date"):
            continue
        fixtures.append({"league": league, "event_id": str(event.get("id", "")),
                         "competition": data.get("leagues", [{}])[0].get("name", league) if data.get("leagues") else league,
                         "home": home.get("team", {}).get("displayName", ""),
                         "away": away.get("team", {}).get("displayName", ""),
                         "kickoff": event["date"], "source": "ESPN third-party"})
    return fixtures


def fetch(date):
    datetime.strptime(date, "%Y-%m-%d")
    stamp = date.replace("-", "")
    fixtures, sources, errors = [], [], []
    for league in LEAGUES:
        url = ENDPOINT.format(league=league, date=stamp)
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urlopen(req, timeout=12) as response:
                payload = json.load(response)
            events = parse_events(payload, league)
            fixtures.extend(events)
            sources.append({"league": league, "url": url, "events": len(events), "status": "OK"})
        except Exception as exc:
            errors.append({"league": league, "error": f"{type(exc).__name__}: {exc}"})
            sources.append({"league": league, "url": url, "status": "ERROR"})
    return {"date": date, "retrieved_at": datetime.now(ZoneInfo("Europe/Warsaw")).isoformat(),
            "status": "UNVERIFIED_CANDIDATES" if fixtures else "NO_VERIFIED_FIXTURES",
            "sources": sources, "errors": errors, "fixtures": fixtures,
            "calendar_gate": "BLOCKED",
            "note": "Third-party ESPN events are candidates, NOT an official complete fixture calendar. Verify organizer schedule and independent source, timezone, and full competition coverage before any P(model) or PLAY."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        data = fetch(args.date)
    except Exception as exc:
        data = {"date": args.date, "status": "SOURCE_UNAVAILABLE", "calendar_gate": "BLOCKED", "fixtures": [], "error": str(exc)}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{data['status']}: {len(data['fixtures'])} candidate events")


if __name__ == "__main__":
    main()
