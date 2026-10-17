"""Tests for unsigned 14-competition, day-by-day human review packet."""
import copy
from datetime import datetime, timezone
import unittest

from tools.kb21_calendar_review_packet import build, render
from tools.kb21_calendar_evidence_dashboard import COMPETITIONS

DAYS = ["2026-10-17", "2026-10-18"]


def data():
    fixtures = [
        {"date_warsaw": DAYS[0], "fixture_id": "eng.1:111",
         "fixture": "Arsenal - Chelsea", "kickoff": "2026-10-17T16:00:00+02:00"},
        {"date_warsaw": DAYS[1], "fixture_id": "bel.1:222",
         "fixture": "Gent - Antwerp", "kickoff": "2026-10-18T18:00:00+02:00"},
    ]
    queue = {"days": DAYS, "fixtures": fixtures}
    gate = {"days": {
        day: {"competitions": [{
            "league_id": code, "errors": [
                "MISSING_INDEPENDENT_REVIEWER", "OFFICIAL_DAY_NOT_VERIFIED_COMPLETE"
            ],
        } for code in COMPETITIONS], "calendar_gate": "BLOCKED", "errors": []}
        for day in DAYS}, "calendar_gate": "BLOCKED"}
    rows = []
    for day in DAYS:
        for code in COMPETITIONS:
            count = sum(f["date_warsaw"] == day and
                        f["fixture_id"].startswith(code + ":") for f in fixtures)
            rows.append({
                "day": day, "league_id": code, "espn_candidates": count,
                "paired_for_review": count if code == "eng.1" else 0,
                "direct_evidence_scope": "FULL_SEASON_FPL" if code == "eng.1"
                else "BELGIAN_SELECTED_ROUND_UNDATED" if code == "bel.1"
                else "UEFA_ARTICLE_DATE_TEAMS_ONLY",
                "evidence_status": "PAIRED_FIXTURES_FOR_REVIEW"
                if code == "eng.1" else "DIRECT_SOURCE_MISSING",
                "source_errors": [], "organizer_review_url": "https://example.org/league",
                "adapter_source": "official-league.json",
                "adapter_comparison": "official-vs-espn.json",
            })
    dashboard = {"days": DAYS, "rows": rows, "calendar_gate": "BLOCKED",
                 "totals": {"direct_adapters": 14}}
    return queue, gate, dashboard


