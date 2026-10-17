import unittest

from tools.kb21_official_review import OFFICIAL_PAGES, build, render
from tools.kb21_calendar_coverage import SCOPE


class OfficialReviewTests(unittest.TestCase):
    def test_every_league_day_requires_explicit_organizer_confirmation(self):
        coverage = {"days": {
            "2026-10-17": {"core_leagues": [
                {"league_id": "eng.1", "competition": "Premier League",
                 "espn_candidates": 6, "independent_provider_candidates": 6,
                 "crossmatched": 6,
                 "status": "TWO_PROVIDER_CANDIDATE_AGREEMENT_REVIEW"},
            ], "other_competitions": []},
            "2026-10-18": {"core_leagues": [], "other_competitions": []},
        }}
        result = build(coverage)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertFalse(result["all_days_organizer_verified"])
        self.assertEqual(result["days"]["2026-10-17"]["total_competitions_to_review"], len(SCOPE))
        self.assertEqual(result["days"]["2026-10-18"]["total_competitions_to_review"], len(SCOPE))
        premier = result["days"]["2026-10-17"]["rows"][0]
        self.assertEqual(premier["review_priority"], "VERIFY_ORGANIZER_COMPLETE_LIST")
        self.assertFalse(premier["official_schedule_checked"])
        self.assertIsNone(premier["organizer_fixture_capture"])
        self.assertFalse(premier["full_match_list_compared"])
        self.assertIn("https://www.premierleague.com/", premier["organizer_entry_url"])
        belgium = next(x for x in result["days"]["2026-10-17"]["rows"]
                       if x["league_id"] == "bel.1")
        self.assertIsNone(belgium["organizer_entry_url"])
        self.assertEqual(belgium["review_priority"], "SOURCE_URL_MISSING")
        self.assertIn("Calendar Gate BLOCKED", render(result))
        self.assertNotIn("Calendar Gate PASS", render(result))

    def test_bad_input_not_accepted(self):
        with self.assertRaises(ValueError):
            build({"days": []})
        with self.assertRaises(ValueError):
            build({"days": {"2026-10-17": None}})

    def test_known_official_pages_use_https(self):
        self.assertEqual(set(SCOPE) - set(OFFICIAL_PAGES), {"bel.1"})
        self.assertTrue(all(x.startswith("https://") for x in OFFICIAL_PAGES.values()))


if __name__ == "__main__":
    unittest.main()
