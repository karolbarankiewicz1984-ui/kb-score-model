"""Three-day KB21 organizer evidence dashboard, with strict NO-PLAY semantics.

Consolidates existing *diagnostic* official-source comparisons. Distinguishes
candidate matching from complete organizer calendar attestation, including
empty days. Does not approve any game, amend source records or score markets.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

COMPETITIONS = {
    "eng.1": "Premier League", "esp.1": "La Liga",
    "ita.1": "Serie A", "ger.1": "Bundesliga",
    "fra.1": "Ligue 1", "por.1": "Liga Portugal",
    "ned.1": "Eredivisie", "bel.1": "Belgian Pro League",
    "tur.1": "Süper Lig", "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
    "uefa.nations": "Nations League",
    "fifa.worldq.uefa": "European Qualifiers",
}

# These are ONLY diagnostics of a fixture source against another data provider.
# Neither a matching pair nor a missing row proves calendar completeness.
ADAPTERS = {
    "eng.1": ("official-fpl-vs-espn.json", "official-fpl-premier-league.json", "FULL_SEASON_FPL"),
    "esp.1": ("official-laliga-vs-espn.json", "official-laliga.json", "SAMPLED_ROUNDS"),
    "ita.1": ("official-press-serie-a-vs-espn.json", "official-press-serie-a.json", "DATED_PRESS"),
    "ger.1": ("official-dfl-vs-espn.json", "official-dfl-bundesliga.json", "ONE_VISIBLE_ROUND"),
    "fra.1": ("official-press-ligue1-vs-espn.json", "official-press-ligue1.json", "DATED_PRESS"),
    "ned.1": ("official-knvb-vs-espn.json", "official-knvb-eredivisie.json", "VISIBLE_KNVB_PROGRAM"),
    "tur.1": ("official-tff-vs-espn.json", "official-tff-superlig.json", "ONE_VISIBLE_ROUND"),
    "por.1": ("official-portugal-vs-espn.json", "official-portugal-postponement.json", "ONE_CLUB_POSTPONEMENT"),
}

def _read(folder, name):
    file = folder / name
    if not file.is_file():
        return None
    return json.loads(file.read_text(encoding="utf-8"))

def summarize(queue, gate, directory):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid candidate queue")
    days = queue["days"]
    if not 1 <= len(days) <= 3 or len(set(days)) != len(days):
        raise ValueError("Expected 1–3 distinct dates")
    if (not isinstance(gate, dict) or gate.get("calendar_gate") not in
            {"BLOCKED", "PASS_MANUAL"} or set(gate.get("days", {})) != set(days)):
        raise ValueError("Calendar Gate scope mismatch or missing audit")
    folder = Path(directory)
    output = {"schema": "kb21-calendar-evidence-dashboard-v1",
              "days": days, "calendar_gate": gate["calendar_gate"],
              "publication": "DIAGNOSTIC / NO PLAY",
              "safe_to_publish_play": False, "organizer_complete_day_verified": False,
              "review_only": True, "rows": [], "totals": {},
              "note": ("Matches with external sources are not signed organizer calendars. "
                       "A zero-game cell never certifies that no match exists. "
                       "Dashboard cannot grant PASS, PLAY or historical observation N.")}
    adapters = {}
    for league, (compare_file, facts_file, coverage) in ADAPTERS.items():
        comparison = _read(folder, compare_file)
        facts = _read(folder, facts_file)
        if (comparison is not None and
                (not isinstance(comparison, dict)
                 or comparison.get("calendar_gate") != "BLOCKED"
                 or not isinstance(comparison.get("days"), dict)
                 or set(comparison["days"]) != set(days))):
            raise ValueError("Untrusted or mismatched comparator: " + compare_file)
        if (facts is not None and
                (not isinstance(facts, dict) or facts.get("league_id") != league
                 or facts.get("calendar_gate") != "BLOCKED"
                 or set(facts.get("days", [])) != set(days))):
            raise ValueError("Untrusted or mismatched official source: " + facts_file)
        adapters[league] = (comparison, facts, coverage, compare_file, facts_file)
    for day in days:
        for league, title in COMPETITIONS.items():
            candidates = sum(1 for event in queue["fixtures"]
                             if event.get("date_warsaw") == day
                             and str(event.get("fixture_id", "")).startswith(league + ":"))
            matched = 0
            source_errors = []
            organizer_visible = None
            source_scope = "NO_DIRECT_MACHINE_ADAPTER"
            adapter_comparison = None
            adapter_source = None
            official_day_reviewed = False
            if league not in adapters:
                state = "NO_DIRECT_ORGANIZER_ADAPTER"
            else:
                comparison, facts, source_scope, adapter_comparison, adapter_source = adapters[league]
                if comparison is None or facts is None:
                    state = "DIRECT_SOURCE_MISSING"
                else:
                    facts_day = facts.get("by_day", {}).get(day)
                    comp_day = comparison["days"].get(day)
                    if not isinstance(facts_day, list) or not isinstance(comp_day, dict):
                        raise ValueError(f"Incomplete adapter day {league}/{day}")
                    organizer_visible = len(facts_day)
                    statuses = comp_day.get("statuses", {})
                    if not isinstance(statuses, dict):
                        raise ValueError("Malformed match statuses")
                    matched = statuses.get("MATCHED_FOR_REVIEW", 0)
                    if not isinstance(matched, int) or matched < 0 or matched > candidates:
                        raise ValueError(f"Impossible source coincidences {league}/{day}")
                    source_errors = list(facts.get("errors", []))
                    if matched < candidates:
                        state = "MISSING_OR_CONFLICTING_CANDIDATES"
                    elif organizer_visible > matched:
                        state = "ORGANIZER_ONLY_FIXTURES"
                    elif source_errors:
                        state = "SOURCE_ISSUES_REQUIRING_REVIEW"
                    elif candidates == 0:
                        state = "NO_GAME_EVIDENCE_NOT_ZERO_CERTIFICATION"
                    else:
                        state = "PAIRED_FIXTURES_FOR_REVIEW"
            day_audit = gate["days"][day]
            if not isinstance(day_audit, dict):
                raise ValueError("Invalid calendar day audit")
            output["rows"].append({
                "day": day, "league_id": league, "competition": title,
                "espn_candidates": candidates, "paired_for_review": matched,
                "organizer_rows_visible": organizer_visible,
                "direct_evidence_scope": source_scope,
                "evidence_status": state, "source_errors": source_errors[:10],
                "adapter_source": adapter_source,
                "adapter_comparison": adapter_comparison,
                "full_day_signed": official_day_reviewed,
                "calendar_gate": "BLOCKED" if gate["calendar_gate"] == "BLOCKED" else "REQUIRES_OTHER_GATES",
            })
    kinds = Counter(row["evidence_status"] for row in output["rows"])
    output["totals"] = {
        "league_day_cells": len(output["rows"]),
        "league_count": len(COMPETITIONS),
        "days_count": len(days),
        "candidate_fixtures": len(queue["fixtures"]),
        "paired_for_review": sum(x["paired_for_review"] for x in output["rows"]),
        "unpaired_candidates": sum(x["espn_candidates"] - x["paired_for_review"] for x in output["rows"]),
        "direct_adapters": len(ADAPTERS),
        "without_direct_adapters": len(COMPETITIONS) - len(ADAPTERS),
        "cells_by_status": dict(sorted(kinds.items())),
        "manual_gate_errors": sum(len(gate["days"][day].get("errors", [])) for day in days),
        "days_passed_manual_gate": sum(gate["days"][day].get("calendar_gate") == "PASS_MANUAL"
                                       for day in days),
    }
    # No direct source can sign a calendar in this dashboard.
    return output

def render(report):
    totals = report["totals"]
    lines = [
        "# KB Score 2.1 — trzydniowa mapa gotowości terminarza",
        "",
        "**WYŁĄCZNIE DIAGNOSTYKA — NIE PLAY**", "",
        f"Dni: {', '.join(report['days'])}",
        f"Calendar Gate: **{report['calendar_gate']}**",
        f"Kandydaci: {totals['candidate_fixtures']}; zgodność par do weryfikacji: "
        f"{totals['paired_for_review']}; niedopasowane: {totals['unpaired_candidates']}",
        f"Bezpośrednie adaptery: {totals['direct_adapters']}/{totals['league_count']} lig; "
        f"nadal bez adaptera: {totals['without_direct_adapters']}",
        f"Braki formalnego audytu: {totals['manual_gate_errors']} powodów; "
        f"zatwierdzone dni: {totals['days_passed_manual_gate']}/{totals['days_count']}.",
        "",
        "| Dzień | Liga | ESPN | Zgodne | Oficjalna lista | Zakres źródła | Stan |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for item in report["rows"]:
        count = (str(item["organizer_rows_visible"])
                 if item["organizer_rows_visible"] is not None else "—")
        lines.append(
            f"| {item['day']} | {item['league_id']} | {item['espn_candidates']} | "
            f"{item['paired_for_review']} | {count} | "
            f"{item['direct_evidence_scope']} | {item['evidence_status']} |"
        )
    lines += ["", "### Ważne blokady", ""]
    for item in report["rows"]:
        if item["evidence_status"] in ("MISSING_OR_CONFLICTING_CANDIDATES",
                                       "ORGANIZER_ONLY_FIXTURES",
                                       "SOURCE_ISSUES_REQUIRING_REVIEW",
                                       "DIRECT_SOURCE_MISSING"):
            lines.append(f"- {item['day']} {item['league_id']}: {item['evidence_status']}"
                         + (f"; błędy: {item['source_errors'][:2]}" if item["source_errors"] else ""))
    lines += ["",
              "Zgodność źródeł nie dowodzi pełnego terminarza. "
              "Dni bez widocznych spotkań są NIEPOTWIERDZONE, a nie zatwierdzone jako puste.",
              "Dopóki Calendar Gate jest BLOCKED, raport nie może generować PLAY, "
              "P(model) ani nowych historycznych obserwacji.", ""]
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("gate")
    parser.add_argument("--sources-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    gate = json.loads(Path(args.gate).read_text(encoding="utf-8"))
    report = summarize(queue, gate, args.sources_dir)
    for name, content in (
        (args.output_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.output_md, render(report))):
        dest = Path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    print("KB21 organizer readiness:", report["totals"], "NO PLAY")

if __name__ == "__main__":
    main()
