"""Compare direct KNVB Eredivisie fixture facts against ESPN; no signoff."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, knvb):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid ESPN queue")
    if (not isinstance(knvb, dict)
            or knvb.get("schema") != "kb21-official-knvb-eredivisie-v1"
            or knvb.get("league_id") != "ned.1"
            or set(knvb.get("days", [])) != set(queue["days"])
            or not isinstance(knvb.get("by_day"), dict)):
        raise ValueError("KNVB source schema/scope mismatch")
    days = {}
    for day in sorted(queue["days"]):
        official = knvb["by_day"].get(day)
        if not isinstance(official, list):
            raise ValueError("Missing official day bucket")
        candidates = [f for f in queue["fixtures"]
                      if f.get("date_warsaw") == day
                      and str(f.get("fixture_id", "")).startswith("ned.1:")]
        used = set()
        statuses = Counter()
        rows = []
        for candidate in candidates:
            name_parts = str(candidate.get("fixture", "")).split(" - ", 1)
            when = _instant(candidate.get("kickoff"))
            if len(name_parts) != 2 or when is None:
                matching_indices, status = [], "INVALID_ESPN_FIXTURE"
            else:
                pair = tuple(_team("ned.1", x) for x in name_parts)
                matching_indices = [i for i, fixture in enumerate(official)
                                    if tuple(_team("ned.1", fixture.get(k))
                                             for k in ("home", "away")) == pair]
                if not matching_indices:
                    status = "NOT_ON_KNVB_VISIBLE_PROGRAM"
                elif len(matching_indices) > 1:
                    status = "DUPLICATE_KNVB_TEAM_PAIR"
                else:
                    idx = matching_indices[0]
                    official_time = _instant(official[idx].get("kickoff_utc"))
                    if official_time is None:
                        status = "INVALID_KNVB_KICKOFF"
                    elif abs((when - official_time).total_seconds()) > 300:
                        status = "START_TIME_CONFLICT"
                    elif idx in used:
                        status = "DUPLICATE_ESPN_CANDIDATE"
                    else:
                        status = "MATCHED_FOR_REVIEW"
                    used.add(idx)
            statuses[status] += 1
            rows.append({
                "fixture_id": candidate.get("fixture_id"),
                "fixture": candidate.get("fixture"),
                "espn_kickoff": candidate.get("kickoff"),
                "status": status,
                "knvb_kickoff": official[matching_indices[0]].get("kickoff_warsaw")
                    if len(matching_indices) == 1 else None,
            })
        only = [r for i, r in enumerate(official) if i not in used]
        statuses["KNVB_ONLY"] += len(only)
        days[day] = {
            "knvb_visible_count": len(official), "espn_candidate_count": len(candidates),
            "matched": statuses["MATCHED_FOR_REVIEW"],
            "statuses": dict(statuses), "comparisons": rows,
            "knvb_only": only,
            "day_found_in_knvb_page": day not in knvb.get("unconfirmed_zero_dates", []),
            "full_day_signed": False,
        }
    return {
        "schema": "kb21-knvb-crosscheck-v1", "league_id": "ned.1",
        "source": knvb.get("official_url"), "days": days,
        "source_errors": knvb.get("errors", []),
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "reviewer_signed": False,
        "note": ("Direct KNVB program, but not a complete independently signed fixture audit. "
                 "Missing or empty dates are not proof of no games."),
    }


def render(report):
    result = ["# KB Score 2.1 — KNVB Eredivisie kontra ESPN", "",
              "**DIAGNOSTYKA / NO PLAY — Calendar Gate BLOCKED**", "",
              "| Dzień | KNVB | ESPN | Zgodne | Niepotwierdzone |",
              "|---|---:|---:|---:|---:|"]
    for day, row in sorted(report["days"].items()):
        issues = row["espn_candidate_count"] - row["matched"] + len(row["knvb_only"])
        result.append(f"| {day} | {row['knvb_visible_count']} | {row['espn_candidate_count']} | "
                      f"{row['matched']} | {issues} |")
        if not row["day_found_in_knvb_page"]:
            result.append(f"- {day}: brak daty na widocznej stronie KNVB; "
                          "NIE potwierdzono zera spotkań.")
        for f in row["comparisons"]:
            if f["status"] != "MATCHED_FOR_REVIEW":
                result.append(f"- {day}: {f['fixture']}: {f['status']}; "
                              f"ESPN {f['espn_kickoff']}; KNVB {f['knvb_kickoff']}")
        for f in row["knvb_only"]:
            result.append(f"- {day}: tylko KNVB: {f['home']} - {f['away']} "
                          f"({f['kickoff_warsaw']})")
    if report["source_errors"]:
        result.extend(["", "Problemy źródła KNVB:"] +
                      ["- " + str(e) for e in report["source_errors"]])
    result.append("\nDane wymagają podpisanej kontroli kompletności wszystkich lig. Brak PLAY.")
    return "\n".join(result) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("knvb")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    with open(a.queue, encoding="utf8") as source:
        queue = json.load(source)
    with open(a.knvb, encoding="utf8") as source:
        knvb = json.load(source)
    report = compare(queue, knvb)
    for name, value in (
        (a.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(report)),
    ):
        dest = Path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding="utf8")
    print("KNVB official vs ESPN:",
          sum(x["matched"] for x in report["days"].values()),
          "matches; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
