"""Compare unsigned UEFA article club/date rows with ESPN discovery.

No timezone-approved kickoff times, no complete competition calendars, no PLAY.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_official_uefa_articles import SOURCES
from tools.kb21_official_research_compare import _team


def _pair(league, record):
    if not isinstance(record, dict):
        return None
    h, a = _team(league, record.get("home")), _team(league, record.get("away"))
    return (h, a) if h and a else None


def compare(queue, official):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid ESPN fixture queue")
    if (not isinstance(official, dict)
            or official.get("schema") != "kb21-official-uefa-league-phase-v1"
            or official.get("league_id") not in SOURCES
            or official.get("official_url") != SOURCES[official["league_id"]]
            or official.get("calendar_gate") != "BLOCKED"
            or official.get("kickoff_timezone_verified") is not False
            or official.get("full_calendar_verified") is not False
            or official.get("reviewer_signed") is not False
            or set(official.get("days", [])) != set(queue["days"])
            or not isinstance(official.get("by_day"), dict)):
        raise ValueError("Untrusted official UEFA article or wrong scope")
    league = official["league_id"]
    result = {
        "schema": "kb21-uefa-date-team-comparison-v1",
        "league_id": league, "days": {},
        "organizer_source": official["official_url"],
        "source_errors": official.get("errors", []),
        "calendar_gate": "BLOCKED", "kickoff_timezone_verified": False,
        "full_day_attestation": False,
        "publication": "DIAGNOSTIC / NO PLAY",
    }
    for day in queue["days"]:
        rows = official["by_day"].get(day)
        if not isinstance(rows, list):
            raise ValueError("Missing UEFA article day evidence")
        for row in rows:
            if not isinstance(row, dict) or row.get("date_printed") != day:
                raise ValueError("UEFA row outside requested day")
        candidates = [
            f for f in queue["fixtures"]
            if isinstance(f, dict) and f.get("date_warsaw") == day
            and str(f.get("fixture_id", "")).startswith(league + ":")
        ]
        available, matches, counts, paired = set(), [], Counter(), 0
        for candidate in candidates:
            fixture = candidate.get("fixture", "")
            parts = fixture.split(" - ", 1) if isinstance(fixture, str) else []
            pair = _pair(league, {"home": parts[0], "away": parts[1]}) if len(parts) == 2 else None
            indices = [idx for idx, item in enumerate(rows)
                       if pair is not None and _pair(league, item) == pair]
            if len(indices) > 1:
                status = "AMBIGUOUS_UEFA_ARTICLE_PAIR"
            elif not indices:
                status = "NOT_IN_UEFA_LEAGUE_PHASE_ARTICLE"
            elif indices[0] in available:
                status = "DUPLICATE_ESPN_PAIR"
            else:
                status = "DATE_TEAMS_ONLY_KICKOFF_UNVERIFIED"
                available.add(indices[0])
                paired += 1
            counts[status] += 1
            matches.append({
                "fixture_id": candidate.get("fixture_id"),
                "fixture": fixture, "status": status,
                "time_comparison_performed": False,
            })
        organizer_only = [row for idx, row in enumerate(rows) if idx not in available]
        counts["ORGANIZER_ONLY"] += len(organizer_only)
        result["days"][day] = {
            "espn_count": len(candidates), "organizer_count": len(rows),
            "date_team_matched": paired,
            "statuses": dict(sorted(counts.items())),
            "comparisons": matches, "organizer_only": organizer_only,
            "time_approved_matches": 0,
            "no_games_certified": False,
            "calendar_gate": "BLOCKED",
        }
    result["note"] = (
        "DATE_TEAMS_ONLY_KICKOFF_UNVERIFIED is not MATCHED_FOR_REVIEW "
        "and is NOT a verified clock or full card. League phase only, "
        "no automatic zero-day proof or PLAY."
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("official")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = compare(
        json.loads(Path(args.queue).read_text(encoding="utf-8")),
        json.loads(Path(args.official).read_text(encoding="utf-8")),
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"UEFA {report['league_id']}: date/team pairs = "
          f"{sum(r['date_team_matched'] for r in report['days'].values())}; "
          "kickoff approved = 0; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
