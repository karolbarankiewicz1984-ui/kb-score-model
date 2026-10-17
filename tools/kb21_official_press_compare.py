"""Compare dated organizer fixture announcements to independent ESPN candidates.

Only identifies coincidences and disagreements. Does not certify full calendar.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team

LEAGUES = frozenset(("ita.1", "fra.1"))


def compare(queue, organizer):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Expected ESPN assessment queue")
    if (not isinstance(organizer, dict)
            or organizer.get("schema") != "kb21-official-press-fixtures-v1"
            or organizer.get("league_id") not in LEAGUES
            or set(organizer.get("days", [])) != set(queue["days"])
            or not isinstance(organizer.get("by_day"), dict)):
        raise ValueError("Unexpected organizer press source or different date scope")
    league = organizer["league_id"]
    out = {
        "schema": "kb21-official-press-crosscheck-v1",
        "league_id": league, "days": {}, "organizer_source": organizer.get("official_url"),
        "organizer_fetch_errors": organizer.get("errors", []),
        "days_outside_article_range": organizer.get("days_outside_article_range", []),
        "days_without_article_fixture_evidence": organizer.get("days_without_article_fixture_evidence", []),
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "human_approved": False,
    }
    for day in sorted(queue["days"]):
        official = organizer["by_day"].get(day)
        if not isinstance(official, list):
            raise ValueError("Missing organizer day")
        independent = [x for x in queue["fixtures"]
                       if x.get("date_warsaw") == day
                       and str(x.get("fixture_id", "")).startswith(league + ":")]
        used = set()
        counts = Counter()
        examined = []
        for candidate in independent:
            parts = candidate.get("fixture", "").split(" - ", 1)
            teams = tuple(_team(league, item) for item in parts) if len(parts) == 2 else ()
            moment = _instant(candidate.get("kickoff"))
            if len(teams) != 2 or not all(teams) or moment is None:
                matches, status = [], "INVALID_ESPN_FIXTURE"
            else:
                matches = [index for index, fact in enumerate(official)
                           if (_team(league, fact.get("home")),
                               _team(league, fact.get("away"))) == teams]
                if len(matches) > 1:
                    status = "AMBIGUOUS_ORGANIZER_PAIR"
                elif not matches:
                    status = "MISSING_IN_ORGANIZER_ARTICLE"
                else:
                    matched = official[matches[0]]
                    official_moment = _instant(matched.get("kickoff_utc"))
                    if official_moment is None:
                        status = "INVALID_ORGANIZER_KICKOFF"
                    elif abs((moment - official_moment).total_seconds()) > 300:
                        status = "KICKOFF_CONFLICT"
                    elif matches[0] in used:
                        status = "DUPLICATE_ESPN_FIXTURE"
                    else:
                        status = "MATCHED_FOR_REVIEW"
                    used.add(matches[0])
            counts[status] += 1
            examined.append({
                "espn_fixture_id": candidate.get("fixture_id"),
                "espn_fixture": candidate.get("fixture"),
                "espn_kickoff": candidate.get("kickoff"),
                "organizer_kickoff": official[matches[0]].get("kickoff_warsaw")
                                     if len(matches) == 1 else None,
                "status": status,
            })
        only_organizer = [fact for idx, fact in enumerate(official) if idx not in used]
        counts["ORGANIZER_ONLY"] += len(only_organizer)
        out["days"][day] = {
            "organizer_count": len(official), "espn_count": len(independent),
            "identical_fixture_count": counts["MATCHED_FOR_REVIEW"],
            "statuses": dict(sorted(counts.items())), "comparisons": examined,
            "organizer_only": only_organizer,
            "organizer_coverage": "DATED_ANNOUNCEMENT_PARTIAL",
            "calendar_gate": "BLOCKED",
        }
    out["note"] = (
        "Dated press releases cannot certify complete, amended, postponed, or "
        "future calendar days. Each league/day requires official review. "
        "Never infer PLAY or produce a model score from matches alone."
    )
    return out


def render(report):
    rows = [
        "# KB21 — bezpośrednie komunikaty organizatorów kontra ESPN",
        "", "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
        "| Dzień | Organizator | ESPN | Zgodne | Konflikty / braki |",
        "|---|---:|---:|---:|---:|",
    ]
    for day, row in sorted(report["days"].items()):
        bad = (row["espn_count"] - row["identical_fixture_count"]
               + len(row["organizer_only"]))
        rows.append(
            f"| {day} | {row['organizer_count']} | {row['espn_count']} | "
            f"{row['identical_fixture_count']} | {bad} |"
        )
    rows.append("")
    for day, row in sorted(report["days"].items()):
        for issue in row["comparisons"]:
            if issue["status"] != "MATCHED_FOR_REVIEW":
                rows.append(
                    f"- {day}: {issue['espn_fixture']} — {issue['status']}; "
                    f"ESPN {issue['espn_kickoff']}; organizator "
                    f"{issue['organizer_kickoff']}"
                )
        for item in row["organizer_only"]:
            rows.append(
                f"- {day}: tylko organizator: {item['home']} – {item['away']} "
                f"{item['kickoff_warsaw']}"
            )
    if report["days_without_article_fixture_evidence"]:
        rows.append("")
        rows.append("Brak potwierdzenia spotkań w komunikacie dla dat (NIE potwierdzono 0 spotkań): "
                    + ", ".join(report["days_without_article_fixture_evidence"]))
    if report["days_outside_article_range"]:
        rows.append("")
        rows.append(
            "Daty poza zasięgiem artykułu (nie oznacza braku spotkań): "
            + ", ".join(report["days_outside_article_range"])
        )
    rows.append("")
    rows.append("Nie wolno automatycznie zatwierdzić żadnego dnia tym raportem.")
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("organizer")
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    q = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    o = json.loads(Path(args.organizer).read_text(encoding="utf-8"))
    report = compare(q, o)
    for name, data in (
        (args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(report)),
    ):
        target = Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")
    print(report["league_id"], "official press comparison:",
          sum(v["identical_fixture_count"] for v in report["days"].values()),
          "matches; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
