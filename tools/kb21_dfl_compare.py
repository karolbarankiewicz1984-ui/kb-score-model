"""Review extracted Bundesliga Media (DFL) matchday fixture rows against ESPN.

Only the page's visible matchday can be compared. Even nine exact matches
cannot prove a full season/full day or verify postponed Bundesliga matches.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, dfl):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected ESPN assessment queue")
    if (not isinstance(dfl, dict)
            or dfl.get("schema") != "kb21-official-bundesliga-media-v1"
            or dfl.get("league_id") != "ger.1"
            or not isinstance(dfl.get("by_day"), dict)
            or set(dfl.get("days", [])) != set(queue.get("days", []))):
        raise ValueError("DFL date or schema mismatch")
    result = {"schema": "kb21-official-dfl-espn-crosscheck-v1",
              "calendar_gate": "BLOCKED",
              "publication": "DIAGNOSTIC / NO PLAY",
              "source": dfl.get("official_url"),
              "source_status": dfl.get("status"),
              "full_day_coverage_verified": False,
              "human_signed": False, "days": {}}
    for day in sorted(queue["days"]):
        official = dfl["by_day"].get(day)
        if not isinstance(official, list):
            raise ValueError("Missing official day bucket")
        espn = [f for f in queue["fixtures"]
                if f.get("date_warsaw") == day and
                str(f.get("fixture_id", "")).split(":")[0] == "ger.1"]
        used = set()
        comparisons = []
        statuses = Counter()
        for event in espn:
            parts = event.get("fixture", "").split(" - ", 1)
            start = _instant(event.get("kickoff"))
            if len(parts) != 2 or start is None:
                status = "INVALID_ESPN_FIXTURE"
                contenders = []
            else:
                host, visitor = [_team("ger.1", name) for name in parts]
                contenders = [x for x in official
                              if (_team("ger.1", x.get("home")),
                                  _team("ger.1", x.get("away"))) == (host, visitor)]
                if len(contenders) > 1:
                    status = "AMBIGUOUS_ORGANIZER_TEAM_PAIR"
                elif not contenders:
                    status = "NOT_ON_EXTRACTED_DFL_MATCHDAY"
                else:
                    other = _instant(contenders[0].get("kickoff_utc"))
                    status = ("BAD_ORGANIZER_TIME" if other is None
                              else "KICKOFF_DISAGREEMENT" if abs((start-other).total_seconds()) > 300
                              else "MATCHED_FOR_REVIEW")
            fixture = contenders[0] if len(contenders) == 1 else None
            if fixture:
                key = (fixture.get("home"), fixture.get("away"), fixture.get("kickoff_utc"))
                if key in used:
                    status = "DUPLICATE_ESPN_FIXTURE"
                used.add(key)
            statuses[status] += 1
            comparisons.append({
                "fixture_id": event.get("fixture_id"),
                "fixture": event.get("fixture"),
                "espn_kickoff": event.get("kickoff"),
                "organizer_home": fixture.get("home") if fixture else None,
                "organizer_away": fixture.get("away") if fixture else None,
                "organizer_kickoff": fixture.get("kickoff_warsaw") if fixture else None,
                "status": status, "calendar_gate": "BLOCKED",
            })
        extra = [f for f in official
                 if (f.get("home"), f.get("away"), f.get("kickoff_utc")) not in used]
        statuses["DFL_ONLY"] += len(extra)
        result["days"][day] = {
            "organizer_visible_fixtures": len(official),
            "espn_candidate_fixtures": len(espn),
            "matched": statuses["MATCHED_FOR_REVIEW"],
            "statuses": dict(sorted(statuses.items())),
            "comparisons": comparisons,
            "dfl_only": extra,
            "organizer_full_day_verified": False,
            "calendar_gate": "BLOCKED",
        }
    result["note"] = ("Bundesliga Media page may only show one matchday. "
                      "Club/time agreement is source evidence, not a complete "
                      "Bundesliga day verification or signed Calendar Gate.")
    return result


def render(result):
    lines = ["# KB Score 2.1 — oficjalna Bundesliga kontra ESPN", "",
             "**DANE POMOCNICZE / NO PLAY — Calendar Gate BLOCKED**", "",
             "| Data PL | DFL | ESPN | Zgodne | Różnice |",
             "|---|---:|---:|---:|---:|"]
    for day, data in sorted(result["days"].items()):
        diff = len(data["comparisons"]) - data["matched"] + len(data["dfl_only"])
        lines.append(f"| {day} | {data['organizer_visible_fixtures']} | "
                     f"{data['espn_candidate_fixtures']} | {data['matched']} | {diff} |")
    for day, data in sorted(result["days"].items()):
        for f in data["comparisons"]:
            if f["status"] != "MATCHED_FOR_REVIEW":
                lines.append(f"- {day} {f['fixture']}: {f['status']} "
                             f"ESPN {f['espn_kickoff']} / DFL {f['organizer_kickoff']}")
        for f in data["dfl_only"]:
            lines.append(f"- {day} tylko DFL {f['home']}–{f['away']}: {f['kickoff_warsaw']}")
    lines += ["", "Brak spotkania na stronie jednej kolejki nie oznacza "
              "braku spotkania w pełnym sezonowym terminarzu.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("dfl")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    report = compare(json.loads(Path(args.queue).read_text(encoding="utf-8")),
                     json.loads(Path(args.dfl).read_text(encoding="utf-8")))
    for name, content in (
        (args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(report)),
    ):
        dest = Path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    matches = sum(row["matched"] for row in report["days"].values())
    print(f"Official DFL vs ESPN {matches} matches (single visible matchday only); "
          f"Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
