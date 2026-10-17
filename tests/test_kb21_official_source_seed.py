import copy
import unittest
from tools.kb21_official_source_seed import seed


DAYS = ["2026-10-17", "2026-10-18"]


def draft():
    def entry():
        return {"organizer_url": "https://www.premierleague.com/en/matches/premier-league/2026-27",
                "fixtures": [], "captured_at": None, "reviewer": None,
                "full_day_checked": False, "confirmed_zero_matches": None}
    return {"days": {day: {"eng.1": entry(), "ger.1": entry()}
                     for day in DAYS},
            "approval": None, "daily_approvals": {day: None for day in DAYS}}


def fixture(day, home, away, time):
    return {"home": home, "away": away, "kickoff_warsaw": f"{day}T{time}:00+02:00"}


def official_fpl():
    return {"schema": "kb21-official-premier-league-fpl-v1",
            "league_id": "eng.1",
            "days": DAYS,
            "season_full_380_catalogue": True,
            "captured_at_utc": "2026-10-17T09:00:00+00:00",
            "official_fixture_endpoint": "https://fantasy.premierleague.com/api/fixtures/",
            "by_day": {
                DAYS[0]: [fixture(DAYS[0], "Everton", "Chelsea", "13:30")],
                DAYS[1]: [fixture(DAYS[1], "Manchester City", "Ipswich Town", "16:00")]
            }}


def official_dfl():
    return {"schema": "kb21-official-bundesliga-media-v1",
            "league_id": "ger.1", "status": "OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW",
            "days": DAYS, "captured_at_utc": "2026-10-17T09:00:00+00:00",
            "official_url": "https://products.bundesliga.com/fixtures",
            "by_day": {
                DAYS[0]: [fixture(DAYS[0], "Hamburger SV", "VfB Stuttgart", "15:30")],
                DAYS[1]: []
            }}


class OfficialSourceSeedTests(unittest.TestCase):
    def test_all_three_sources_stay_unsigned(self):
        original = draft()
        preserved = copy.deepcopy(original)
        result = seed(original, {"eng.1": official_fpl(), "ger.1": official_dfl()})
        self.assertEqual(original, preserved)
        self.assertEqual(result["organizer_live_seed_summary"]["fixtures_prefilled"],
                         {"eng.1": 2, "ger.1": 1})
        premier = result["days"][DAYS[0]]["eng.1"]
        self.assertEqual(premier["fixtures"][0]["home"], "Everton")
        self.assertEqual(premier["organizer_source_catalogue_kind"], "FULL_SEASON_380_FPL")
        self.assertFalse(premier["full_day_checked"])
        self.assertIsNone(premier["captured_at"])
        self.assertIsNone(premier["reviewer"])
        self.assertIsNone(premier["confirmed_zero_matches"])
        self.assertIsNone(result["approval"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")

    def test_dfl_empty_day_does_not_claim_no_games(self):
        report = seed(draft(), {"ger.1": official_dfl()})
        row = report["days"][DAYS[1]]["ger.1"]
        self.assertEqual(row["fixtures"], [])
        self.assertIsNone(row["confirmed_zero_matches"])
        self.assertFalse(row["full_day_checked"])

    def test_existing_research_never_overwritten_on_conflict(self):
        original = draft()
        original["days"][DAYS[0]]["eng.1"]["fixtures"] = [{
            "home": "Everton", "away": "Chelsea",
            "kickoff": f"{DAYS[0]}T14:00:00+02:00"
        }]
        report = seed(original, {"eng.1": official_fpl()})
        first = report["days"][DAYS[0]]["eng.1"]
        self.assertEqual(first["fixtures"], original["days"][DAYS[0]]["eng.1"]["fixtures"])
        self.assertEqual(
            first["organizer_data_discrepancies"]["additional_organizer_events"][0]["kickoff"],
            f"{DAYS[0]}T13:30:00+02:00")
        self.assertGreater(
            report["organizer_live_seed_summary"]["discrepancies_against_existing_research"]["eng.1"],
            0)
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_bad_scope_and_signed_input_rejected(self):
        source = official_fpl()
        source["days"] = [DAYS[0]]
        with self.assertRaises(ValueError):
            seed(draft(), {"eng.1": source})
        original = draft()
        original["approval"] = {"reviewer": "someone"}
        with self.assertRaises(ValueError):
            seed(original, {"eng.1": official_fpl()})
        original = draft()
        original["days"][DAYS[0]]["eng.1"]["full_day_checked"] = True
        with self.assertRaises(ValueError):
            seed(original, {"eng.1": official_fpl()})

    def test_incomplete_fpl_source_cannot_fill_full_season(self):
        source = official_fpl()
        source["season_full_380_catalogue"] = False
        report = seed(draft(), {"eng.1": source})
        self.assertNotIn("eng.1", report["organizer_live_seed_summary"]["fixtures_prefilled"])
        self.assertEqual(report["days"][DAYS[0]]["eng.1"]["fixtures"], [])
        self.assertEqual(report["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