class CalendarReviewPacketTests(unittest.TestCase):
    def test_42_to_28_rows_counts_and_safety(self):
        q, g, d = data()
        r = build(q, g, d, datetime(2026, 10, 17, 12, tzinfo=timezone.utc))
        self.assertEqual(r["totals"]["league_day_reviews"], 28)
        self.assertEqual(r["totals"]["formal_blocker_occurrences"], 56)
        self.assertEqual(r["totals"]["diagnostic_pairs_only"], 1)
        self.assertFalse(r["safe_to_publish_play"])
        self.assertEqual(r["calendar_gate"], "BLOCKED")
        self.assertTrue(all(row["manual_review_required"] for row in r["rows"]))
        self.assertTrue(all(row["reviewer"] is None for row in r["rows"]))
        self.assertIn("NIE PLAY", render(r))

    def test_first_kickoff_past_is_not_retroactively_approvable(self):
        q, g, d = data()
        r = build(q, g, d, datetime(2026, 10, 17, 15, tzinfo=timezone.utc))
        row = next(row for row in r["rows"]
                   if row["day"] == DAYS[0] and row["league_id"] == "eng.1")
        self.assertEqual(row["time_status"],
                         "FIRST_KICKOFF_PASSED_NO_RETROACTIVE_APPROVAL")
        self.assertEqual(r["totals"]["day_league_checks_after_first_kickoff"], 1)
        self.assertEqual(row["source_role"], "FULL_SEASON_SNAPSHOT_NOT_ATTESTATION")
        self.assertFalse(row["full_day_approved_by_this_packet"])

    def test_future_first_kickoff_still_needs_manual_review(self):
        q, g, d = data()
        r = build(q, g, d, datetime(2026, 10, 17, 11, tzinfo=timezone.utc))
        row = next(row for row in r["rows"]
                   if row["day"] == DAYS[1] and row["league_id"] == "bel.1")
        self.assertEqual(row["time_status"],
                         "FUTURE_FIRST_KICKOFF_MANUAL_REVIEW_REQUIRED")
        self.assertEqual(row["source_role"], "UNDATED_ROUND_ONLY")
        self.assertEqual(row["priority"], 1)
        self.assertFalse(row["fixtures"][0]["organizer_confirmed"])

    def test_empty_candidates_not_official_zero(self):
        q, g, d = data()
        r = build(q, g, d, datetime(2026, 10, 17, 11, tzinfo=timezone.utc))
        row = next(row for row in r["rows"]
                   if row["day"] == DAYS[0] and row["league_id"] == "uefa.champions")
        self.assertEqual(row["time_status"], "ZERO_CANDIDATES_NOT_CONFIRMED_ZERO_DAY")
        self.assertEqual(row["priority"], 3)
        self.assertIn("Brak kandydatów", render(r))

    def test_reject_skipped_competition_or_duplicate_day_row(self):
        q, g, d = data()
        d["rows"] = d["rows"][:-1]
        with self.assertRaisesRegex(ValueError, "fourteen"):
            build(q, g, d)
        q, g, d = data()
        d["rows"].append(copy.deepcopy(d["rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build(q, g, d)

    def test_reject_mismatched_candidate_count_or_extra_game(self):
        q, g, d = data()
        d["rows"][0]["espn_candidates"] = 9
        with self.assertRaisesRegex(ValueError, "Inconsistent"):
            build(q, g, d)
        q, g, d = data()
        q["fixtures"].append({"date_warsaw": DAYS[0], "fixture_id": "unknown.1:4"})
        with self.assertRaisesRegex(ValueError, "outside official"):
            build(q, g, d)

    def test_reject_bad_clock_and_untrusted_link(self):
        q, g, d = data()
        with self.assertRaisesRegex(ValueError, "timezone"):
            build(q, g, d, datetime(2026, 10, 17, 15))
        d["rows"][0]["organizer_review_url"] = "http://example.org/untrusted"
        with self.assertRaisesRegex(ValueError, "Invalid organizer"):
            build(q, g, d)

    def test_formal_blockers_are_exactly_validator_blocks(self):
        q, g, d = data()
        g["days"][DAYS[1]]["competitions"][0]["errors"].append(
            "OFFICIAL_VS_INDEPENDENT_FIXTURE_COUNT_DIFFERENCE"
        )
        r = build(q, g, d)
        self.assertEqual(r["totals"]["formal_blocker_occurrences"], 57)
        self.assertEqual(r["totals"]["formal_blocker_types"][
            "OFFICIAL_VS_INDEPENDENT_FIXTURE_COUNT_DIFFERENCE"], 1)
        self.assertIn("OFFICIAL_VS_INDEPENDENT_FIXTURE_COUNT_DIFFERENCE", render(r))


    def test_unsigned_partial_evidence_is_shown_but_never_signed(self):
        q, g, d = data()
        from tools.kb21_official_review import OFFICIAL_PAGES
        review = {
            "days": {day: {league: {
                "reviewer": None, "captured_at": None,
                "full_day_checked": False, "confirmed_zero_matches": None,
                "fixtures": [], "organizer_url": url,
            } for league, url in OFFICIAL_PAGES.items()} for day in DAYS},
            "approval": None, "daily_approvals": {day: None for day in DAYS},
        }
        review["days"][DAYS[0]]["uefa.nations"]["partial_official_source_hints"] = {
            "kind": "DATE_CLUB_ONLY_UNVERIFIED_KICKOFF",
            "source_status": "OFFICIAL_LEAGUE_PHASE_ARTICLE_PARTIAL_FOR_REVIEW",
            "captured_at_utc": "2026-10-17T09:00:00Z",
            "organizer_full_day_attested": False,
            "date_and_kickoff_authenticated": False,
            "fixture_hints": [{"home": "Poland", "away": "Sweden",
                               "date_printed": DAYS[0], "clock_verified": False}],
        }
        result = build(q, g, d, partial_draft=review)
        self.assertEqual(result["totals"]["partial_hint_league_days"], 1)
        self.assertIn("Poland", render(result))
        self.assertIn("POMOCNICZY DOWÓD ORGANIZATORA", render(result))
        self.assertFalse(result["safe_to_publish_play"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_partially_signed_or_wrong_date_hints_refused(self):
        q, g, d = data()
        bad = {"days": {day: {} for day in DAYS}, "approval": None}
        with self.assertRaisesRegex(ValueError, "omitted competition"):
            build(q, g, d, partial_draft=bad)
        signed = {"days": {day: {} for day in DAYS},
                  "approval": {"reviewer": "fake"}}
        with self.assertRaisesRegex(ValueError, "unsigned"):
            build(q, g, d, partial_draft=signed)

    def test_day_wide_kickoff_closes_other_league_and_empty_slots(self):
        q, g, d = data()
        # EPL kicks off at 14:00 UTC. LaLiga's first event is later,
        # but the signoff validator requires whole-day approval before EPL.
        q["fixtures"].append({
            "date_warsaw": DAYS[0], "fixture_id": "esp.1:301",
            "fixture": "Real Betis - Barcelona",
            "kickoff": "2026-10-17T19:00:00+02:00",
        })
        target = next(x for x in d["rows"]
                      if x["day"] == DAYS[0] and x["league_id"] == "esp.1")
        target["espn_candidates"] = 1
        report = build(q, g, d, datetime(2026, 10, 17, 15, tzinfo=timezone.utc))
        by_league = {x["league_id"]: x for x in report["rows"] if x["day"] == DAYS[0]}
        self.assertEqual(by_league["esp.1"]["time_status"],
                         "FUTURE_FIRST_KICKOFF_MANUAL_REVIEW_REQUIRED")
        self.assertEqual(by_league["esp.1"]["day_wide_review_deadline"]["prematch_signoff_status"],
                         "DAY_FIRST_KICKOFF_ALREADY_PASSED")
        self.assertEqual(by_league["uefa.champions"]["day_wide_review_deadline"]["prematch_signoff_status"],
                         "DAY_FIRST_KICKOFF_ALREADY_PASSED")
        self.assertEqual(report["totals"]["whole_days_after_first_candidate_kickoff"], 1)
        self.assertIn("TERMIN DLA CAŁEGO DNIA", render(report))

    def test_comparator_result_kept_as_observation_not_signoff(self):
        q, g, d = data()
        comparisons = {
            (item["date_warsaw"], item["fixture_id"]): {
                "organizer_comparator_status": "KICKOFF_CONFLICT",
                "official_kickoff_claim": "2026-10-17T16:30:00+02:00",
                "comparison_file": "official-fpl-vs-espn.json",
                "kickoff_evidence_validated_by_signoff": False,
            } for item in q["fixtures"]
        }
        result = build(q, g, d, comparisons=comparisons)
        self.assertEqual(result["totals"]["candidate_comparisons_with_source_conflicts"], 2)
        self.assertIn("KICKOFF_CONFLICT", render(result))
        self.assertFalse(result["safe_to_publish_play"])
        comparisons[(DAYS[0], "eng.1:111")]["kickoff_evidence_validated_by_signoff"] = True
        with self.assertRaisesRegex(ValueError, "must remain diagnostic"):
            build(q, g, d, comparisons=comparisons)

    def test_unknown_day_kickoff_fails_open_window_claim(self):
        q, g, d = data()
        q["fixtures"][0]["kickoff"] = None
        r = build(q, g, d, datetime(2026, 10, 17, 10, tzinfo=timezone.utc))
        self.assertEqual(r["day_review_deadlines"][DAYS[0]]["prematch_signoff_status"],
                         "DAY_KICKOFF_UNKNOWN_SIGNOFF_WINDOW_UNVERIFIABLE")


    def test_early_official_archive_is_visible_without_signing_day(self):
        q, g, d = data()
        early = {
            "schema": "kb21-earliest-kickoff-early-official-crosscheck-v1",
            "days": DAYS, "calendar_gate": "BLOCKED",
            "matches": [{
                "day": DAYS[0], "fixture_id": "eng.1:111",
                "status": "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW",
                "capture_at_utc": "2026-10-17T08:00:00+00:00",
                "official_kickoff_from_early_capture": "2026-10-17T14:00:00+00:00",
                "prematch_clock_review_only": True, "calendar_gate": "BLOCKED",
            }],
        }
        r = build(q, g, d, early_archive=early)
        self.assertEqual(r["totals"]["early_official_archive_matches"], 1)
        self.assertIn("Archiwum oficjalne", render(r))
        self.assertFalse(r["safe_to_publish_play"])
        self.assertEqual(r["totals"]["source_day_signoffs_from_packet"], 0)
        early["matches"][0]["capture_at_utc"] = "2026-10-17T15:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "pre-day"):
            build(q, g, d, early_archive=early)
        early["matches"][0]["capture_at_utc"] = "2026-10-17T08:00:00+00:00"
        early["matches"][0]["prematch_clock_review_only"] = False
        with self.assertRaisesRegex(ValueError, "cannot approve"):
            build(q, g, d, early_archive=early)

    def test_early_organizer_revisions_remain_explicitly_unsigned(self):
        q, g, d = data()
        revisions = {
            "schema": "kb21-early-official-revision-audit-v1",
            "days": DAYS, "calendar_gate": "BLOCKED",
            "safe_to_publish_play": False,
            "rows": [{
                "day": day, "league_id": league,
                "status": "NO_EARLY_OFFICIAL_SNAPSHOT",
                "eligible_snapshot_count": 0,
                "last_capture_utc": None, "first_capture_utc": None,
                "added_pairs": [], "removed_pairs": [],
                "kickoff_changes": [], "calendar_gate": "BLOCKED",
                "full_organizer_day_attested": False, "human_signed": False,
            } for day in DAYS for league in ("eng.1", "ned.1", "ger.1", "esp.1")],
        }
        changed = revisions["rows"][0]
        changed.update({
            "status": "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW",
            "eligible_snapshot_count": 2,
            "first_capture_utc": "2026-10-17T07:00:00Z",
            "last_capture_utc": "2026-10-17T09:00:00Z",
            "removed_pairs": [{"home": "Arsenal", "away": "Chelsea",
                               "earliest_kickoff_utc": "2026-10-17T14:00:00Z"}],
        })
        r = build(q, g, d, early_revisions=revisions)
        self.assertEqual(r["totals"]["early_organizer_day_revisions_to_review"], 1)
        self.assertIn("WYMAGA SPRAWDZENIA ZMIAN", render(r))
        self.assertFalse(r["safe_to_publish_play"])
        self.assertEqual(r["totals"]["source_day_signoffs_from_packet"], 0)
        changed["last_capture_utc"] = "2026-10-17T15:00:00Z"
        with self.assertRaisesRegex(ValueError, "after first game"):
            build(q, g, d, early_revisions=revisions)
        changed["last_capture_utc"] = "2026-10-17T09:00:00Z"
        changed["human_signed"] = True
        with self.assertRaisesRegex(ValueError, "cannot grant approval"):
            build(q, g, d, early_revisions=revisions)

    def test_early_organizer_revisions_require_every_two_league_day_cell(self):
        q, g, d = data()
        bad = {
            "schema": "kb21-early-official-revision-audit-v1",
            "days": DAYS, "calendar_gate": "BLOCKED",
            "safe_to_publish_play": False, "rows": [],
        }
        with self.assertRaisesRegex(ValueError, "missing competition/day"):
            build(q, g, d, early_revisions=bad)

    def test_real_zero_day_worklist_is_displayed_but_never_approved(self):
        q, g, d = data()
        day, league = DAYS[0], "eng.1"
        # English league has a game on this mock day, so use an empty
        # competition slot with no candidates: no fabrication of fixtures.
        league = "esp.1"
        official_row = next(x for x in g["days"][day]["competitions"]
                            if x["league_id"] == league)
        official_row["errors"].append("ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER")
        item = {
            "day": day, "league_id": league, "status": "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE",
            "action": "Review the complete official Spanish schedule",
            "machine_zero_candidate_needs_human_review": False,
            "automated_source_capture_utc": None,
            "human_reviewer": None, "confirmed_zero_matches": None,
            "full_day_checked": False, "calendar_gate": "BLOCKED",
        }
        report = {"schema": "kb21-zero-day-evidence-worklist-v1",
                  "days": DAYS, "calendar_gate": "BLOCKED",
                  "safe_to_publish_play": False, "rows": [item]}
        got = build(q, g, d, zero_evidence=report)
        self.assertEqual(got["totals"]["zero_day_review_cells"], 1)
        self.assertIn("NIEPOTWIERDZONY DZIEŃ BEZ SPOTKAŃ", render(got))
        self.assertFalse(got["safe_to_publish_play"])
        item["human_reviewer"] = "made up"
        with self.assertRaisesRegex(ValueError, "cannot sign"):
            build(q, g, d, zero_evidence=report)
        item["human_reviewer"] = None
        item["machine_zero_candidate_needs_human_review"] = True
        with self.assertRaisesRegex(ValueError, "False full-season"):
            build(q, g, d, zero_evidence=report)
        report["rows"] = []
        with self.assertRaisesRegex(ValueError, "each formal"):
            build(q, g, d, zero_evidence=report)

    def test_signed_date_discards_only_its_old_zero_worklist_tasks(self):
        q, g, d = data()
        record = next(x for x in g["days"][DAYS[1]]["competitions"]
                      if x["league_id"] == "esp.1")
        record["errors"].append("ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER")
        # Day 0 was actually validated as PASS_MANUAL. Its old unsigned
        # zero-source row must not erase the still pending day 1 review.
        g["days"][DAYS[0]]["calendar_gate"] = "PASS_MANUAL"
        items = [{
            "day": day, "league_id": "esp.1",
            "status": "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE",
            "action": "Review complete organizer schedule",
            "machine_zero_candidate_needs_human_review": False,
            "automated_source_capture_utc": None,
            "human_reviewer": None, "confirmed_zero_matches": None,
            "full_day_checked": False, "calendar_gate": "BLOCKED",
        } for day in DAYS]
        worklist = {
            "schema": "kb21-zero-day-evidence-worklist-v1",
            "days": DAYS, "calendar_gate": "BLOCKED",
            "safe_to_publish_play": False, "rows": items,
        }
        packet = build(q, g, d, zero_evidence=worklist)
        self.assertEqual(packet["totals"]["zero_day_review_cells"], 1)
        self.assertFalse(packet["safe_to_publish_play"])
        first = next(x for x in packet["rows"]
                     if x["day"] == DAYS[0] and x["league_id"] == "esp.1")
        second = next(x for x in packet["rows"]
                      if x["day"] == DAYS[1] and x["league_id"] == "esp.1")
        self.assertIsNone(first["zero_day_proof_worklist"])
        self.assertEqual(second["zero_day_proof_worklist"]["status"],
                         "NO_COMPLETE_OFFICIAL_DAY_EVIDENCE")
        g["days"][DAYS[0]]["calendar_gate"] = "BLOCKED"
        with self.assertRaisesRegex(ValueError, "each formal zero blocker"):
            build(q, g, d, zero_evidence=worklist)

if __name__ == "__main__":
    unittest.main()
