"""Compare one officially announced postponed Portugal league fixture to ESPN.

Gil Vicente article supplies Lisbon-local time. SC Braga homepage has an
unlabelled display clock, so a different raw clock is not a verified conflict.
Neither website proves the complete organizer league/day fixture card.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, source):
    if (not isinstance(queue, dict)
            or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Expected assessment queue")
    if (not isinstance(source, dict)
            or source.get("schema") != "kb21-official-portugal-club-postponement-v1"
            or source.get("league_id") != "por.1"
            or set(source.get("days", [])) != set(queue["days"])
            or not isinstance(source.get("by_day"), dict)):
        raise ValueError("Portugal source scope/schema mismatch")
    result = {
        "schema": "kb21-portugal-postponement-crosscheck-v1",
        "league_id": "por.1", "days": {},
        "club_time_display": source.get("source_comparison"),
        "source_errors": source.get("errors", []),
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "human_approved": False, "full_calendar_verified": False,
    }
    for day in sorted(queue["days"]):
        official = source["by_day"].get(day)
        if not isinstance(official, list):
            raise ValueError("Missing source date")
        candidates = [f for f in queue["fixtures"]
                      if f.get("date_warsaw") == day
                      and str(f.get("fixture_id", "")).startswith("por.1:")]
        used = set()
        statuses = Counter()
        examined = []
        for candidate in candidates:
            parts = str(candidate.get("fixture", "")).split(" - ", 1)
            moment = _instant(candidate.get("kickoff"))
            if len(parts) != 2 or moment is None:
                matches, status = [], "INVALID_ESPN_FIXTURE"
            else:
                names = tuple(_team("por.1", name) for name in parts)
                matches = [i for i, record in enumerate(official)
                           if tuple(_team("por.1", record.get(field))
                                    for field in ("home", "away")) == names]
                if not matches:
                    status = "NOT_IN_GIL_CLUB_ARTICLE"
                elif len(matches) > 1:
                    status = "AMBIGUOUS_GIL_CLUB_ARTICLE"
                else:
                    idx = matches[0]
                    published = _instant(official[idx].get("kickoff_utc"))
                    if published is None:
                        status = "INVALID_PUBLISHED_KICKOFF"
                    elif abs((published - moment).total_seconds()) > 300:
                        status = "START_TIME_CONFLICT_WITH_GIL_ARTICLE"
                    elif idx in used:
                        status = "DUPLICATE_ESPN_CANDIDATE"
                    else:
                        status = "MATCHED_GIL_ARTICLE_FOR_REVIEW"
                    used.add(idx)
            statuses[status] += 1
            examined.append({
                "fixture_id": candidate.get("fixture_id"),
                "fixture": candidate.get("fixture"),
                "espn_kickoff": candidate.get("kickoff"),
                "gil_official_kickoff": official[matches[0]].get("kickoff_warsaw")
                    if len(matches) == 1 else None,
                "status": status,
            })
        extra = [fixture for index, fixture in enumerate(official)
                 if index not in used]
        statuses["GIL_ARTICLE_ONLY"] += len(extra)
        result["days"][day] = {
            "espn_count": len(candidates), "gil_article_count": len(official),
            "matched": statuses["MATCHED_GIL_ARTICLE_FOR_REVIEW"],
            "statuses": dict(statuses), "comparisons": examined,
            "gil_article_only": extra,
            "unconfirmed_zero_day": not official,
            "full_day_verified": False,
            "calendar_gate": "BLOCKED",
        }
    result["note"] = (
        "One dated Gil Vicente club announcement corroborates only one postponed "
        "fixture. No full Portugal fixture catalogue, no zero-day certification, "
        "no assumed timezone for Braga display, no review signoff or PLAY."
    )
    return result


def render(data):
    out = ["# KB21 — Portugalia: przełożony mecz klubowy kontra ESPN", "",
           "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
           "Porównanie godzin stron: " + str(data["club_time_display"]), "",
           "| Dzień | Gil Vicente | ESPN | Zgodne | Nieuzgodnione |",
           "|---|---:|---:|---:|---:|"]
    for day, row in sorted(data["days"].items()):
        problems = (row["espn_count"] - row["matched"] +
                    len(row["gil_article_only"]))
        out.append(f"| {day} | {row['gil_article_count']} | {row['espn_count']} | "
                   f"{row['matched']} | {problems} |")
        if row["unconfirmed_zero_day"]:
            out.append(f"- {day}: niepotwierdzony brak meczów — strona jednego "
                       "klubu nie stanowi kompletnego kalendarza ligi.")
        for event in row["comparisons"]:
            if event["status"] != "MATCHED_GIL_ARTICLE_FOR_REVIEW":
                out.append(f"- {day}: {event['fixture']} — {event['status']}; "
                           f"ESPN {event['espn_kickoff']}, "
                           f"Gil Vicente {event['gil_official_kickoff']}")
        for event in row["gil_article_only"]:
            out.append(f"- {day}: tylko Gil Vicente: {event['home']} - "
                       f"{event['away']} ({event['kickoff_warsaw']})")
    for problem in data["source_errors"]:
        out.append("- Problem odczytu: " + str(problem))
    out.append("")
    out.append("Nadal wymagane: pełna lista zaległych meczów organizatora i podpisana kontrola.")
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    queue = json.loads(Path(a.queue).read_text(encoding="utf-8"))
    official = json.loads(Path(a.official).read_text(encoding="utf-8"))
    data = compare(queue, official)
    for name, content in (
        (a.output, json.dumps(data, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(data)),
    ):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print("Portugal official postponed vs ESPN:",
          sum(x["matched"] for x in data["days"].values()),
          "matches; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
