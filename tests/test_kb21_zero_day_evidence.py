"""A complete FPL catalogue helps manual zero-day review, NEVER authorizes it."""
import copy
import unittest

from tests.test_kb21_calendar_signoff import sample
from tools.kb21_zero_day_evidence import build, render


def materials():
    q, i = sample()
    # Independent match belongs to Portugal; England has no candidates.
    q["fixtures"][0]["fixture_id"] = "por.1:111"
    draft = copy.deepcopy(i)
    draft["approval"] = None
    draft["daily_approvals"] = {day: None for day in draft["days"]}
    for row in draft["days"][q["days"][0]].values():
        row.update({"fixtures": [], "captured_at": None, "reviewer": None,
                    "full_day_checked": False, "confirmed_zero_matches": None})
    return q, draft


def fpl(captured="2026-10-17T08:00:00Z", match=False):
    return {
        "schema": "kb21-official-premier-league-fpl-v1",
        "league_id": "eng.1",
        "calendar_gate": "BLOCKED",
        "reviewer_signed": False, "full_calendar_verified": False,
        "season_full_380_catalogue": True, "season_fixture_count": 380,
        "season_team_count": 20, "fixtures_missing_kickoff_count": 0,
        "invalid_or_provisional_fixture_ids": [],
        "days": ["2026-10-18"], "captured_at_utc": captured,
        "by_day": {"2026-10-18": ([{
            "fixture_id": 450, "league_id": "eng.1",
            "home": "Chelsea", "away": "Arsenal",
            "kickoff_utc": "2026-10-18T14:00:00Z",
        }] if match else [])},
        "official_fixture_endpoint": "https://fantasy.premierleague.com/api/fixtures/",
    }


class ZeroDayEvidenceTests(unittest.TestCase):
    def test_valid_full_380_source_only_prioritizes_human_review(self):
        q, draft = materials()
        original = copy.deepcopy(draft)
        r = build(q, draft, fpl())
        self.assertEqual(draft, original)
        self.assertEqual(r["totals"]["zero_game_review_cells"], 14)
        self.assertEqual(r["totals"]["full_season_fpl_zero_candidates"], 1)
        self.assertEqual(r["calendar_gate"], "BLOCKED")
        self.assertFalse(r["safe_to_publish_play"])
        eng = next(x for x in r["rows"] if x["league_id"] == "eng.1")
        self.assertEqual(eng["status"],
                         "FULL_SEASON_FPL_ZERO_CANDIDATE_NEEDS_HUMAN_SIGNOFF")
        self.assertFalse(eng["full_day_checked"])
        self.assertIsNone(eng["human_reviewer"])
        self.assertIsNone(eng["confirmed_zero_matches"])
        self.assertIn("ZERO PODPISÓW", render(r))

    def test_post_kickoff_fpl_never_claims_prematch_candidate(self):
        q, draft = materials()
        r = build(q, draft, fpl(captured="2026-10-18T17:30:00Z"))
        self.assertEqual(r["totals"]["full_season_fpl_zero_candidates"], 0)
        eng = next(x for x in r["rows"] if x["league_id"] == "eng.1")
        self.assertEqual(eng["status"],
                         "FULL_SEASON_FPL_EMPTY_DAY_CAPTURE_TOO_LATE")

    def test_incomplete_fpl_catalogue_is_not_zero_day_proof(self):
        q, draft = materials()
        source = fpl()
        source["season_fixture_count"] = 379
        r = build(q, draft, source)
        self.assertEqual(r["totals"]["full_season_fpl_zero_candidates"], 0)
        source = fpl()
        source["fixtures_missing_kickoff_count"] = 1
        self.assertEqual(build(q, draft, source)["totals"][
            "full_season_fpl_zero_candidates"], 0)

    def test_fpl_scheduled_match_disagrees_with_empty_espn(self):
        q, draft = materials()
        result = build(q, draft, fpl(match=True))
        self.assertEqual(result["totals"]["suspicious_independent_zero_cases"], 1)
        eng = next(x for x in result["rows"] if x["league_id"] == "eng.1")
        self.assertEqual(eng["status"],
                         "OFFICIAL_FPL_LISTS_GAMES_ESPN_LISTS_ZERO")

    def test_missing_organizer_rows_while_espn_has_fixture_is_not_zero(self):
        q, draft = materials()
        result = build(q, draft, fpl())
        por = next(x for x in result["rows"] if x["league_id"] == "por.1")
        self.assertEqual(por["status"], "ESPN_HAS_FIXTURES_BUT_ORGANIZER_INVENTORY_EMPTY")
        self.assertEqual(por["independent_candidates"], 1)

    def test_partial_source_cannot_certify_empty_day(self):
        q, draft = materials()
        draft["days"]["2026-10-18"]["bel.1"]["partial_official_source_hints"] = {
            "kind": "UNDATED_SELECTED_ROUND_ONLY", "fixture_hints": []}
        result = build(q, draft)
        row = next(x for x in result["rows"] if x["league_id"] == "bel.1")
        self.assertEqual(row["status"], "PARTIAL_OR_UNDATED_SOURCE_CANNOT_CERTIFY_ZERO")
        self.assertEqual(result["totals"]["full_season_fpl_zero_candidates"], 0)

    def test_refuse_forged_human_approval(self):
        q, draft = materials()
        draft["days"]["2026-10-18"]["eng.1"]["reviewer"] = "fake reviewer"
        with self.assertRaisesRegex(ValueError, "edited or signed"):
            build(q, draft, fpl())
        q, draft = materials()
        draft["approval"] = {"reviewer": "fake reviewer"}
        with self.assertRaisesRegex(ValueError, "unsigned"):
            build(q, draft, fpl())

    def test_no_independent_day_first_kickoff_does_not_certify_zero(self):
        q, draft = materials()
        q["fixtures"] = []
        report = build(q, draft, fpl())
        eng = next(x for x in report["rows"] if x["league_id"] == "eng.1")
        self.assertEqual(eng["status"],
                         "FULL_SEASON_FPL_EMPTY_DAY_NO_KNOWN_EARLIEST_START")


if __name__ == "__main__":
    unittest.main()
