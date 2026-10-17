"""Unsigned TFF organizer fixture comparison against ESPN KB21 candidates."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, organizer):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Expected ESPN assessment queue")
    if (not isinstance(organizer, dict)
            or organizer.get("schema") != "kb21-official-tff-superlig-v1"
            or organizer.get("league_id") != "tur.1"
            or set(organizer.get("days", [])) != set(queue["days"])
            or not isinstance(organizer.get("by_day"), dict)):
        raise ValueError("TFF fixture source schema/scope mismatch")
    trusted_capture = (organizer.get("status") ==
                       "OFFICIAL_TFF_MATCHWEEK_PARTIAL_FOR_REVIEW"
                       and not organizer.get("errors"))
    days = {}
    for day in sorted(queue["days"]):
        facts = organizer["by_day"].get(day)
        if not isinstance(facts, list):
            raise ValueError("Missing TFF day bucket")
        candidates = [f for f in queue["fixtures"]
                      if f.get("date_warsaw") == day
                      and str(f.get("fixture_id", "")).startswith("tur.1:")]
        statuses, comparisons, used = Counter(), [], set()
        for candidate in candidates:
            names = str(candidate.get("fixture", "")).split(" - ", 1)
            moment = _instant(candidate.get("kickoff"))
            matches = []
            if not trusted_capture:
                status = "UNRELIABLE_TFF_MATCHWEEK"
            elif len(names) != 2 or moment is None:
                status = "INVALID_ESPN_FIXTURE"
            else:
                teams = tuple(_team("tur.1", name) for name in names)
                matches = [i for i, fact in enumerate(facts)
                           if tuple(_team("tur.1", fact.get(k)) for k in
                                    ("home", "away")) == teams]
                if len(matches) > 1:
                    status = "DUPLICATE_TFF_PAIR"
                elif not matches:
                    status = "NOT_ON_VISIBLE_TFF_MATCHWEEK"
                else:
                    index = matches[0]
                    other = _instant(facts[index].get("kickoff_utc"))
                    if other is None:
                        status = "INVALID_TFF_KICKOFF"
                    elif abs((moment-other).total_seconds()) > 300:
                        status = "START_TIME_CONFLICT"
                    elif index in used:
                        status = "DUPLICATE_ESPN_CANDIDATE"
                    else:
                        status = "MATCHED_FOR_REVIEW"
                    used.add(index)
            statuses[status] += 1
            comparisons.append({
                "fixture": candidate.get("fixture"),
                "fixture_id": candidate.get("fixture_id"),
                "espn_kickoff": candidate.get("kickoff"),
                "tff_kickoff": (facts[matches[0]].get("kickoff_warsaw")
                                if len(matches) == 1 else None),
                "status": status,
            })
        extra = [x for i, x in enumerate(facts) if i not in used]
        statuses["TFF_ONLY"] += len(extra)
        days[day] = {
            "tff_visible": len(facts), "espn_candidates": len(candidates),
            "matched": statuses["MATCHED_FOR_REVIEW"], "statuses": dict(statuses),
            "comparisons": comparisons, "tff_only": extra,
            "official_day_complete": False,
            "visible_page_contains_date": day not in organizer.get("unconfirmed_zero_dates", []),
        }
    return {
        "schema": "kb21-tff-crosscheck-v1", "league_id": "tur.1",
        "source": organizer.get("official_url"), "days": days,
        "source_errors": organizer.get("errors", []),
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "reviewer_signed": False,
        "note": "TFF selected matchweek does not certify the entire season or all postponed games; no automatic signoff or PLAY.",
    }


def render(report):
    lines = ["# KB Score 2.1 — oficjalny TFF kontra ESPN", "",
             "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
             "| Dzień | TFF | ESPN | Zgodne | Niepotwierdzone |",
             "|---|---:|---:|---:|---:|"]
    for day, info in sorted(report["days"].items()):
        differences = info["espn_candidates"]-info["matched"]+len(info["tff_only"])
        lines.append(f"| {day} | {info['tff_visible']} | {info['espn_candidates']} | "
                     f"{info['matched']} | {differences} |")
        if not info["visible_page_contains_date"]:
            lines.append(f"- {day}: brak daty w widocznej kolejce TFF, nie potwierdzono braku gier.")
        for row in info["comparisons"]:
            if row["status"] != "MATCHED_FOR_REVIEW":
                lines.append(f"- {day} {row['fixture']}: {row['status']}; "
                             f"ESPN {row['espn_kickoff']}, TFF {row['tff_kickoff']}")
        for row in info["tff_only"]:
            lines.append(f"- {day} tylko TFF {row['home']}–{row['away']}: {row['kickoff_warsaw']}")
    if report["source_errors"]:
        lines.append("Błędy źródła: " + ", ".join(map(str, report["source_errors"])))
    lines.append("\nWciąż nie jest to zatwierdzony pełny terminarz.")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("tff")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    q = json.loads(Path(a.queue).read_text(encoding="utf-8"))
    official = json.loads(Path(a.tff).read_text(encoding="utf-8"))
    result = compare(q, official)
    for name, body in (
        (a.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(result)),
    ):
        dest = Path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
    print("TFF official vs ESPN:",
          sum(row["matched"] for row in result["days"].values()),
          "matches; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
