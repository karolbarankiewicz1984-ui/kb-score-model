"""Compare direct KNVB Eredivisie fixture facts against ESPN; no signoff."""
import argparse
from collections import Counter
import json
from datetime import timezone
from pathlib import Path
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team


def compare(queue, knvb, results=None):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid ESPN queue")
    if (not isinstance(knvb, dict)
            or knvb.get("schema") != "kb21-official-knvb-eredivisie-v1"
            or knvb.get("league_id") != "ned.1"
            or set(knvb.get("days", [])) != set(queue["days"])
            or not isinstance(knvb.get("by_day"), dict)):
        raise ValueError("KNVB source schema/scope mismatch")
    # KNVB moves started/completed matches off the current 'programma'
    # page. The 'uitslagen' page is a DATE/CLUB hint only, never an
    # authenticated pre-match kickoff or evidence of full-day completeness.
    usable_results = False
    capture = None
    if results is not None:
        from tools.kb21_official_knvb_results import SOURCE as RESULTS_URL
        if (not isinstance(results, dict)
                or results.get("schema") != "kb21-knvb-results-date-pair-v1"
                or results.get("league_id") != "ned.1"
                or results.get("official_url") != RESULTS_URL
                or set(results.get("days", [])) != set(queue["days"])
                or not isinstance(results.get("by_day"), dict)
                or results.get("calendar_gate") != "BLOCKED"
                or results.get("prematch_calendar_verified") is not False
                or results.get("official_kickoff_verified") is not False
                or results.get("full_day_verified") is not False
                or results.get("reviewer_signed") is not False
                or results.get("confirmed_zero_matches") is not False):
            raise ValueError("Unsafe KNVB result-page evidence")
        capture = _instant(results.get("captured_at_utc"))
        if capture is None:
            raise ValueError("KNVB results-page capture is not timezone-aware")
        usable_results = (results.get("status") == "KNVB_RESULTS_DATE_PAIRS_PARTIAL"
                          and results.get("errors") == [])
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
        result_pairs = results["by_day"].get(day) if results is not None else []
        if not isinstance(result_pairs, list):
            raise ValueError("Missing KNVB results-date bucket")
        for evidence in result_pairs:
            if (not isinstance(evidence, dict)
                    or evidence.get("date_printed") != day
                    or evidence.get("league_id") != "ned.1"
                    or evidence.get("kickoff_time_verified") is not False
                    or evidence.get("match_result_verified") is not False
                    or evidence.get("kickoff_utc") is not None):
                raise ValueError("Unsafe KNVB results-row evidence")
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
                    if usable_results and capture >= when:
                        from_results = [
                            item for item in result_pairs
                            if tuple(_team("ned.1", item.get(k))
                                     for k in ("home", "away")) == pair
                        ]
                        if len(from_results) == 1:
                            status = "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF"
                        elif len(from_results) > 1:
                            status = "AMBIGUOUS_KNVB_RESULTS_DATE_PAIR"
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
                "knvb_results_date_team_only": (
                    status == "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF"),
                "results_page_captured_at_utc": results.get("captured_at_utc")
                    if (results is not None and
                        status == "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF") else None,
                "kickoff_verified_from_results": False,
            })
        only = [r for i, r in enumerate(official) if i not in used]
        statuses["KNVB_ONLY"] += len(only)
        days[day] = {
            "knvb_visible_count": len(official), "espn_candidate_count": len(candidates),
            "matched": statuses["MATCHED_FOR_REVIEW"],
            "post_start_result_date_pairs": statuses[
                "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF"],
            "statuses": dict(statuses), "comparisons": rows,
            "knvb_only": only,
            "day_found_in_knvb_page": day not in knvb.get("unconfirmed_zero_dates", []),
            "full_day_signed": False,
        }
    return {
        "schema": "kb21-knvb-crosscheck-v1", "league_id": "ned.1",
        "source": knvb.get("official_url"), "days": days,
        "source_errors": knvb.get("errors", []),
        "results_page_source": results.get("official_url") if results is not None else None,
        "results_page_only": True,
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "reviewer_signed": False,
        "note": ("Direct KNVB program may hide matches after kickoff; "
                 "the KNVB results page can corroborate a DATE/CLUB pair "
                 "after start but NEVER pre-match kickoff, complete day or score. "
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
    p.add_argument("--results")
    p.add_argument("--output", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    with open(a.queue, encoding="utf8") as source:
        queue = json.load(source)
    with open(a.knvb, encoding="utf8") as source:
        knvb = json.load(source)
    results = None
    if a.results:
        with open(a.results, encoding="utf8") as source:
            results = json.load(source)
    report = compare(queue, knvb, results=results)
    for name, value in (
        (a.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(report)),
    ):
        dest = Path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding="utf8")
    print("KNVB official vs ESPN:",
          sum(x["matched"] for x in report["days"].values()),
          "pre-start time-agreement pairs;",
          sum(x["post_start_result_date_pairs"] for x in report["days"].values()),
          "post-start result-page team/date hints; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
