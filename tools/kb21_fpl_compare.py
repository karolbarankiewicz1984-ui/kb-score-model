"""Compare ESPN's 3-day queue against direct organizer-owned Fantasy PL JSON.

FPL provides real club IDs, full-season fixtures, match status and kickoffs.
This is independently useful even if third-party football-data.org is absent.
A match is a source-consistency check, NOT signed Calendar Gate or PLAY.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def _fixture_team_ids(league, fixture):
    parts = fixture.get("fixture", "").split(" - ", 1)
    if len(parts) != 2:
        return None
    home, away = (_team(league, name) for name in parts)
    return (home, away) if home and away else None


def compare(queue, official):
    if not isinstance(queue, dict) or not isinstance(queue.get("days"), list):
        raise ValueError("Expected analyst queue with dates")
    if not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected analyst queue fixtures")
    if (not isinstance(official, dict)
            or official.get("schema") != "kb21-official-premier-league-fpl-v1"
            or official.get("league_id") != "eng.1"
            or not isinstance(official.get("by_day"), dict)
            or set(official.get("days", [])) != set(queue["days"])):
        raise ValueError("FPL evidence date/scope invalid")
    summary = {"schema": "kb21-official-premier-league-crosscheck-v1",
               "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
               "fpl_capture_utc": official.get("captured_at_utc"),
               "full_season_fpl_catalogue": official.get("season_full_380_catalogue") is True,
               "full_organizer_day_signed": False, "days": {}}
    for day in sorted(queue["days"]):
        if day not in official["by_day"] or not isinstance(official["by_day"][day], list):
            raise ValueError("Official FPL fixture day missing")
        organizer = official["by_day"][day]
        espn = [f for f in queue["fixtures"]
                if f.get("date_warsaw") == day
                and str(f.get("fixture_id", "")).split(":")[0] == "eng.1"]
        used_organizer = set()
        examined = []
        totals = Counter()
        for item in espn:
            clubs = _fixture_team_ids("eng.1", item)
            tm = _instant(item.get("kickoff"))
            if clubs is None or tm is None:
                status = "INVALID_ESPN_FIXTURE"
                matches = []
            else:
                matches = [f for f in organizer
                           if (_team("eng.1", f.get("home")),
                               _team("eng.1", f.get("away"))) == clubs]
                status = "NO_OFFICIAL_CLUB_PAIR"
                if len(matches) == 1:
                    ft = _instant(matches[0].get("kickoff_utc"))
                    if ft is None:
                        status = "INVALID_ORGANIZER_KICKOFF"
                    elif abs((tm-ft).total_seconds()) > 300:
                        status = "KICKOFF_DISAGREEMENT"
                    elif matches[0].get("kickoff_provisional"):
                        status = "ORGANIZER_KICKOFF_PROVISIONAL"
                    else:
                        status = "MATCHED_FOR_REVIEW"
                elif len(matches) > 1:
                    status = "DUPLICATE_ORGANIZER_TEAM_PAIR"
            match = matches[0] if len(matches) == 1 else None
            if match is not None:
                key = str(match.get("fixture_id"))
                if key in used_organizer:
                    status = "AMBIGUOUS_DUPLICATE_ESPN_FIXTURE"
                used_organizer.add(key)
            totals[status] += 1
            examined.append({
                "espn_fixture_id": item.get("fixture_id"),
                "espn_fixture": item.get("fixture"),
                "espn_kickoff": item.get("kickoff"),
                "status": status,
                "fpl_fixture_id": match.get("fixture_id") if match else None,
                "fpl_home_team_id": match.get("home_team_id") if match else None,
                "fpl_away_team_id": match.get("away_team_id") if match else None,
                "fpl_home": match.get("home") if match else None,
                "fpl_away": match.get("away") if match else None,
                "fpl_kickoff": match.get("kickoff_warsaw") if match else None,
                "fpl_started": match.get("started") if match else None,
                "fpl_finished": match.get("finished") if match else None,
                "calendar_gate": "BLOCKED", "official_full_day_signed": False,
            })
        extras = [f for f in organizer if str(f.get("fixture_id")) not in used_organizer]
        for _ in extras:
            totals["FPL_ONLY"] += 1
        summary["days"][day] = {
            "fpl_fixture_count": len(organizer),
            "espn_fixture_count": len(espn),
            "identical_club_and_kickoff_count": totals["MATCHED_FOR_REVIEW"],
            "statuses": dict(sorted(totals.items())),
            "comparisons": examined,
            "official_only": [{
                "fpl_fixture_id": f.get("fixture_id"),
                "home": f.get("home"), "away": f.get("away"),
                "kickoff_warsaw": f.get("kickoff_warsaw"),
            } for f in extras],
            "status": "REVIEW_REQUIRED",
            "calendar_gate": "BLOCKED",
        }
    summary["note"] = (
        "FPL is organizer-owned fixture data, not the human-signed complete calendar. "
        "Mismatches require independent review; zero-match FPL days cannot automatically "
        "clear all fixtures; no pre-market freeze or PLAY is granted."
    )
    return summary


def render(data):
    out = ["# KB Score 2.1 — oficjalne Premier League FPL kontra ESPN",
           "", "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
           "| Dzień | FPL | ESPN | Zgodne | Konflikty | Tylko FPL |",
           "|---|---:|---:|---:|---:|---:|"]
    for day, info in sorted(data["days"].items()):
        conflict = info["espn_fixture_count"] - info["identical_club_and_kickoff_count"]
        out.append(
            f"| {day} | {info['fpl_fixture_count']} | {info['espn_fixture_count']} | "
            f"{info['identical_club_and_kickoff_count']} | {conflict} | "
            f"{len(info['official_only'])} |")
    out += ["", "## Niezgodności", ""]
    for day, info in sorted(data["days"].items()):
        for record in info["comparisons"]:
            if record["status"] != "MATCHED_FOR_REVIEW":
                out.append(f"- {day}: {record['espn_fixture']} — {record['status']}, "
                           f"ESPN {record['espn_kickoff']}, FPL {record['fpl_kickoff']}")
        for f in info["official_only"]:
            out.append(f"- {day}: **tylko oficjalne FPL** {f['home']}–{f['away']} "
                       f"o {f['kickoff_warsaw']}")
    out += ["", "Do PASS_MANUAL konieczny niezależny pełny audyt i podpis, "
            "także dla 13 pozostałych kategorii rozgrywek.", ""]
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official_fpl")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    source = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    official = json.loads(Path(args.official_fpl).read_text(encoding="utf-8"))
    data = compare(source, official)
    for filename, content in (
        (args.output, json.dumps(data, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(data)),
    ):
        dest = Path(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    matches = sum(d["identical_club_and_kickoff_count"] for d in data["days"].values())
    conflicts = sum(d["espn_fixture_count"] - d["identical_club_and_kickoff_count"]
                    for d in data["days"].values())
    extras = sum(len(d["official_only"]) for d in data["days"].values())
    print(f"Official FPL vs ESPN: {matches} matching, {conflicts} differing, "
          f"{extras} FPL-only, Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
