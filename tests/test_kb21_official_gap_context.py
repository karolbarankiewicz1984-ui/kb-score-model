"""Adjacent official fixtures are useful context, not signed zero dates."""
import copy
from datetime import datetime, timezone
import unittest

from tests.test_kb21_zero_day_evidence import materials
from tools.kb21_official_gap_context import date_gap, PORTUGAL_SEASON_SCHEDULE
from tools.kb21_official_press_fixtures import SOURCES
from tools.kb21_official_knvb import SOURCE as KNVB_URL
from tools.kb21_zero_day_evidence import build, render

DAY = "2026-10-19"
NOW = datetime(2026, 10, 17, 21, tzinfo=timezone.utc)
DEADLINE = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)


def press():
    return {
        "schema": "kb21-official-press-fixtures-v1",
        "league_id": "fra.1", "days": [DAY],
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False, "errors": [],
        "status": "OFFICIAL_DATED_ARTICLE_PARTIAL_FOR_REVIEW",
        "official_url": SOURCES["fra.1"][0],
        "captured_at_utc": "2026-10-17T17:00:00Z",
        "parsed_article_fixture_count": 18,
        "expected_article_fixture_count": 18,
        "article_fixture_dates": [
            "2026-10-16", "2026-10-17", "2026-10-18",
            "2026-10-23", "2026-10-24", "2026-10-25"],
        "by_day": {DAY: []},
    }


def knvb():
    return {
        "schema": "kb21-official-knvb-eredivisie-v1",
        "league_id": "ned.1", "days": [DAY],
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False, "errors": [],
        "status": "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW",
        "official_url": KNVB_URL,
        "captured_at_utc": "2026-10-17T17:00:00Z",
        "page_fixture_count": 16,
        "page_dates_found": ["2026-10-17", "2026-10-18", "2026-10-23"],
        "unconfirmed_zero_dates": [DAY],
        "by_day": {DAY: []},
    }


def scope_19():
    q, inventory = materials()
    former = q["days"][0]
    q["days"] = [DAY]
    for fixture in q["fixtures"]:
        fixture["date_warsaw"] = DAY
        fixture["kickoff"] = "2026-10-19T18:00:00+02:00"
    inventory["days"][DAY] = inventory["days"].pop(former)
    inventory["daily_approvals"] = {DAY: None}
    return q, inventory


class GapDateContextTests(unittest.TestCase):
    def test_real_ligue1_round_gap_helps_review_but_not_zero_confirmation(self):
        q, inv = scope_19()
        report = build(q, inv, now=NOW, ligue1=press(), knvb=knvb())
        hints = {x["league_id"]: x for x in report["rows"]}
        self.assertEqual(report["totals"]["adjacent_official_round_context_rows"], 2)
        for league in ("fra.1", "ned.1"):
            row = hints[league]
            self.assertEqual(row["status"], "ADJACENT_OFFICIAL_MATCHDAYS_ONLY_NOT_ZERO_PROOF")
            self.assertFalse(row["full_day_checked"])
            self.assertIsNone(row["human_reviewer"])
            self.assertIsNone(row["confirmed_zero_matches"])
            self.assertEqual(row["calendar_gate"], "BLOCKED")
            self.assertEqual(row["adjacent_official_matchday_dates"]["next_visible_date"],
                             "2026-10-23")
        self.assertEqual(hints["fra.1"]["adjacent_official_matchday_dates"]
                         ["previous_visible_date"], "2026-10-18")
        self.assertIn("Sąsiednie oficjalne terminy", render(report))
        self.assertFalse(report["safe_to_publish_play"])

    def test_false_complete_or_signed_article_is_not_a_hint(self):
        src = press()
        src["reviewer_signed"] = True
        self.assertIsNone(date_gap("fra.1", DAY, src, DEADLINE))
        src = press()
        src["parsed_article_fixture_count"] = 9
        self.assertIsNone(date_gap("fra.1", DAY, src, DEADLINE))
        src = press()
        src["by_day"][DAY] = [{"home": "X", "away": "Y"}]
        self.assertIsNone(date_gap("fra.1", DAY, src, DEADLINE))
        src = press()
        src["errors"] = ["fetch failed"]
        self.assertIsNone(date_gap("fra.1", DAY, src, DEADLINE))

    def test_knvb_date_gap_cannot_confuse_other_competition_or_third_party(self):
        src = knvb()
        self.assertIsNone(date_gap("fra.1", DAY, src, DEADLINE))
        src = knvb()
        src["official_url"] = "https://unknown.example/eredivisie"
        self.assertIsNone(date_gap("ned.1", DAY, src, DEADLINE))
        src = knvb()
        src["page_dates_found"].append(DAY)
        self.assertIsNone(date_gap("ned.1", DAY, src, DEADLINE))
        src = knvb()
        src["page_dates_found"] = ["2026-10-17", "2026-10-18"]
        self.assertIsNone(date_gap("ned.1", DAY, src, DEADLINE))

    def test_capture_after_start_remains_context_but_no_prematch_claim(self):
        src = press()
        src["captured_at_utc"] = "2026-10-19T18:00:00Z"
        evidence = date_gap("fra.1", DAY, src, DEADLINE)
        self.assertIsNotNone(evidence)
        self.assertFalse(evidence["snapshot_taken_before_first_whole_day_candidate"])
        self.assertFalse(evidence["verified_zero_games"])

    def test_portugal_cup_pdf_is_only_manual_context(self):
        q, inv = materials()
        r = build(q, inv)
        por = next(row for row in r["rows"] if row["league_id"] == "por.1")
        self.assertEqual(por["supplemental_organizer_calendar_for_manual_review"],
                         PORTUGAL_SEASON_SCHEDULE)
        self.assertEqual(por["status"], "ESPN_HAS_FIXTURES_BUT_ORGANIZER_INVENTORY_EMPTY")
        self.assertFalse(r["safe_to_publish_play"])

    def test_no_remote_article_cannot_change_prior_blocker_counts(self):
        q, inv = scope_19()
        without = build(q, inv, now=NOW)
        with_official = build(q, inv, now=NOW, ligue1=press(), knvb=knvb())
        self.assertEqual(without["totals"]["zero_game_review_cells"],
                         with_official["totals"]["zero_game_review_cells"])
        self.assertEqual(with_official["totals"]["never_human_signed"],
                         without["totals"]["never_human_signed"])
        self.assertTrue(all(not row["full_day_checked"] for row in with_official["rows"]))


if __name__ == "__main__":
    unittest.main()
