"""Unsiged KB21 organizer review packet: per-league/day blockers, fixtures and time windows.

A configured adapter is not a signed complete calendar. This packet does NOT
authorize PLAY, verify no-match days, score games, or modify historical N.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from tools.kb21_calendar_evidence_dashboard import COMPETITIONS
from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_match_triage import collect as collect_match_comparisons

ROLES = {
    "FULL_SEASON_FPL": "FULL_SEASON_SNAPSHOT_NOT_ATTESTATION",
    "UEFA_ARTICLE_DATE_TEAMS_ONLY": "DATE_TEAM_ONLY_NO_KICKOFF_PROOF",
    "BELGIAN_SELECTED_ROUND_UNDATED": "UNDATED_ROUND_ONLY",
    "HISTORICAL_2026_WC_CYCLE_CONTEXT": "HISTORICAL_CYCLE_NOT_A_DAY_CALENDAR",
    "NO_DIRECT_MACHINE_ADAPTER": "NO_DIRECT_SOURCE",
}


def build(queue, gate, dashboard, now=None, partial_draft=None, comparisons=None,
          early_archive=None, early_revisions=None, zero_evidence=None):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)
            or not isinstance(gate, dict) or not isinstance(gate.get("days"), dict)
            or not isinstance(dashboard, dict) or not isinstance(dashboard.get("rows"), list)):
        raise ValueError("Invalid Calendar Gate packet inputs")
    days = queue["days"]
    if (not 1 <= len(days) <= 3 or len(set(days)) != len(days)
            or set(gate["days"]) != set(days)
            or set(dashboard.get("days", [])) != set(days)
            or gate.get("calendar_gate") != dashboard.get("calendar_gate")):
        raise ValueError("Review packet calendar scope mismatch")
    if partial_draft is not None:
        if (not isinstance(partial_draft, dict)
                or not isinstance(partial_draft.get("days"), dict)
                or set(partial_draft["days"]) != set(days)
                or partial_draft.get("approval") is not None):
            raise ValueError("Partial source draft must remain unsigned and date-scoped")
        daily = partial_draft.get("daily_approvals") or {}
        if not isinstance(daily, dict) or any(v is not None for v in daily.values()):
            raise ValueError("Signed daily approval must never enter unsigned hints packet")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    expected = {(day, league) for day in days for league in COMPETITIONS}
    dashboard_rows = {}
    for row in dashboard["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid dashboard source row")
        key = row.get("day"), row.get("league_id")
        if key not in expected or key in dashboard_rows:
            raise ValueError("Unexpected or duplicate source day/league")
        dashboard_rows[key] = row
    if set(dashboard_rows) != expected:
        raise ValueError("All fourteen competitions required for every date")
    official_errors = {}
    for day in days:
        value = gate["days"][day]
        if not isinstance(value, dict) or not isinstance(value.get("competitions"), list):
            raise ValueError("Missing validated organizer competition checks")
        for row in value["competitions"]:
            if not isinstance(row, dict) or not isinstance(row.get("errors"), list):
                raise ValueError("Invalid organizer blocker list")
            key = day, row.get("league_id")
            if key not in expected or key in official_errors:
                raise ValueError("Unrecognized or duplicate formal blocker scope")
            if not all(isinstance(e, str) and e for e in row["errors"]):
                raise ValueError("Malformed formal blocker")
            official_errors[key] = sorted(set(row["errors"]))
    if set(official_errors) != expected:
        raise ValueError("Missing formal competition/day errors")
    fixtures = {key: [] for key in expected}
    seen = set()
    for item in queue["fixtures"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid independent candidate")
        fixture_id = item.get("fixture_id")
        if not isinstance(fixture_id, str) or ":" not in fixture_id or fixture_id in seen:
            raise ValueError("Invalid or duplicated candidate ID")
        seen.add(fixture_id)
        key = item.get("date_warsaw"), fixture_id.rsplit(":", 1)[0]
        if key not in expected:
            raise ValueError("Candidate outside official calendar scope")
        kickoff = _instant(item.get("kickoff"))
        fixtures[key].append({
            "fixture_id": fixture_id,
            "fixture": item.get("fixture") if isinstance(item.get("fixture"), str) else None,
            "kickoff_source": item.get("kickoff"),
            "kickoff_utc": kickoff.astimezone(timezone.utc).isoformat() if kickoff else None,
            "organizer_confirmed": False,
        })
    # The actual signoff validator requires whole-day approval BEFORE the
    # earliest independent fixture across ALL fourteen competitions, not
    # before each league's own first kickoff.
    day_windows = {}
    for day in days:
        all_candidates = [c for (fixture_day, _), group in fixtures.items()
                          if fixture_day == day for c in group]
        all_starts = [_instant(c["kickoff_source"]) for c in all_candidates]
        known = [x for x in all_starts if x is not None]
        earliest = min(known) if known else None
        if earliest is not None and earliest <= now:
            status = "DAY_FIRST_KICKOFF_ALREADY_PASSED"
        elif len(known) != len(all_starts):
            status = "DAY_KICKOFF_UNKNOWN_SIGNOFF_WINDOW_UNVERIFIABLE"
        elif earliest is not None:
            status = "DAY_FIRST_KICKOFF_FUTURE_MANUAL_REVIEW_REQUIRED"
        else:
            status = "NO_CANDIDATES_NO_ZERO_GAME_PROOF"
        day_windows[day] = {
            "earliest_candidate_kickoff_utc":
                earliest.astimezone(timezone.utc).isoformat() if earliest else None,
            "prematch_signoff_status": status,
            "independent_candidate_count": len(all_candidates),
        }
    if comparisons is not None:
        if not isinstance(comparisons, dict):
            raise ValueError("Invalid per-fixture organizer comparison map")
        actual = {(day, c["fixture_id"])
                  for (day, _), group in fixtures.items() for c in group}
        if set(comparisons) != actual:
            raise ValueError("Organizer match comparisons must cover every fixture")
        if any(not isinstance(v, dict)
               or v.get("kickoff_evidence_validated_by_signoff") is not False
               for v in comparisons.values()):
            raise ValueError("Comparisons must remain diagnostic")
    # The early organizer-vault comparison is a separate provenance claim,
    # never a signature or a substitute for official full-day inspection.
    early_by_key = {}
    if early_archive is not None:
        if (not isinstance(early_archive, dict)
                or early_archive.get("schema")
                != "kb21-earliest-kickoff-early-official-crosscheck-v1"
                or early_archive.get("calendar_gate") != "BLOCKED"
                or set(early_archive.get("days", [])) != set(days)
                or not isinstance(early_archive.get("matches"), list)):
            raise ValueError("Invalid early archive diagnostic report")
        valid_ids = {(day, item["fixture_id"]) for (day, _), vals in fixtures.items()
                     for item in vals}
        for record in early_archive["matches"]:
            if not isinstance(record, dict):
                raise ValueError("Invalid early archive row")
            key = record.get("day"), record.get("fixture_id")
            if key not in valid_ids or key in early_by_key:
                raise ValueError("Duplicate or unrecognized early archive fixture")
            if (record.get("calendar_gate") != "BLOCKED"
                    or record.get("prematch_clock_review_only") is not True):
                raise ValueError("Early archive cannot approve a match")
            if record.get("status") == "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW":
                earliest = _instant(day_windows[key[0]]["earliest_candidate_kickoff_utc"])
                captured = _instant(record.get("capture_at_utc"))
                if earliest is None or captured is None or captured >= earliest:
                    raise ValueError("Early match claim missing valid pre-day capture")
            early_by_key[key] = record
    # Revision comparison covers selected organizer feeds, never
    # an attested full day. Protect against missing league/date cells, forged
    # signoffs, duplicate rows or claims of pre-kickoff captures after the
    # independent earliest start across every competition.
    revision_by_key = {}
    if early_revisions is not None:
        from tools.kb21_early_snapshot_revisions import SCHEMA as REVISION_SCHEMA
        if (not isinstance(early_revisions, dict)
                or early_revisions.get("schema") != REVISION_SCHEMA
                or early_revisions.get("calendar_gate") != "BLOCKED"
                or early_revisions.get("safe_to_publish_play") is not False
                or set(early_revisions.get("days", [])) != set(days)
                or not isinstance(early_revisions.get("rows"), list)):
            raise ValueError("Invalid/approved organizer revision report")
        for event in early_revisions["rows"]:
            if not isinstance(event, dict):
                raise ValueError("Invalid organizer revision row")
            key = event.get("day"), event.get("league_id")
            if (key[0] not in days or key[1] not in ("eng.1", "ned.1", "ger.1", "esp.1")
                    or key in revision_by_key):
                raise ValueError("Unrecognized or duplicate official revision date/league")
            if (event.get("calendar_gate") != "BLOCKED"
                    or event.get("full_organizer_day_attested") is not False
                    or event.get("human_signed") is not False):
                raise ValueError("Official revision report cannot grant approval")
            deadline = _instant(day_windows[key[0]]["earliest_candidate_kickoff_utc"])
            captured = _instant(event.get("last_capture_utc"))
            if captured is not None and (deadline is None or captured >= deadline):
                raise ValueError("Prematch official revision source captured after first game")
            revision_by_key[key] = event
        if set(revision_by_key) != {(day, league)
                                   for day in days for league in ("eng.1", "ned.1", "ger.1", "esp.1")}:
            raise ValueError("Official revision audit missing competition/day rows")
    # Exact zero-day worklist from the SAME unsigned inventory/signoff
    # validator. Never interpret a complete FPL 380-match catalogue as
    # a manual confirmation of a blank organizer day.
    zero_by_key = {}
    if zero_evidence is not None:
        from tools.kb21_zero_day_evidence import SCHEMA as ZERO_SCHEMA
        if (not isinstance(zero_evidence, dict)
                or zero_evidence.get("schema") != ZERO_SCHEMA
                or zero_evidence.get("calendar_gate") != "BLOCKED"
                or zero_evidence.get("safe_to_publish_play") is not False
                or set(zero_evidence.get("days", [])) != set(days)
                or not isinstance(zero_evidence.get("rows"), list)):
            raise ValueError("Invalid zero-day worklist")
        seen_zero_keys = set()
        for item in zero_evidence["rows"]:
            if not isinstance(item, dict):
                raise ValueError("Malformed zero-day worklist item")
            key = item.get("day"), item.get("league_id")
            if key not in expected or key in seen_zero_keys:
                raise ValueError("Unrecognized/duplicate zero-day worklist entry")
            seen_zero_keys.add(key)
            if (item.get("calendar_gate") != "BLOCKED"
                    or item.get("human_reviewer") is not None
                    or item.get("confirmed_zero_matches") is not None
                    or item.get("full_day_checked") is not False):
                raise ValueError("Zero-day worklist cannot sign a day")
            if item.get("machine_zero_candidate_needs_human_review"):
                deadline = _instant(day_windows[key[0]]["earliest_candidate_kickoff_utc"])
                capture = _instant(item.get("automated_source_capture_utc"))
                if (key[1] != "eng.1" or deadline is None
                        or capture is None or capture >= deadline
                        or now >= deadline):
                    raise ValueError("False full-season pre-day evidence claim")
            # Previous unsigned draft may still contain a zero blocker on
            # a day now genuinely signed by a human. Retain full evidence
            # checks above, but discard the stale unsigned blocker ONLY if
            # the strict current gate explicitly validated that whole day.
            # Keep blockers for other dates in the same rolling window.
            if gate["days"][key[0]].get("calendar_gate") != "PASS_MANUAL":
                zero_by_key[key] = item
        expected_zeros = {
            key for key, errs in official_errors.items()
            if "ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER" in errs
        }
        if set(zero_by_key) != expected_zeros:
            raise ValueError("Zero-day worklist must cover each formal zero blocker")
    rows, blockers = [], Counter()
    for day in days:
        for league in COMPETITIONS:
            key = day, league
            source = dashboard_rows[key]
            url = source.get("organizer_review_url")
            if url and (urlsplit(url).scheme != "https" or not urlsplit(url).hostname):
                raise ValueError("Invalid organizer entry URL")
            candidates = fixtures[key]
            count = source.get("espn_candidates")
            matched = source.get("paired_for_review")
            if (count != len(candidates) or not isinstance(matched, int)
                    or isinstance(matched, bool) or not 0 <= matched <= count):
                raise ValueError("Inconsistent source review/candidate counts")
            official = official_errors[key]
            blockers.update(official)
            hints = None
            if partial_draft is not None:
                day_slots = partial_draft["days"][day]
                if not isinstance(day_slots, dict) or league not in day_slots:
                    raise ValueError("Partial source draft omitted competition/day")
                review_slot = day_slots[league]
                if not isinstance(review_slot, dict):
                    raise ValueError("Invalid partial organizer slot")
                if (review_slot.get("reviewer")
                        or review_slot.get("captured_at")
                        or review_slot.get("full_day_checked") is True
                        or review_slot.get("confirmed_zero_matches") is True):
                    raise ValueError("Partial evidence cannot replace already signed source")
                hints = review_slot.get("partial_official_source_hints")
                if hints is not None and (not isinstance(hints, dict)
                                           or hints.get("organizer_full_day_attested") is not False
                                           or hints.get("date_and_kickoff_authenticated") is not False
                                           or not isinstance(hints.get("fixture_hints"), list)):
                    raise ValueError("Unsafe partial-source hint evidence")
            times = [_instant(c.get("kickoff_source")) for c in candidates]
            known = [x for x in times if x is not None]
            first = min(known) if known else None
            if candidates and len(known) != len(candidates):
                time_status = "MISSING_KICKOFF_NO_PREMATCH_PROOF"
            elif first and first <= now:
                time_status = "FIRST_KICKOFF_PASSED_NO_RETROACTIVE_APPROVAL"
            elif first:
                time_status = "FUTURE_FIRST_KICKOFF_MANUAL_REVIEW_REQUIRED"
            else:
                time_status = "ZERO_CANDIDATES_NOT_CONFIRMED_ZERO_DAY"
            source_status = source.get("evidence_status")
            if candidates and (matched != count or source_status in (
                    "SOURCE_ISSUES_REQUIRING_REVIEW",
                    "DIRECT_SOURCE_MISSING",
                    "MISSING_OR_CONFLICTING_CANDIDATES",
                    "ORGANIZER_ONLY_FIXTURES")):
                priority = 1
            elif candidates:
                priority = 2
            else:
                priority = 3
            for candidate in candidates:
                if comparisons is not None:
                    candidate["organizer_crosscheck"] = dict(
                        comparisons[(day, candidate["fixture_id"])])
                if (day, candidate["fixture_id"]) in early_by_key:
                    candidate["early_official_archive"] = dict(
                        early_by_key[(day, candidate["fixture_id"])])
            rows.append({
                "day": day, "league_id": league, "competition": COMPETITIONS[league],
                "priority": priority, "organizer_url": url,
                "source_file": source.get("adapter_source"),
                "comparison_file": source.get("adapter_comparison"),
                "source_role": ROLES.get(source.get("direct_evidence_scope"),
                                         "PARTIAL_DIAGNOSTIC_SOURCE"),
                "source_status": source_status,
                "fixtures": sorted(candidates,
                                   key=lambda c: (c["kickoff_utc"] or "9999", c["fixture_id"])),
                "independent_candidates": count, "paired_only_for_review": matched,
                "first_candidate_kickoff_utc": first.astimezone(timezone.utc).isoformat()
                if first else None,
                "time_status": time_status,
                "day_wide_review_deadline": day_windows[day],
                "formal_errors": official,
                "source_errors": source.get("source_errors", []),
                "partial_official_source_hints": hints,
                "early_organizer_revision": revision_by_key.get(key),
                "zero_day_proof_worklist": zero_by_key.get(key),
                "full_day_approved_by_this_packet": False,
                "reviewer": None, "manual_review_required": True,
                "calendar_gate": "BLOCKED",
            })
    rows.sort(key=lambda x: (x["day"], x["priority"],
                              -x["independent_candidates"], x["league_id"]))
    return {
        "schema": "kb21-calendar-review-packet-v1",
        "days": days, "generated_at_utc": now.isoformat(), "rows": rows,
        "day_review_deadlines": day_windows,
        "totals": {
            "league_day_reviews": len(rows),
            "adapters_configured": dashboard.get("totals", {}).get("direct_adapters"),
            "fixtures_to_review": len(queue["fixtures"]),
            "diagnostic_pairs_only": sum(x["paired_only_for_review"] for x in rows),
            "partial_hint_league_days": sum(
                x["partial_official_source_hints"] is not None for x in rows),
            "source_day_signoffs_from_packet": 0,
            "zero_day_review_cells": len(zero_by_key),
            "zero_day_full_season_fpl_precheck_only": sum(
                item["machine_zero_candidate_needs_human_review"]
                for item in zero_by_key.values()),
            "early_official_archive_matches": sum(
                item.get("early_official_archive", {}).get("status")
                == "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
                for row in rows for item in row["fixtures"]),
            "early_organizer_day_revisions_to_review": sum(
                row.get("early_organizer_revision", {}).get("status")
                == "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW"
                for row in rows if row.get("early_organizer_revision") is not None),
            "formal_blocker_occurrences": sum(blockers.values()),
            "formal_blocker_types": dict(sorted(blockers.items())),
            "day_league_checks_after_first_kickoff": sum(
                x["time_status"] == "FIRST_KICKOFF_PASSED_NO_RETROACTIVE_APPROVAL"
                for x in rows),
            "whole_days_after_first_candidate_kickoff": sum(
                w["prematch_signoff_status"] == "DAY_FIRST_KICKOFF_ALREADY_PASSED"
                for w in day_windows.values()),
            "knvb_post_start_result_date_pairs": sum(
                1 for row in rows for c in row["fixtures"]
                if c.get("organizer_crosscheck", {}).get("organizer_comparator_status")
                == "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF"
            ),
            "candidate_comparisons_with_source_conflicts": sum(
                1 for row in rows for c in row["fixtures"]
                if c.get("organizer_crosscheck", {}).get("organizer_comparator_status")
                not in (None, "MATCHED_FOR_REVIEW",
                        "COMPARATOR_NOT_AVAILABLE", "NO_COMPARATOR_RECORD",
                        "DATE_TEAMS_ONLY_KICKOFF_UNVERIFIED",
                        "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF")
            ),
        },
        "publication": "DIAGNOSTIC / NO PLAY",
        "safe_to_publish_play": False,
        "calendar_gate": "BLOCKED",
        "note": ("Unsigned diagnostic aid. Pair agreement is not organizer "
                 "authentication. An empty source is not verified zero. "
                 "The reviewer must independently inspect full dated official "
                 "schedules before first kickoff and sign using the existing "
                 "Calendar Gate protocol."),
    }


def render(packet):
    total = packet["totals"]
    lines = [
        "# KB Score 2.1 — szczegółowa karta kontroli terminarzy",
        "", "**NIE PLAY — BRAK AUTOMATYCZNEGO PODPISU**", "",
        "Stan UTC: " + packet["generated_at_utc"],
        "Adaptery: " + str(total["adapters_configured"]) + "/14 (nie oznacza pełnej weryfikacji)",
        "Pozycji organizator/dzień: " + str(total["league_day_reviews"]),
        "Kandydaci ESPN: " + str(total["fixtures_to_review"]) +
        "; porównania diagnostyczne: " + str(total["diagnostic_pairs_only"]),
        "Błędy formalne na poziomie rozgrywek: " + str(total["formal_blocker_occurrences"]),
        "Brakujące kontrole dnia bez spotkań: " + str(total["zero_day_review_cells"]) +
        "; z pełnym katalogiem FPL do ręcznego przeglądu: " +
        str(total["zero_day_full_season_fpl_precheck_only"]),
        "Źródła ze wskazówkami bez zatwierdzonych godzin: " +
        str(total["partial_hint_league_days"]) + " kart rozgrywki/dzień",
        "Wczesne archiwum: zgodne pary do kontroli (NIE zatwierdzone): " +
        str(total["early_official_archive_matches"]),
        "Zmiany oficjalnych terminarzy między porannymi odczytami: " +
        str(total["early_organizer_day_revisions_to_review"]),
        "Przekroczony początek pierwszego meczu (liga/dzień): " +
        str(total["day_league_checks_after_first_kickoff"]),
        "Dni z upływem pierwszego startu ESPN: " +
        str(total["whole_days_after_first_candidate_kickoff"]),
        "Szczegółowe różnice od organizatorów (bez automatycznego rozstrzygnięcia): " +
        str(total["candidate_comparisons_with_source_conflicts"]),
        "KNVB: mecze z podstrony wyników już po starcie (bez potwierdzenia "
        "przedmeczowej godziny): " + str(total["knvb_post_start_result_date_pairs"]),
        "", "## Najczęstsze błędy formalne", "",
    ]
    for code, count in sorted(total["formal_blocker_types"].items(),
                              key=lambda p: (-p[1], p[0]))[:12]:
        lines.append("- " + str(count) + " × " + code)
    for day in packet["days"]:
        lines += ["", "## " + day, "",
                  "| P | Liga | ESPN | Porównane | Zakres dowodu | Okno czasowe |",
                  "|---|---|---:|---:|---|---|"]
        daily = [row for row in packet["rows"] if row["day"] == day]
        deadline = packet["day_review_deadlines"][day]
        lines.append("**TERMIN DLA CAŁEGO DNIA (WSZYSTKIE LIGI):** " +
                     deadline["prematch_signoff_status"] +
                     "; najwcześniejszy kandydat ESPN UTC: " +
                     str(deadline["earliest_candidate_kickoff_utc"] or "nieznany") +
                     ". Pary z oficjalnych źródeł nie zastępują pełnej kontroli.")
        lines.append("")
        for row in daily:
            lines.append("| P" + str(row["priority"]) + " | " + row["competition"]
                         + " | " + str(row["independent_candidates"])
                         + " | " + str(row["paired_only_for_review"])
                         + " | " + row["source_role"]
                         + " | " + row["time_status"] + " |")
        lines += ["", "### Zadania z konkretnymi dowodami", ""]
        for row in daily:
            url = ("[oficjalny kalendarz](" + row["organizer_url"] + ")"
                   if row["organizer_url"] else "BRAK URL")
            lines.append("#### P" + str(row["priority"]) + " " +
                         row["competition"] + " — " + url)
            lines.append("Źródło: " + str(row["source_status"]) + " / " +
                         row["source_role"] + "; pierwszy start ESPN: " +
                         str(row["first_candidate_kickoff_utc"] or "nieznany") +
                         "; " + row["time_status"])
            zero = row.get("zero_day_proof_worklist")
            if zero is not None:
                lines.append("NIEPOTWIERDZONY DZIEŃ BEZ SPOTKAŃ: " +
                             str(zero["status"]) +
                             "; zadanie: " + str(zero["action"]) +
                             "; czas oficjalnego odczytu UTC: " +
                             str(zero.get("automated_source_capture_utc") or "brak") +
                             ". Nie jest to podpis, zero cert ani PLAY.")
            partial = row["partial_official_source_hints"]
            if partial is not None:
                lines.append("POMOCNICZY DOWÓD ORGANIZATORA (niezatwierdzony): " +
                             str(partial["kind"]) + " / " +
                             str(partial.get("source_status")) +
                             " / pobrano UTC " + str(partial.get("captured_at_utc")))
                if partial["fixture_hints"]:
                    for hint in partial["fixture_hints"]:
                        lines.append("- WSKAZÓWKA (bez potwierdzonej daty/godziny): " +
                                     json.dumps(hint, ensure_ascii=False))
                else:
                    lines.append("- Brak par w częściowym źródle NIE POTWIERDZA zera meczów.")
            for event in row["fixtures"]:
                lines.append("- ESPN " + event["fixture_id"] + " "
                             + str(event["fixture"]) + " / " +
                             str(event["kickoff_source"]) +
                             " (niezatwierdzony czas organizatora)")
                archive = event.get("early_official_archive")
                if archive:
                    lines.append("  - Archiwum oficjalne przed dniem meczu: " +
                                 str(archive["status"]) + "; pobrano UTC: " +
                                 str(archive.get("capture_at_utc") or "brak") +
                                 "; godzina źródła: " +
                                 str(archive.get("official_kickoff_from_early_capture")
                                     or "brak") +
                                 " — wyłącznie diagnostyka, NIE PLAY")
                cross = event.get("organizer_crosscheck")
                if cross:
                    lines.append("  - Porównanie organizatora: **" +
                                 str(cross["organizer_comparator_status"]) +
                                 "**; godzina w źródle: " +
                                 str(cross.get("official_kickoff_claim") or "brak") +
                                 "; plik: " + str(cross.get("comparison_file")) +
                                 " — WYMAGA POTWIERDZENIA, NIE PLAY")
            revision = row.get("early_organizer_revision")
            if revision is not None:
                lines.append("- ARCHIWALNE PORÓWNANIE DWÓCH ODCZYTÓW: " +
                             str(revision["status"]) +
                             "; dostępnych bezpiecznych odczytów: " +
                             str(revision["eligible_snapshot_count"]) +
                             "; pierwszy: " + str(revision.get("first_capture_utc")) +
                             "; ostatni: " + str(revision.get("last_capture_utc")))
                if revision["status"] == "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW":
                    lines.append("  - WYMAGA SPRAWDZENIA ZMIAN: " +
                                 json.dumps({
                                     "added": revision["added_pairs"],
                                     "removed": revision["removed_pairs"],
                                     "changed_kickoff": revision["kickoff_changes"],
                                 }, ensure_ascii=False))
            for error in row["formal_errors"]:
                lines.append("- BLOKADA: " + error)
            for error in row["source_errors"][:4]:
                lines.append("- PROBLEM POBRANIA: " + str(error))
            if not row["fixtures"]:
                lines.append("- Brak kandydatów nie oznacza oficjalnie pustego dnia.")
            lines.append("")
    lines += ["", "Przed zatwierdzeniem: pełna, aktualna karta organizatora, "
              "godziny i strefa czasowa, niezależne porównanie oraz osobista "
              "weryfikacja przed pierwszym meczem. "
              "Ten raport nigdy nie zatwierdza PLAY ani historycznego N.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("gate")
    p.add_argument("dashboard")
    p.add_argument("--partial-draft")
    p.add_argument("--comparisons-dir")
    p.add_argument("--early-archive-compare")
    p.add_argument("--early-archive-revisions")
    p.add_argument("--zero-evidence-worklist")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    a = p.parse_args()
    obj = build(
        json.loads(Path(a.queue).read_text(encoding="utf-8")),
        json.loads(Path(a.gate).read_text(encoding="utf-8")),
        json.loads(Path(a.dashboard).read_text(encoding="utf-8")),
        partial_draft=json.loads(Path(a.partial_draft).read_text(encoding="utf-8"))
        if a.partial_draft else None,
        comparisons=collect_match_comparisons(
            json.loads(Path(a.queue).read_text(encoding="utf-8")), a.comparisons_dir)
        if a.comparisons_dir else None,
        early_archive=json.loads(Path(a.early_archive_compare).read_text(encoding="utf-8"))
        if a.early_archive_compare else None,
        early_revisions=json.loads(Path(a.early_archive_revisions).read_text(encoding="utf-8"))
        if a.early_archive_revisions else None,
        zero_evidence=json.loads(Path(a.zero_evidence_worklist).read_text(encoding="utf-8"))
        if a.zero_evidence_worklist else None,
    )
    for filename, value in (
        (a.output_json, json.dumps(obj, ensure_ascii=False, indent=2) + "\n"),
        (a.output_md, render(obj))):
        dest = Path(filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding="utf-8")
    print("KB21 calendar review packet:", obj["totals"], "NO PLAY")


if __name__ == "__main__":
    main()
