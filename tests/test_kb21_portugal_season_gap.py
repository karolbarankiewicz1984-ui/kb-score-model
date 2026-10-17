"""Official LP J8/J9 gap and known postponed fixture never sign ZERO games."""
import copy
from datetime import datetime, timezone
import unittest

from tests.test_kb21_zero_day_evidence import materials
from tests.test_kb21_official_portugal_postponed import GIL
from tools.kb21_official_portugal_postponed import parse_gil_article
from tools.kb21_portugal_season_gap import season_break, SOURCE
from tools.kb21_zero_day_evidence import build, render


def club():
    return {
        "schema": "kb21-official-portugal-club-postponement-v1",
        "league_id": "por.1",
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False,
        "status": "CLUB_ARTICLE_PARTIAL_FOR_REVIEW",
        "gil_official_article": parse_gil_article(GIL),
    }


def zero_portugal(day="2026-10-18"):
    q, draft = materials()
    old = q["days"][0]
    q["days"] = [day]
    draft["days"] = {day: draft["days"].pop(old)}
    draft["daily_approvals"] = {day: None}
    # Keep one independent fixture, but OUTSIDE the Portuguese league.
    # The gate must still treat 14 league/day cards as unsigned.
    q["fixtures"][0]["fixture_id"] = "eng.1:111"
    q["fixtures"][0]["date_warsaw"] = day
    q["fixtures"][0]["kickoff"] = day + "T18:00:00+02:00"
    return q, draft


class PortugalOfficialGapTests(unittest.TestCase):
    def test_17_and_18_only_from_official_2026_season_calendar(self):
        for day in ("2026-10-17", "2026-10-18"):
            gap = season_break(day)
            self.assertEqual(gap["previous_scheduled_league_round"]["round"], 8)
            self.assertEqual(gap["previous_scheduled_league_round"]
                             ["scheduled_weekend_reference"], "2026-10-11")
            self.assertEqual(gap["next_scheduled_league_round"]["round"], 9)
            self.assertEqual(gap["next_scheduled_league_round"]
                             ["scheduled_weekend_reference"], "2026-10-25")
            self.assertEqual(gap["official_publication"], SOURCE)
            self.assertFalse(gap["confirmed_zero_matches"])
            self.assertFalse(gap["captured_full_date_fixture_list"])
            self.assertFalse(gap["reviewer_signed"])
            self.assertFalse(gap["cpc_amendment_log_reviewed"])
            self.assertEqual(gap["calendar_gate"], "BLOCKED")
        self.assertIsNone(season_break("2026-10-19"))
        self.assertIsNone(season_break("2026-10-25"))
        self.assertIsNone(season_break("2025-10-18"))
        self.assertIsNone(season_break("2027-10-18"))
        self.assertIsNone(season_break("2026-11-18"))

    def test_real_club_article_proves_postponements_can_occur_in_round_break(self):
        gap = season_break("2026-10-18", club())
        post = gap["known_postponement_elsewhere_in_window"]
        self.assertEqual(post["home"], "SC Braga")
        self.assertEqual(post["away"], "Gil Vicente FC")
        self.assertEqual(post["date_warsaw"], "2026-10-19")
        self.assertEqual(post["kickoff_utc"], "2026-10-19T19:15:00+00:00")
        self.assertFalse(gap["confirmed_zero_matches"])

    def test_forged_club_article_never_becomes_postponed_evidence(self):
        fake = club()
        fake["gil_official_article"]["kickoff_utc"] = "2026-10-18T19:15:00Z"
        self.assertIsNone(season_break("2026-10-18", fake)[
            "known_postponement_elsewhere_in_window"])
        fake = club()
        fake["reviewer_signed"] = True
        self.assertIsNone(season_break("2026-10-18", fake)[
            "known_postponement_elsewhere_in_window"])
        fake = club()
        fake["gil_official_article"]["source_url"] = "https://fake.invalid/"
        self.assertIsNone(season_break("2026-10-18", fake)[
            "known_postponement_elsewhere_in_window"])

    def test_18_oct_zero_worklist_gets_dated_reference_without_clearing_gate(self):
        q, draft = zero_portugal()
        saved = copy.deepcopy(draft)
        report = build(q, draft, portugal=club(),
                       now=datetime(2026, 10, 17, 20, tzinfo=timezone.utc))
        self.assertEqual(draft, saved)
        por = next(x for x in report["rows"] if x["league_id"] == "por.1")
        self.assertEqual(por["status"], "PORTUGAL_ROUND_BREAK_CPC_CHANGES_UNCHECKED")
        self.assertEqual(por["portugal_official_published_round_gap"]["day"],
                         "2026-10-18")
        self.assertEqual(report["totals"]["portugal_published_round_break_context_rows"], 1)
        self.assertEqual(report["totals"]["zero_game_review_cells"], 14)
        self.assertEqual(report["totals"]["never_human_signed"], 14)
        self.assertFalse(report["safe_to_publish_play"])
        self.assertIsNone(por["confirmed_zero_matches"])
        self.assertFalse(por["full_day_checked"])
        self.assertIn("J8", render(report))
        self.assertIn("Braga", render(report))

    def test_17_oct_still_not_approved_retroactively(self):
        q, draft = zero_portugal("2026-10-17")
        report = build(q, draft, portugal=club(),
                       now=datetime(2026, 10, 18, tzinfo=timezone.utc))
        por = next(x for x in report["rows"] if x["league_id"] == "por.1")
        self.assertEqual(por["status"], "PORTUGAL_ROUND_BREAK_CPC_CHANGES_UNCHECKED")
        self.assertEqual(por["calendar_gate"], "BLOCKED")
        self.assertFalse(por["full_day_checked"])

    def test_existing_independent_portuguese_match_takes_priority_over_gap(self):
        q, draft = materials()
        report = build(q, draft, portugal=club())
        por = next(x for x in report["rows"] if x["league_id"] == "por.1")
        self.assertEqual(por["status"], "ESPN_HAS_FIXTURES_BUT_ORGANIZER_INVENTORY_EMPTY")
        self.assertEqual(por["independent_candidates"], 1)
        self.assertIsNotNone(por["portugal_official_published_round_gap"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
