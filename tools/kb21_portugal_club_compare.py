"""Compare official Portugal postponed club-news evidence to ESPN candidates.

Club news is not a full official Liga Portugal fixture calendar.
An unlabeled SC Braga clock is preserved raw and NEVER treated as local/UTC.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, organizer):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid candidate queue")
    if (not isinstance(organizer, dict)
            or organizer.get("schema") != "kb21-official-portugal-club-postponement-v1"
            or organizer.get("league_id") != "por.1"
            or set(organizer.get("days", [])) != set(queue["days"])
            or not isinstance(organizer.get("by_day"), dict)):
        raise ValueError("Portugal club evidence scope/schema mismatch")
    output = {
        "schema": "kb21-portugal-club-postponement-crosscheck-v1",
        "league_id": "por.1", "days": {},
        "club_clock_evidence": {
            "gil_local_clock": (organizer.get("gil_official_article") or {}).get("gil_local_clock"),
            "gil_timezone": (organizer.get("gil_official_article") or {}).get("gil_timezone"),
            "braga_visible_clock": (organizer.get("braga_visible_display") or {}).get("display_clock"),
            "braga_time_zone": None,
            "status": organizer.get("source_comparison"),
        },
        "source_errors": organizer.get("source_errors", []),
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "reviewer_signed": False, "full_calendar_verified": False,
    }
    for day in sorted(queue["days"]):
        official = organizer["by_day"].get(day)
        if not isinstance(official, list):
            raise ValueError("Missing organizer date")
        espn = [row for row in queue["fixtures"]
                if row.get("date_warsaw") == day
                and str(row.get("fixture_id", "")).startswith("por.1:")]
        counts = Counter()
        comparisons = []
        matched_official = set()
        for row in espn:
            parts = str(row.get("fixture", "")).split(" - ", 1)
            moment = _instant(row.get("kickoff"))
            if len(parts) != 2 or moment is None:
                status, matching = "INVALID_ESPN_FIXTURE", []
            else:
                pair = tuple(_team("por.1", p) for p in parts)
                matching = [i for i, event in enumerate(official)
                            if tuple(_team("por.1", event.get(k))
                                     for k in ("home", "away")) == pair]
                if len(matching) == 0:
                    status = "NOT_IN_SINGLE_CLUB_POSTPONEMENT_ARTICLE"
                elif len(matching) > 1:
                    status = "AMBIGUOUS_OFFICIAL_FIXTURE"
                else:
                    record = official[matching[0]]
                    start = _instant(record.get("kickoff_utc"))
                    status = ("UNREADABLE_OFFICIAL_TIME" if start is None
                              else "KICKOFF_CONFLICT" if abs((moment - start).total_seconds()) > 300
                              else "DUPLICATE_ESPN_MATCH" if matching[0] in matched_official
                              else "MATCHED_FOR_REVIEW")
                    matched_official.add(matching[0])
            counts[status] += 1
            comparisons.append({
                "candidate": row.get("fixture"), "candidate_id": row.get("fixture_id"),
                "espn_kickoff": row.get("kickoff"), "status": status,
                "club_article_kickoff_warsaw": official[matching[0]].get("kickoff_warsaw")
                    if len(matching) == 1 else None,
            })
        club_only = [o for idx, o in enumerate(official) if idx not in matched_official]
        counts["CLUB_ARTICLE_ONLY"] += len(club_only)
        output["days"][day] = {
            "club_article_count": len(official), "espn_candidate_count": len(espn),
            "matched": counts["MATCHED_FOR_REVIEW"],
            "statuses": dict(counts),
            "comparisons": comparisons, "club_article_only": club_only,
            "official_full_day_verified": False, "confirmed_zero_matches": None,
        }
    output["note"] = (
        "ONE verified club article is not a complete league day or matchweek. "
        "SC Braga raw 19:15 clock has unspecified timezone and is not "
        "proof of conflict against Gil Vicente 20:15 Lisbon local. "
        "No PDF LIVE, PLAY, P(model), or historical N is authorized."
    )
    return output


def render(report):
    lines = ["# KB Score 2.1 — zaległy mecz SC Braga - Gil Vicente",
             "", "**Źródła klubowe / NIE pełen terminarz ligi — Calendar Gate BLOCKED / NO PLAY**", "",
             f"Gil Vicente: {report['club_clock_evidence']['gil_local_clock'] or 'BRAK'} "
             f"({report['club_clock_evidence']['gil_timezone'] or 'BRAK STREFY'})",
             f"SC Braga: {report['club_clock_evidence']['braga_visible_clock'] or 'BRAK'} "
             "(STREFA CZASOWA WITRYNY NIEPOTWIERDZONA)",
             f"Status porównania źródeł: {report['club_clock_evidence']['status']}",
             "", "| Dzień | Mecze z artykułu | ESPN | Zgodne | Konflikty / brak w artykule |",
             "|---|---:|---:|---:|---:|"]
    for day, row in report["days"].items():
        bad = row["espn_candidate_count"] - row["matched"] + len(row["club_article_only"])
        lines.append(f"| {day} | {row['club_article_count']} | "
                     f"{row['espn_candidate_count']} | {row['matched']} | {bad} |")
        for item in row["comparisons"]:
            if item["status"] != "MATCHED_FOR_REVIEW":
                lines.append(f"- {day}: {item['candidate']}: {item['status']} "
                             f"ESPN={item['espn_kickoff']} klub={item['club_article_kickoff_warsaw']}")
        for item in row["club_article_only"]:
            lines.append(f"- {day}: tylko oficjalny klub {item['home']} - {item['away']} "
                         f"{item['kickoff_warsaw']}")
    lines.extend(["", "NIE wolno potwierdzać pustego dnia ani całej ligi "
                  "na podstawie pojedynczej informacji klubowej.", ""])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("official")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    q = json.loads(Path(a.queue).read_text(encoding="utf-8"))
    o = json.loads(Path(a.official).read_text(encoding="utf-8"))
    result = compare(q, o)
    for name, content in (
        (a.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(result)),
    ):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf8")
    print("Portugal club vs ESPN:", sum(r["matched"] for r in result["days"].values()),
          "matches; raw display timezone unresolved; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
