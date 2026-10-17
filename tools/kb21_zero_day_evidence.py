"""Prioritize evidence for unresolved KB21 'ZERO_MATCHES' signoff blockers.

A full 380-fixture FPL season can be a strong candidate for independent
manual review of a zero-match day. It NEVER proves human attestation or
sets confirmed_zero_matches, reviewer, captured_at, full_day_checked, PLAY.
No other partial organizer feed is treated as zero proof.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from tools.kb21_calendar_coverage import SCOPE
from tools.kb21_calendar_signoff import validate
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_review import OFFICIAL_PAGES
from tools.kb21_official_gap_context import date_gap, PORTUGAL_SEASON_SCHEDULE
from tools.kb21_portugal_season_gap import season_break

SCHEMA = "kb21-zero-day-evidence-worklist-v1"


def _full_fpl(snapshot, days):
    if snapshot is None or not isinstance(snapshot, dict):
        return False
    if (snapshot.get("schema") != "kb21-official-premier-league-fpl-v1"
            or snapshot.get("league_id") != "eng.1"
            or snapshot.get("calendar_gate") != "BLOCKED"
            or snapshot.get("reviewer_signed") is not False
            or snapshot.get("full_calendar_verified") is not False
            or snapshot.get("season_full_380_catalogue") is not True
            or snapshot.get("season_fixture_count") != 380
            or snapshot.get("season_team_count") != 20
            or snapshot.get("fixtures_missing_kickoff_count") != 0
            or snapshot.get("invalid_or_provisional_fixture_ids") != []
            or set(snapshot.get("days", [])) != set(days)
            or not isinstance(snapshot.get("by_day"), dict)
            or set(snapshot["by_day"]) != set(days)
            or _instant(snapshot.get("captured_at_utc")) is None):
        return False
    return all(isinstance(rows, list) for rows in snapshot["by_day"].values())


def build(queue, draft, fpl=None, now=None, ligue1=None, knvb=None, portugal=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Zero evidence check needs timezone-aware current time")
    now = now.astimezone(timezone.utc)
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)
            or not isinstance(draft, dict) or not isinstance(draft.get("days"), dict)
            or draft.get("approval") is not None):
        raise ValueError("Expected unsigned queue and source-prepared inventory")
    days = queue["days"]
    if (not 1 <= len(days) <= 3 or len(set(days)) != len(days)
            or set(draft["days"]) != set(days)):
        raise ValueError("Scope mismatch")
    daily = draft.get("daily_approvals") or {}
    if (not isinstance(daily, dict)
            or any(record is not None for record in daily.values())):
        raise ValueError("Already signed daily review cannot be treated as unsigned")
    valid_fpl = _full_fpl(fpl, days)
    gate = validate(queue, draft)
    if (gate["calendar_gate"] != "BLOCKED"
            or gate.get("approved_days") != 0
            or gate.get("safe_to_publish_play") is not False):
        raise ValueError("Never classify signed calendars as pending zero work")
    rows = []
    all_kickoffs = {}
    for day in days:
        fixtures = [x for x in queue["fixtures"] if x.get("date_warsaw") == day]
        kicks = [_instant(x.get("kickoff")) for x in fixtures]
        all_kickoffs[day] = (min(kicks) if kicks and all(kicks) else None)
    for day in sorted(days):
        slots = draft["days"][day]
        if not isinstance(slots, dict) or set(slots) != set(SCOPE):
            raise ValueError("All 14 official competition slots required")
        formal = gate["days"][day]["competitions"]
        if len(formal) != len(SCOPE):
            raise ValueError("Incomplete organizer validation rows")
        lookup = {x["league_id"]: x for x in formal}
        if set(lookup) != set(SCOPE):
            raise ValueError("Missing official validation scope")
        for league in SCOPE:
            if "ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER" not in lookup[league]["errors"]:
                continue
            slot = slots[league]
            if (not isinstance(slot, dict) or slot.get("reviewer")
                    or slot.get("captured_at") is not None
                    or slot.get("full_day_checked") is True
                    or slot.get("confirmed_zero_matches") is True
                    or slot.get("fixtures") != []):
                raise ValueError("Unsigned zero-source slot was edited or signed")
            independent = [x for x in queue["fixtures"]
                           if x.get("date_warsaw") == day
                           and str(x.get("fixture_id", "")).startswith(league + ":")]
            deadline = all_kickoffs[day]
            status = "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE"
            action = "Check a complete official date-specific organizer calendar and sign before first kickoff"
            official_capture = None
            official_url = slot.get("organizer_facts_source") or OFFICIAL_PAGES.get(league)
            if independent:
                status = "ESPN_HAS_FIXTURES_BUT_ORGANIZER_INVENTORY_EMPTY"
                action = "Reconcile missing organizer fixture rows; NEVER claim a zero day"
            elif league == "eng.1" and valid_fpl:
                official_rows = fpl["by_day"][day]
                official_capture = fpl["captured_at_utc"]
                official_url = fpl.get("official_fixture_endpoint") or official_url
                if official_rows:
                    status = "OFFICIAL_FPL_LISTS_GAMES_ESPN_LISTS_ZERO"
                    action = "Investigate ESPN missing a scheduled match before signoff"
                elif deadline is None:
                    status = "FULL_SEASON_FPL_EMPTY_DAY_NO_KNOWN_EARLIEST_START"
                    action = "Verify organizer and independent schedule; no safe cutoff time"
                elif _instant(official_capture) >= deadline:
                    status = "FULL_SEASON_FPL_EMPTY_DAY_CAPTURE_TOO_LATE"
                    action = "Historical evidence only; do not sign retrospectively"
                elif now >= deadline:
                    status = "FULL_SEASON_FPL_EMPTY_DAY_HUMAN_SIGNOFF_DEADLINE_PASSED"
                    action = "Snapshot was early but the human did NOT sign before first kickoff; no retrospective approval"
                else:
                    status = "FULL_SEASON_FPL_ZERO_CANDIDATE_NEEDS_HUMAN_SIGNOFF"
                    action = ("Independently verify organizer 380-match catalogue and all updates "
                              "before earliest kickoff; document reviewer, actual capture and completeness")
            elif slot.get("organizer_source_catalogue_kind") or slot.get("partial_official_source_hints"):
                status = "PARTIAL_OR_UNDATED_SOURCE_CANNOT_CERTIFY_ZERO"
                action = "Verify full date-specific official schedule; selected rounds/articles are insufficient"
            gap = date_gap(league, day, (
                ligue1 if league == "fra.1"
                else knvb if league == "ned.1" else None), deadline)
            if gap is not None and not independent:
                status = "ADJACENT_OFFICIAL_MATCHDAYS_ONLY_NOT_ZERO_PROOF"
                action = ("Review the full live organizer day for postponements "
                          "or added league matches; adjacent published rounds "
                          "are helpful context, NOT a verified empty day")
            # Portugal's dated official season grid explicitly brackets the
            # 17/18 Oct league round break (J8 -> J9), but permits CPC changes.
            # An already-observed 19 Oct postponed league fixture demonstrates
            # exactly why a published round gap must NOT certify no games.
            portugal_context = (season_break(day, portugal)
                                if league == "por.1" else None)
            if portugal_context is not None and not independent:
                status = "PORTUGAL_ROUND_BREAK_CPC_CHANGES_UNCHECKED"
                action = portugal_context["manual_action"]
            supplement = (PORTUGAL_SEASON_SCHEDULE
                          if league == "por.1" and day == "2026-10-18"
                          else None)
            rows.append({
                "portugal_official_published_round_gap": portugal_context,
                "adjacent_official_matchday_dates": gap,
                "supplemental_organizer_calendar_for_manual_review": supplement,
                "day": day, "league_id": league, "competition": SCOPE[league],
                "status": status, "action": action,
                "independent_candidates": len(independent),
                "official_url_to_review": official_url,
                "automated_source_capture_utc": official_capture,
                "earliest_candidate_start_entire_day_utc":
                    deadline.astimezone(timezone.utc).isoformat() if deadline else None,
                "machine_zero_candidate_needs_human_review":
                    status == "FULL_SEASON_FPL_ZERO_CANDIDATE_NEEDS_HUMAN_SIGNOFF",
                "confirmed_zero_matches": None, "human_reviewer": None,
                "full_day_checked": False, "calendar_gate": "BLOCKED",
            })
    counts = Counter(row["status"] for row in rows)
    return {
        "schema": SCHEMA, "days": sorted(days),
        "calendar_gate": "BLOCKED", "safe_to_publish_play": False,
        "source_scope": "UNSIGNED_REAL_FIXTURE_DRAFT",
        "totals": {
            "zero_game_review_cells": len(rows),
            "full_season_fpl_zero_candidates": counts[
                "FULL_SEASON_FPL_ZERO_CANDIDATE_NEEDS_HUMAN_SIGNOFF"],
            "suspicious_independent_zero_cases": counts[
                "OFFICIAL_FPL_LISTS_GAMES_ESPN_LISTS_ZERO"],
            "adjacent_official_round_context_rows": sum(
                row["adjacent_official_matchday_dates"] is not None for row in rows),
            "portugal_published_round_break_context_rows": sum(
                row["portugal_official_published_round_gap"] is not None
                for row in rows),
            "never_human_signed": len(rows),
            "by_status": dict(sorted(counts.items())),
        },
        "rows": rows,
        "note": ("No unreviewed source certifies a zero-day automatically. "
                 "An empty sampled fixture list is not proof of zero games. "
                 "FPL requires independent reviewer and human documentation. "
                 "No retrospective approval, freeze, P(model), or PLAY."),
    }


def render(report):
    t = report["totals"]
    lines = [
        "# KB Score 2.1 — lista dowodów dla brakujących dni bez meczów",
        "", "**WYŁĄCZNIE DO RĘCZNEJ KONTROLI. ZERO PODPISÓW. NIE PLAY.**", "",
        "Niepotwierdzone puste terminarze: **" + str(t["zero_game_review_cells"]) + "**.",
        "Premier League: kompletny katalog 380 gier i przedmeczowy dowód "
        "braku zaplanowanego spotkania: **" +
        str(t["full_season_fpl_zero_candidates"]) + "**.",
        "Dni między opublikowanymi kolejkami organizatora (NIE dowód "
        "braku gier): **" + str(t["adjacent_official_round_context_rows"]) + "**.",
        "Portugalia: daty z oficjalnego planu sezonu, wymagają sprawdzenia "
        "przełożeń i poprawek CPC (NIE zero): **" +
        str(t["portugal_published_round_break_context_rows"]) + "**.",
        "", "## Najpilniejsze: brak dowodu pełnego terminarza", "",
    ]
    urgent = [row for row in report["rows"]
              if row["status"] == "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE"]
    for item in urgent:
        lines.append("- **" + item["day"] + " " + item["competition"] +
                     "** — " + item["official_url_to_review"] +
                     " — uzyskać pełny terminarz i potwierdzenie zerowej liczby gier.")
    lines += ["", "| Data | Rozgrywki | Poziom dowodu | Kandydaci ESPN | Oficjalny terminarz |",
        "|---|---|---|---:|---|",
    ]
    for row in report["rows"]:
        link = ("[strona](" + row["official_url_to_review"] + ")"
                if row["official_url_to_review"] else "BRAK")
        lines.append(f"| {row['day']} | {row['competition']} | {row['status']} | "
                     f"{row['independent_candidates']} | {link} |")
        lines.append("- Następny krok: " + row["action"] +
                     "; pierwszy mecz całego dnia UTC: " +
                     str(row["earliest_candidate_start_entire_day_utc"] or "nieznany") +
                     "; odczyt źródła UTC: " +
                     str(row["automated_source_capture_utc"] or "brak"))
        gap = row.get("adjacent_official_matchday_dates")
        if gap is not None:
            lines.append("  - Sąsiednie oficjalne terminy: " +
                         gap["previous_visible_date"] + " -> " +
                         gap["next_visible_date"] +
                         "; pobrano UTC " + gap["captured_at_utc"] +
                         "; źródło: " + gap["official_url"] +
                         "; przed pierwszym meczem całego dnia: " +
                         str(gap["snapshot_taken_before_first_whole_day_candidate"]) +
                         ". BRAK podpisu i BRAK dowodu zera spotkań.")
        portugal_gap = row.get("portugal_official_published_round_gap")
        if portugal_gap is not None:
            lines.append("  - Liga Portugal Betclic, oficjalne ramy: J8 (" +
                         portugal_gap["previous_scheduled_league_round"]
                         ["scheduled_weekend_reference"] + "), 3. runda "
                         "Pucharu (" +
                         str(portugal_gap["cup_round_on_reference_day"] or "18 października") +
                         "), J9 (" +
                         portugal_gap["next_scheduled_league_round"]
                         ["scheduled_weekend_reference"] +
                         "); pełny terminarz i zmiany CPC NIE zweryfikowane.")
            if portugal_gap["known_postponement_elsewhere_in_window"]:
                lines.append("  - Potwierdzony w klubowym źródle przykład "
                             "przełożonego spotkania ligowego 19 X: " +
                             str(portugal_gap["known_postponement_elsewhere_in_window"]))
        if row.get("supplemental_organizer_calendar_for_manual_review"):
            lines.append("  - Oficjalny kalendarz portugalskich rozgrywek "
                         "(w tym runda pucharowa; NIE wyklucza przełożonych "
                         "meczów ligowych): " +
                         row["supplemental_organizer_calendar_for_manual_review"])
    lines.append("")
    lines.append("WAŻNE: Do faktycznego zatwierdzenia recenzent musi "
                 "niezależnie sprawdzić kompletny dzienny terminarz przed pierwszym "
                 "meczem dnia. Nie wpisujemy automatycznie potwierdzenia zera, "
                 "nazwiska, daty kontroli ani zatwierdzenia.")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("draft")
    p.add_argument("--fpl")
    p.add_argument("--ligue1")
    p.add_argument("--knvb")
    p.add_argument("--portugal")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    q, draft = [
        json.loads(Path(filename).read_text(encoding="utf-8"))
        for filename in (a.queue, a.draft)
    ]
    fpl = json.loads(Path(a.fpl).read_text(encoding="utf-8")) if a.fpl else None
    ligue1 = json.loads(Path(a.ligue1).read_text(encoding="utf-8")) if a.ligue1 else None
    knvb = json.loads(Path(a.knvb).read_text(encoding="utf-8")) if a.knvb else None
    portugal = json.loads(Path(a.portugal).read_text(encoding="utf-8")) if a.portugal else None
    report = build(q, draft, fpl, ligue1=ligue1, knvb=knvb, portugal=portugal)
    for name, body in (
        (a.output_json, json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
        (a.output_md, render(report)),
    ):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    print("KB21 zero-day evidence triage:", report["totals"], "NO PLAY")
    print("KB21 urgent absent full-day sources:",
          [(r["day"], r["league_id"], r["official_url_to_review"])
           for r in report["rows"]
           if r["status"] == "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE"])


if __name__ == "__main__":
    main()
