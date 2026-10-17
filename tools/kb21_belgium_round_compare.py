"""Compare JPL undated selected-round club pairs to ESPN without guessing dates."""
import argparse
import json
from pathlib import Path

from tools.kb21_official_belgium import SOURCE
from tools.kb21_official_research_compare import _team


def _pair(home, away):
    a, b = _team("bel.1", home), _team("bel.1", away)
    return (a, b) if a and b else None


def compare(queue, source):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid KB21 queue")
    if (not isinstance(source, dict)
            or source.get("schema") != "kb21-official-belgium-selected-round-v1"
            or source.get("league_id") != "bel.1"
            or source.get("official_url") != SOURCE
            or source.get("calendar_gate") != "BLOCKED"
            or source.get("full_calendar_verified") is not False
            or source.get("date_verified") is not False
            or source.get("kickoff_timezone_verified") is not False
            or source.get("reviewer_signed") is not False
            or set(source.get("days", [])) != set(queue["days"])
            or not isinstance(source.get("by_day"), dict)
            or not isinstance(source.get("undated_fixtures"), list)):
        raise ValueError("Invalid unsigned Belgium JPL selected-round source")
    if any(source["by_day"].get(day) != [] for day in queue["days"]):
        raise ValueError("Undated JPL round cannot contain dated by-day fixtures")
    pairs = set()
    for f in source["undated_fixtures"]:
        if (not isinstance(f, dict) or f.get("date_warsaw") is not None
                or f.get("kickoff_warsaw") is not None):
            raise ValueError("JPL source must not claim verified fixture dates")
        pair = _pair(f.get("home"), f.get("away"))
        if pair is None:
            raise ValueError("Invalid JPL club pair")
        pairs.add(pair)
    out = {
        "schema": "kb21-belgium-undated-compare-v1",
        "league_id": "bel.1", "days": {},
        "organizer_source": SOURCE, "source_errors": source.get("errors", []),
        "calendar_gate": "BLOCKED", "full_day_attestation": False,
        "publication": "DIAGNOSTIC / NO PLAY",
    }
    for day in queue["days"]:
        candidates = [f for f in queue["fixtures"]
                      if isinstance(f, dict) and f.get("date_warsaw") == day
                      and str(f.get("fixture_id", "")).startswith("bel.1:")]
        hints = []
        for f in candidates:
            fixture = f.get("fixture")
            clubs = fixture.split(" - ", 1) if isinstance(fixture, str) else []
            if len(clubs) == 2 and _pair(*clubs) in pairs:
                hints.append(f.get("fixture_id"))
        out["days"][day] = {
            "espn_count": len(candidates),
            "organizer_count": 0,  # no reliably dated official fixtures
            "undated_organizer_round_count": len(source["undated_fixtures"]),
            "team_pair_only_hints": hints,  # no time/date claim
            "time_approved_matches": 0,
            "statuses": {},
            "calendar_gate": "BLOCKED",
            "no_games_certified": False,
        }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = compare(json.loads(Path(a.queue).read_text(encoding="utf-8")),
                     json.loads(Path(a.source).read_text(encoding="utf-8")))
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("Belgium JPL undated round comparison; no official dates, "
          "no kickoff approval, Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
