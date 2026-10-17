import unittest
from tools.kb21_official_source_seed import seed

DAYS = ["2026-10-18", "2026-10-19"]


def draft():
    def blank():
        return {"fixtures": [], "reviewer": None, "captured_at": None,
                "full_day_checked": False, "confirmed_zero_matches": None}
    return {"days": {date: {"por.1": blank()} for date in DAYS}, "approval": None}


def portugal():
    return {
        "schema": "kb21-official-portugal-club-postponement-v1",
        "league_id": "por.1", "days": DAYS,
        "status": "CLUB_ARTICLE_PARTIAL_FOR_REVIEW",
        "captured_at_utc": "2026-10-17T09:00:00+00:00",
        "official_url": "https://gilvicentefc.pt/data-e-hora-do-jogo-em-atraso-com-o-sc-braga/",
        "source_comparison": "DISPLAY_TIMEZONE_NOT_STATED",
        "errors": [],
        "by_day": {
            "2026-10-18": [],
            "2026-10-19": [{"home": "SC Braga", "away": "Gil Vicente FC",
                           "kickoff_warsaw": "2026-10-19T21:15:00+02:00"}],
        },
    }


class PortugalSeedTests(unittest.TestCase):
    def test_single_postponed_match_is_unsigned_only(self):
        result = seed(draft(), {"por.1": portugal()})
        row = result["days"]["2026-10-19"]["por.1"]
        self.assertEqual(len(row["fixtures"]), 1)
        self.assertEqual(row["organizer_source_catalogue_kind"],
                         "ONE_PORTUGAL_POSTPONED_CLUB_MATCH")
        self.assertEqual(row["organizer_unresolved_display_timezone"],
                         "DISPLAY_TIMEZONE_NOT_STATED")
        self.assertTrue(row["organizer_source_not_full_day"])
        self.assertIsNone(row["reviewer"])
        self.assertFalse(row["full_day_checked"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIsNone(result["approval"])

    def test_no_club_match_on_sunday_is_not_zero_confirmation(self):
        result = seed(draft(), {"por.1": portugal()})
        row = result["days"]["2026-10-18"]["por.1"]
        self.assertEqual(row["fixtures"], [])
        self.assertIsNone(row["confirmed_zero_matches"])

    def test_no_gil_confirmation_cannot_prefill(self):
        bad = portugal()
        bad["status"] = "NO_AUTHENTICATED_CLUB_FIXTURE"
        report = seed(draft(), {"por.1": bad})
        self.assertEqual(report["days"]["2026-10-19"]["por.1"]["fixtures"], [])
        self.assertNotIn("por.1",
                         report["organizer_live_seed_summary"]["fixtures_prefilled"])

    def test_conflicting_research_is_preserved(self):
        manual = draft()
        manual["days"]["2026-10-19"]["por.1"]["fixtures"] = [{
            "home": "SC Braga", "away": "Gil Vicente",
            "kickoff": "2026-10-19T20:15:00+02:00"}]
        report = seed(manual, {"por.1": portugal()})
        row = report["days"]["2026-10-19"]["por.1"]
        self.assertEqual(row["fixtures"][0]["kickoff"],
                         "2026-10-19T20:15:00+02:00")
        self.assertTrue(row["organizer_data_discrepancies"]["requires_manual_check"])


if __name__ == "__main__":
    unittest.main()
