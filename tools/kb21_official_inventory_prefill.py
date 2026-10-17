"""Prefill unsigned original KB21 official inventory, never sign it.

The prefilled fixture list is RESEARCH, not authenticated organizer capture or
independent signed official verification. A human must recheck EACH competition,
document capture time, official source, and attest full-card coverage. An
official partial club-page never certifies all Portuguese fixtures.
"""
import argparse
import copy
import json
from pathlib import Path


def prefill(template, research):
    if not isinstance(template, dict) or not isinstance(template.get("days"), dict):
        raise ValueError("Expected unsigned official calendar inventory template")
    if template.get("approval") is not None:
        raise ValueError("Refuse to modify previously signed calendar inventory")
    if not isinstance(research, dict) or research.get("schema") != "kb21-official-research-v1":
        raise ValueError("Expected organizer-source research file")
    if (research.get("status") != "OFFICIAL_WEB_RESEARCH_UNSIGNED"
            or set(template["days"]) != set(research.get("date_scope", []))
            or set(template["days"]) != set(research.get("days", {}))):
        raise ValueError("Research date window stale or unexpectedly signed")
    result = copy.deepcopy(template)
    count = 0
    for day, leagues in result["days"].items():
        for league, slot in leagues.items():
            if slot.get("reviewer") or slot.get("captured_at") or slot.get("full_day_checked"):
                raise ValueError("Template already contains claimed human review")
            facts = research["days"][day].get(league)
            if facts is None:
                continue
            fixtures = facts.get("fixtures")
            if not isinstance(fixtures, list):
                raise ValueError("Invalid research fixture list")
            slot["fixtures"] = copy.deepcopy(fixtures)
            slot["research_source_url"] = facts.get("official_source_url")
            slot["research_source_kind"] = facts.get("source_kind")
            slot["research_full_round_source_found"] = facts.get("full_round_source_found") is True
            slot["research_official_fixture_list_extracted"] = facts.get("official_fixture_list_extracted") is True
            slot["research_note"] = facts.get("note", "")
            slot["needs_current_organizer_verification"] = True
            slot["captured_at"] = None
            slot["reviewer"] = None
            slot["full_day_checked"] = False
            slot["confirmed_zero_matches"] = None
            count += len(fixtures)
    result["schema"] = "kb21-manual-inventory-prefilled-research-v1"
    result["approval"] = None
    result["research_fixtures_prefilled"] = count
    result["calendar_gate"] = "BLOCKED"
    result["publication"] = "DIAGNOSTIC / NO PLAY"
    result["note"] = (
        "Prefilled unofficial research makes manual review easier but supplies "
        "NO official capture timestamps, full-scope verification, human reviewer or "
        "signature. Do not mark the league/day verified until organizer fixtures "
        "are independently rechecked, especially the Portuguese partial source. "
        "Historic days MUST NOT be signed off retrospectively."
    )
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inventory_template")
    p.add_argument("official_research")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    draft = prefill(
        json.loads(Path(args.inventory_template).read_text(encoding="utf-8")),
        json.loads(Path(args.official_research).read_text(encoding="utf-8")),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"KB21 official audit draft: {draft['research_fixtures_prefilled']} prefilled fixtures; "
          f"0 automatically verified; Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
