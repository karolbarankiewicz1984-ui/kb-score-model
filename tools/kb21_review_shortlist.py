"""Create a ten-fixture *research* shortlist for manual KB Score 2.1 validation.

Ranks ONLY by evidence availability, never market attractiveness. The shortlist
is a bounded analyst calibration exercise, NOT a production PLAY limit.
Past/started fixtures are excluded at generation time to prevent post-start
backfilling. Historical N and LIVE scoring are untouched.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant


def choose(queue, now=None, limit=10):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue with fixtures list")
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("limit must be in 1..100")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    eligible, dropped = [], {"started_or_past": 0, "invalid_kickoff": 0}
    seen = set()
    for fixture in queue["fixtures"]:
        kickoff = _instant(fixture.get("kickoff"))
        if kickoff is None:
            dropped["invalid_kickoff"] += 1
            continue
        if kickoff <= now:
            dropped["started_or_past"] += 1
            continue
        key = fixture.get("fixture_id")
        if not key or key in seen:
            continue
        seen.add(key)
        research = fixture.get("pre_match_research") or {}
        context = research.get("context") or {}
        independent = fixture.get("independent_crosscheck") or {}
        both_sides = bool(context.get("home") and context.get("away"))
        any_history = bool(context.get("home") or context.get("away"))
        crossmatch = independent.get("status") == "MATCHED_FOR_REVIEW"
        # This score is ONLY a workflow ordering key (data completeness);
        # NEVER a sporting prediction, Sport Score, confidence or P(model).
        priority = (2 if crossmatch else 0) + (2 if both_sides else 1 if any_history else 0)
        eligible.append({
            "fixture_id": key, "fixture": fixture.get("fixture"),
            "competition": fixture.get("competition"),
            "kickoff": fixture.get("kickoff"),
            "date_warsaw": fixture.get("date_warsaw"),
            "evidence_priority_only": priority,
            "independent_source_status": independent.get("status"),
            "previous_goal_history_status": research.get("status"),
            "research_context": context or None,
            "assessment": fixture.get("assessment") or {},
            "official_calendar_verified": False,
            "calendar_gate": "BLOCKED",
            "publication": "DIAGNOSTIC / NO PLAY",
        })
    eligible.sort(key=lambda f: (-f["evidence_priority_only"], f["kickoff"], f["fixture_id"]))
    return {
        "status": "MANUAL_PREMATCH_RESEARCH_QUEUE",
        "calendar_gate": "BLOCKED",
        "publication": "DIAGNOSTIC / NO PLAY",
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "available_future_candidates": len(eligible),
        "excluded": dropped,
        "selection_limit_for_validation_only": limit,
        "fixtures": eligible[:limit],
        "note": (
            "Ordering reflects source completeness, NOT expected success. "
            "Human analyst must verify official FULL calendar and independently "
            "document STR/QUAL/MATCH, pre-market P(model), freeze and confidence. "
            "No LIVE publication or historical N writes.")
    }


def render(shortlist):
    out = ["# KB Score 2.1 — pierwsza kolejka ręcznej walidacji", "",
           "**Wyłącznie przyszłe mecze. DIAGNOSTYKA / NO PLAY. Calendar Gate BLOCKED.**", "",
           f"Wygenerowano: {shortlist['generated_at_utc']}",
           f"Przyszli kandydaci: {shortlist['available_future_candidates']}; "
           f"do przeglądu: {len(shortlist['fixtures'])}; "
           f"rozpoczęte/past: {shortlist['excluded']['started_or_past']}", "",
           "Kolejność wynika tylko z kompletności źródeł; NIE z jakości typu.", ""]
    for i, f in enumerate(shortlist["fixtures"], 1):
        out.extend([
            f"## {i}. {f['fixture']} — {f['kickoff']}",
            f"- Rozgrywki: {f['competition']} | ID: {f['fixture_id']}",
            f"- Zgodność pomocniczych kalendarzy: {f['independent_source_status'] or 'BRAK'}",
            f"- Historia meczów: {f['previous_goal_history_status'] or 'BRAK'}",
            "- Brakuje: oficjalny terminarz i kompletność karty; dowody siły, jakości, "
            "kontekstu; analityczne STR/QUAL/MATCH; pre-price P(model) oraz freeze.",
            "- Decyzja: BRAK — karta do oceny, nie rekomendacja.",
            "",
        ])
    if not shortlist["fixtures"]:
        out.extend(["Brak nierozpoczętych meczów z bieżącej listy. Nie rekonstruuj oceny wstecz.", ""])
    out += ["---", "Ta próbka 10 meczów służy testowi spójności metody, NIE ogranicza przyszłej liczby analiz.", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    source = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    chosen = choose(source, limit=args.limit)
    for path, body in [(Path(args.output_json), json.dumps(chosen, ensure_ascii=False, indent=2) + "\n"),
                       (Path(args.output_md), render(chosen))]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    print(f"{len(chosen['fixtures'])} KB21 prospective research cards, NO PLAY")


if __name__ == "__main__":
    main()
