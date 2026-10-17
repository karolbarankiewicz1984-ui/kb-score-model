"""Unsigned comparison: official LaLiga matchday HTML versus independent ESPN queue."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, official):
    if (not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list)
            or not isinstance(queue.get("days"), list)):
        raise ValueError("Expected fixture candidate queue")
    if (not isinstance(official, dict)
            or official.get("schema") != "kb21-official-laliga-matchday-html-v1"
            or official.get("league_id") != "esp.1"
            or set(official.get("days", [])) != set(queue["days"])):
        raise ValueError("Wrong LaLiga organizer source scope")
    result = {"schema": "kb21-official-laliga-crosscheck-v1",
              "days": {}, "calendar_gate": "BLOCKED",
              "publication": "DIAGNOSTIC / NO PLAY",
              "organizer_capture_utc": official.get("captured_at_utc"),
              "organizer_source_errors": official.get("errors", []),
              "full_calendar_verified": False, "reviewer_signed": False}
    for day in sorted(queue["days"]):
        official_rows = official.get("by_day", {}).get(day)
        if not isinstance(official_rows, list):
            raise ValueError("Missing organizer date")
        espn = [x for x in queue["fixtures"] if x.get("date_warsaw") == day
                and str(x.get("fixture_id", "")).startswith("esp.1:")]
        statuses = Counter()
        comparisons, used = [], set()
        for candidate in espn:
            pair = str(candidate.get("fixture", "")).split(" - ", 1)
            pair = tuple(_team("esp.1", x) for x in pair) if len(pair) == 2 else ()
            matched = [official_row for official_row in official_rows
                       if (_team("esp.1", official_row.get("home")),
                           _team("esp.1", official_row.get("away"))) == pair]
            if not pair or _instant(candidate.get("kickoff")) is None:
                status = "INVALID_CANDIDATE"
            elif len(matched) > 1:
                status = "AMBIGUOUS_ORGANIZER_MATCH"
            elif not matched:
                status = "NO_OFFICIAL_CLUB_PAIR"
            else:
                official_time = _instant(matched[0].get("kickoff_utc"))
                candidate_time = _instant(candidate.get("kickoff"))
                if official_time is None:
                    status = "INVALID_OFFICIAL_KICKOFF"
                elif abs((official_time - candidate_time).total_seconds()) > 300:
                    status = "KICKOFF_CONFLICT"
                elif id(matched[0]) in used:
                    status = "AMBIGUOUS_DUPLICATE_ESPN"
                else:
                    status = "MATCHED_FOR_REVIEW"
                used.add(id(matched[0]))
            statuses[status] += 1
            comparisons.append({"candidate": candidate.get("fixture"),
                                "candidate_id": candidate.get("fixture_id"),
                                "status": status,
                                "espn_kickoff": candidate.get("kickoff"),
                                "organizer_kickoff": matched[0].get("kickoff_warsaw") if len(matched) == 1 else None})
        only_organizer = [x for x in official_rows if id(x) not in used]
        statuses["OFFICIAL_ONLY"] += len(only_organizer)
        result["days"][day] = {"espn_count": len(espn), "official_count": len(official_rows),
                               "matched": statuses["MATCHED_FOR_REVIEW"],
                               "statuses": dict(statuses),
                               "comparisons": comparisons, "official_only": only_organizer,
                               "calendar_gate": "BLOCKED"}
    result["note"] = ("Official LaLiga matchday pages are sampled, not a complete calendar. "
                      "Any conflict or missing organizer page requires review. "
                      "No automatic signoff, scoring, freeze, PLAY or observation write.")
    return result


def render(report):
    out = ["# KB Score 2.1 — LaLiga oficjalny terminarz kontra ESPN", "",
           "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
           "| Dzień | LaLiga | ESPN | Zgodne | Niepotwierdzone |",
           "|---|---:|---:|---:|---:|"]
    for day, row in sorted(report["days"].items()):
        issues = row["espn_count"] - row["matched"] + len(row["official_only"])
        out.append(f"| {day} | {row['official_count']} | {row['espn_count']} | {row['matched']} | {issues} |")
    for day, row in sorted(report["days"].items()):
        for issue in row["comparisons"]:
            if issue["status"] != "MATCHED_FOR_REVIEW":
                out.append(f"- {day} {issue['candidate']}: {issue['status']} (ESPN: {issue['espn_kickoff']}, LaLiga: {issue['organizer_kickoff']})")
        for x in row["official_only"]:
            out.append(f"- {day} tylko LaLiga: {x['home']} — {x['away']} {x['kickoff_warsaw']}")
    out.append("Wynik nie jest ręcznym zatwierdzeniem kompletnego kalendarza.")
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    official = json.loads(Path(args.official).read_text(encoding="utf-8"))
    report = compare(queue, official)
    for filename, data in ((args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
                           (args.output_md, render(report))):
        dest = Path(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(data, encoding="utf-8")
    print("Official LaLiga vs ESPN:", sum(row["matched"] for row in report["days"].values()),
          "matches; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
