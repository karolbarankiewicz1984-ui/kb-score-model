"""Show REAL calendar evidence progress rather than re-counting empty template errors.

The live validator historically checked an empty template (206 predictable
errors), while eight actual organizer source adapters had already populated
a separate unsigned draft. This report runs the SAME signoff validator on
BOTH, compares blockers by league/day, and NEVER adds review signatures,
certifies zero-game days, or changes PLAY/P(model)/historical N.

The prepared draft may have fewer *data* issues, but MUST have 42 missing
human reviews and remain BLOCKED. Those human requirements are intentionally
not reduced by this report.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.kb21_calendar_signoff import validate
from tools.kb21_calendar_coverage import SCOPE


def _checks(result):
    checks = {}
    for day, data in result["days"].items():
        for row in data["competitions"]:
            key = day, row["league_id"]
            if key in checks:
                raise ValueError("Duplicate league/day validator cell")
            checks[key] = tuple(row["errors"])
    return checks


def _count(checks):
    return Counter(error for errors in checks.values() for error in errors)


def _unsigned_inventory(queue, template, draft):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(template, dict) or not isinstance(draft, dict)):
        raise ValueError("Expected queue and two inventories")
    days = queue["days"]
    if (not 1 <= len(days) <= 3
            or len(set(days)) != len(days)
            or set(template.get("days", {})) != set(days)
            or set(draft.get("days", {})) != set(days)):
        raise ValueError("Review window mismatch")
    for source in (template, draft):
        if source.get("approval") is not None:
            raise ValueError("Prepared progress report refuses signed global approval")
        daily = source.get("daily_approvals") or {}
        if (not isinstance(daily, dict)
                or set(daily) - set(days)
                or any(value is not None for value in daily.values())):
            raise ValueError("Prepared progress refuses signed daily approvals")
        for day in days:
            slots = source["days"][day]
            if not isinstance(slots, dict) or set(slots) != set(SCOPE):
                raise ValueError("Prepared review requires all 14 competitions per date")
            for league in SCOPE:
                row = slots[league]
                if (not isinstance(row, dict)
                        or row.get("reviewer")
                        or row.get("captured_at") is not None
                        or row.get("full_day_checked") is True
                        or row.get("confirmed_zero_matches") is True):
                    raise ValueError("Prepared progress cannot include human signoffs")
                if not isinstance(row.get("fixtures"), list):
                    raise ValueError("Prepared progress requires fixture lists")
    return days


def analyze(queue, empty_template, prepared_draft):
    days = _unsigned_inventory(queue, empty_template, prepared_draft)
    baseline = validate(queue, empty_template)
    prepared = validate(queue, prepared_draft)
    if (baseline.get("calendar_gate") != "BLOCKED"
            or prepared.get("calendar_gate") != "BLOCKED"
            or baseline.get("approved_days") != 0
            or prepared.get("approved_days") != 0
            or prepared.get("manual_source_attestation") is not False
            or prepared.get("safe_to_publish_play") is not False):
        raise ValueError("No unsigned comparison may approve the calendar")
    before, after = _checks(baseline), _checks(prepared)
    expected = {(day, league) for day in days for league in SCOPE}
    if set(before) != expected or set(after) != expected:
        raise ValueError("Validator result missing competition-day entries")
    baseline_counts, prepared_counts = _count(before), _count(after)
    resolved = baseline_counts - prepared_counts
    introduced = prepared_counts - baseline_counts
    per_day = []
    for day in sorted(days):
        for league in SCOPE:
            key = day, league
            draft_slot = prepared_draft["days"][day][league]
            source_url = draft_slot.get("organizer_facts_source")
            source_capture = draft_slot.get("organizer_facts_capture_utc")
            scoped = draft_slot.get("organizer_source_catalogue_kind")
            per_day.append({
                "day": day, "league_id": league,
                "prefilled_fixture_rows": len(draft_slot["fixtures"]),
                "machine_source_url": source_url,
                "machine_source_capture_utc": source_capture,
                "machine_source_scope": scoped,
                "source_proof_is_human_signature": False,
                "baseline_errors": list(before[key]),
                "prepared_errors": list(after[key]),
                "resolved_error_codes": sorted(set(before[key]) - set(after[key])),
                "introduced_error_codes": sorted(set(after[key]) - set(before[key])),
                "reviewer": None,
                "human_review_complete": False,
                "calendar_gate": "BLOCKED",
            })
    return {
        "schema": "kb21-calendar-real-progress-v1",
        "days": sorted(days),
        "baseline": {
            "source": "EMPTY_TEMPLATE",
            "missing_evidence_occurrences": sum(baseline_counts.values()),
            "errors_by_code": dict(sorted(baseline_counts.items())),
        },
        "prepared": {
            "source": "CURRENT_UNSIGNED_OFFICIAL_FACTS_DRAFT",
            "missing_evidence_occurrences": sum(prepared_counts.values()),
            "errors_by_code": dict(sorted(prepared_counts.items())),
            "fixture_rows_ready_for_human_inspection": sum(
                row["prefilled_fixture_rows"] for row in per_day),
            "cells_with_prefilled_fixture_rows": sum(
                row["prefilled_fixture_rows"] > 0 for row in per_day),
            "cells_with_machine_capture_metadata": sum(
                row["machine_source_capture_utc"] is not None for row in per_day),
        },
        "actual_blockers_resolved_vs_template": dict(sorted(resolved.items())),
        "new_or_more_visible_blockers": dict(sorted(introduced.items())),
        "net_reduction_in_formal_errors": (
            sum(baseline_counts.values()) - sum(prepared_counts.values())),
        "competition_day_cells": len(expected),
        "human_reviewed_cells": 0,
        "human_approval_days": 0,
        "gate": "BLOCKED", "calendar_gate": "BLOCKED",
        "safe_to_publish_play": False, "publication": "DIAGNOSTIC / NO PLAY",
        "rows": per_day,
        "note": (
            "The empty-template 206 baseline is NOT the count of substantive "
            "missing match facts after source prefill. Using the original "
            "signoff validator on the current UNSIGNED draft measures actual "
            "evidence preparation without relaxing required human review, "
            "source completeness, zero-game proof, prematch timestamps, "
            "independent comparisons or the first-kickoff deadline. "
            "A machine-source capture metadata field is NOT the signed "
            "'captured_at' reviewer field. No retrospective signoff."
        ),
    }


def render(report):
    before = report["baseline"]
    after = report["prepared"]
    out = [
        "# KB Score 2.1 — rzeczywisty postęp zamiast pustego szablonu",
        "", "**TYLKO DIAGNOSTYKA, 0 PODPISÓW, NIE PLAY**", "",
        "Kolejny raport pokazuje DWIE oddzielne liczby błędów z TEGO SAMEGO walidatora.",
        "Liczba błędów przy pustym szablonie: **" +
        str(before["missing_evidence_occurrences"]) + "**.",
        "Liczba błędów przy faktycznie przygotowanym, ale niepodpisanym szkicu: **" +
        str(after["missing_evidence_occurrences"]) + "**.",
        "Zmiana netto: **" + str(report["net_reduction_in_formal_errors"]) + "**.",
        "Wiersze meczów w szkicu do sprawdzenia: **" +
        str(after["fixture_rows_ready_for_human_inspection"]) + "**.",
        "Zatwierdzone karty: **0/" +
        str(report["competition_day_cells"]) + "**. Zatwierdzone dni: **0/" +
        str(len(report["days"])) + "**.",
        "", "## Co udało się usunąć z listy blokad pustego szablonu?",
        "",
    ]
    for name, count in sorted(report["actual_blockers_resolved_vs_template"].items(),
                              key=lambda kv: (-kv[1], kv[0])):
        out.append(f"- {count} × {name}")
    if not report["actual_blockers_resolved_vs_template"]:
        out.append("- Brak zmniejszenia błędów; sprawdzić parsowanie źródeł.")
    out += ["", "## Jakie problemy ujawniły się po dodaniu rzeczywistych danych?",
            ""]
    for name, count in sorted(report["new_or_more_visible_blockers"].items(),
                              key=lambda kv: (-kv[1], kv[0])):
        out.append(f"- {count} × {name}")
    if not report["new_or_more_visible_blockers"]:
        out.append("- Brak dodatkowych konfliktów tego typu.")
    out += ["", "## Nadal blokowane źródła i decyzje",
            "", "| Dzień | Liga | Pary w szkicu | Dowód automatyczny | Formalne braki |",
            "|---|---|---:|---|---:|"]
    for row in report["rows"]:
        evidence = row["machine_source_scope"] or "BRAK"
        out.append(f"| {row['day']} | {row['league_id']} | "
                   f"{row['prefilled_fixture_rows']} | {evidence} | "
                   f"{len(row['prepared_errors'])} |")
    out += ["", "**NIE ZATWIERDZAĆ RETROSPEKTYWNIE.** "
            "Daty, nazwa recenzenta, pełny termin organizatora i "
            "potwierdzenie dni bez gier muszą być prawdziwe. "
            "Czas pobrania przez program to dowód pomocniczy, "
            "nie podpis niezależnego recenzenta. "
            "Calendar Gate pozostaje BLOCKED.", ""]
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("template")
    p.add_argument("prepared_draft")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    report = analyze(*[
        json.loads(Path(name).read_text(encoding="utf-8"))
        for name in (args.queue, args.template, args.prepared_draft)
    ])
    for filename, value in (
        (args.output_json, json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
        (args.output_md, render(report))):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    print("KB21 honest prepared evidence progress:",
          {"empty_template": report["baseline"]["missing_evidence_occurrences"],
           "prepared_unsigned": report["prepared"]["missing_evidence_occurrences"],
           "fixture_rows": report["prepared"]["fixture_rows_ready_for_human_inspection"],
           "human_approvals": 0}, "NO PLAY")


if __name__ == "__main__":
    main()
