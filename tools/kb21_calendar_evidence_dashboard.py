"""Three-day KB21 organizer evidence dashboard, with strict NO-PLAY semantics.

Consolidates existing *diagnostic* official-source comparisons. Distinguishes
candidate matching from complete organizer calendar attestation, including
empty days. Does not approve any game, amend source records or score markets.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_official_review import OFFICIAL_PAGES

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
    # UEFA dated league-phase news only: team/date, NEVER time-verified pairs.
    "uefa.champions": ("official-uefa-champions-vs-espn.json", "official-uefa-champions.json", "UEFA_ARTICLE_DATE_TEAMS_ONLY"),
    "uefa.europa": ("official-uefa-europa-vs-espn.json", "official-uefa-europa.json", "UEFA_ARTICLE_DATE_TEAMS_ONLY"),
    "uefa.europa.conf": ("official-uefa-conference-vs-espn.json", "official-uefa-conference.json", "UEFA_ARTICLE_DATE_TEAMS_ONLY"),
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
    # Other tournaments and malformed fixture identifiers must never disappear
    # silently from the 14-competition diagnostic denominator.
    for event in queue["fixtures"]:
        if not isinstance(event, dict) or event.get("date_warsaw") not in days:
            raise ValueError("Fixture outside reviewed dates or invalid record")
        if not isinstance(event.get("fixture_id"), str) or not event["fixture_id"]:
            raise ValueError("Missing or invalid fixture identifier")
    untracked = [
        event["fixture_id"] for event in queue["fixtures"]
        if not any(event["fixture_id"].startswith(league + ":")
                   for league in COMPETITIONS)
    ]
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
            date_team_only = 0
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
                    if source_scope == "UEFA_ARTICLE_DATE_TEAMS_ONLY":
                        date_team_only = comp_day.get("date_team_matched", 0)
                        if (not isinstance(date_team_only, int)
                                or date_team_only < 0 or date_team_only > candidates
                                or matched != 0
                                or facts.get("kickoff_timezone_verified") is not False):
                            raise ValueError("Untrusted UEFA time-approval claim")
                        if source_errors:
                            state = "SOURCE_ISSUES_REQUIRING_REVIEW"
                        elif candidates and date_team_only == candidates and organizer_visible == candidates:
                            state = "DATE_TEAMS_ONLY_TIME_UNVERIFIED"
                        elif candidates:
                            state = "MISSING_OR_CONFLICTING_CANDIDATES"
                        elif organizer_visible:
                            state = "ORGANIZER_ONLY_FIXTURES"
                        else:
                            state = "NO_GAME_EVIDENCE_NOT_ZERO_CERTIFICATION"
                    elif matched < candidates:
                        state = "MISSING_OR_CONFLICTING_CANDIDATES"
                    elif organizer_visible > matched:
                        state = "ORGANIZER_ONLY_FIXTURES"
                    elif source_errors:
                        state = "SOURCE_ISSUES_REQUIRING_REVIEW"
                    elif candidates == 0:
                        state = "NO_GAME_EVIDENCE_NOT_ZERO_CERTIFICATION"
                    else:
                        state = "PAIRED_FIXTURES_FOR_REVIEW"
            # A clear human-review queue must not mistake matching pairs,
            # missing source adapters or both-provider zeros for signoff.
            if candidates and state in (
                    "MISSING_OR_CONFLICTING_CANDIDATES",
                    "ORGANIZER_ONLY_FIXTURES", "SOURCE_ISSUES_REQUIRING_REVIEW",
                    "DIRECT_SOURCE_MISSING", "NO_DIRECT_ORGANIZER_ADAPTER",
                    "DATE_TEAMS_ONLY_TIME_UNVERIFIED"):
                next_action = "RESOLVE_OFFICIAL_SOURCE_OR_FIXTURE_CONFLICT"
                review_priority = 1
            elif candidates:
                next_action = "VERIFY_FULL_ORGANIZER_DAY_AND_SIGN"
                review_priority = 2
            else:
                next_action = "VERIFY_OFFICIAL_ZERO_OR_MISSING_FIXTURES"
                review_priority = 3
            day_audit = gate["days"][day]
            if not isinstance(day_audit, dict):
                raise ValueError("Invalid calendar day audit")
            output["rows"].append({
                "day": day, "league_id": league, "competition": title,
                "espn_candidates": candidates, "paired_for_review": matched,
                "date_team_only_matches": date_team_only,
                "organizer_rows_visible": organizer_visible,
                "direct_evidence_scope": source_scope,
                "evidence_status": state, "source_errors": source_errors[:10],
                "adapter_source": adapter_source,
                "adapter_comparison": adapter_comparison,
                "full_day_signed": official_day_reviewed,
                "organizer_review_url": OFFICIAL_PAGES.get(league),
                "next_action": next_action,
                "review_priority": review_priority,
                "calendar_gate": "BLOCKED" if gate["calendar_gate"] == "BLOCKED" else "REQUIRES_OTHER_GATES",
            })
    kinds = Counter(row["evidence_status"] for row in output["rows"])
    paired_total = sum(row["paired_for_review"] for row in output["rows"])
    output["totals"] = {
        "league_day_cells": len(output["rows"]),
        "league_count": len(COMPETITIONS),
        "days_count": len(days),
        "candidate_fixtures": len(queue["fixtures"]),
        "paired_for_review": paired_total,
        "date_team_only_not_time_approved": sum(row["date_team_only_matches"] for row in output["rows"]),
        "unpaired_candidates": len(queue["fixtures"]) - paired_total,
        "outside_competition_scope": len(untracked),
        "outside_competition_scope_ids": sorted(set(untracked))[:20],
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
        f"Poza 14 kategoriami rozgrywek: {totals['outside_competition_scope']} "
        f"(wliczone do niedopasowanych).",
        f"UEFA - pary data/kluby BEZ potwierdzenia czasu: "
        f"{totals['date_team_only_not_time_approved']} (NIE wliczane do zgodnych).",
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
    if totals["outside_competition_scope"]:
        lines.append(
            "- WYKRYTO MECZE POZA ZAKRESEM 14 ROZGRYWEK: "
            + ", ".join(totals["outside_competition_scope_ids"])
            + "; wymagają osobnego audytu i nie są potwierdzonymi meczami."
        )
    for item in report["rows"]:
        if item["evidence_status"] in ("MISSING_OR_CONFLICTING_CANDIDATES",
                                       "DATE_TEAMS_ONLY_TIME_UNVERIFIED",
                                       "ORGANIZER_ONLY_FIXTURES",
                                       "SOURCE_ISSUES_REQUIRING_REVIEW",
                                       "DIRECT_SOURCE_MISSING"):
            lines.append(f"- {item['day']} {item['league_id']}: {item['evidence_status']}"
                         + (f"; błędy: {item['source_errors'][:2]}" if item["source_errors"] else ""))
    lines += ["", "### Praktyczna kolejka kontroli oficjalnego terminarza", "",
              "Kolejność: (1) błędy i brakujące dowody przy meczach, "
              "(2) pełna inwentaryzacja rozgrywek z meczami, "
              "(3) potwierdzenie dni bez spotkań. "
              "Wszystkie pozycje wymagają ręcznej weryfikacji, także 0 meczów.", ""]
    for day in report["days"]:
        lines.append(f"#### {day}")
        for item in sorted((row for row in report["rows"] if row["day"] == day),
                           key=lambda r: (r["review_priority"], -r["espn_candidates"],
                                          r["league_id"])):
            url = item["organizer_review_url"]
            source = f"[źródło organizatora]({url})" if url else "BRAK OFICJALNEGO ADRESU"
            lines.append(
                f"- P{item['review_priority']} {item['competition']} "
                f"(ESPN {item['espn_candidates']}, porównane {item['paired_for_review']}): "
                f"{item['next_action']}; {source}; "
                f"stan źródła: {item['evidence_status']}"
            )
        lines.append("")
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
