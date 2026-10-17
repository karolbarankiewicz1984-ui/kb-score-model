import copy
import unittest
from tools.kb21_official_source_seed import seed

DAYS = ["2026-10-17", "2026-10-18"]


def draft():
    def entry():
        return {"fixtures": [], "captured_at": None, "reviewer": None,
                "full_day_checked": False, "confirmed_zero_matches": None}
    return {"days": {day: {"ita.1": entry(), "fra.1": entry()}
                     for day in DAYS}, "approval": None}


def official(league):
    home, away = (("Bologna", "Inter") if league == "ita.1"
                  else ("RC Strasbourg Alsace", "Paris Saint-Germain"))
    return {
        "schema": "kb21-official-press-fixtures-v1", "league_id": league,
        "days": DAYS, "official_url": (
            "https://en.legaseriea.it/serie-a/news/the-referees-for-the-7th-round-x8311"
            if league == "ita.1" else
            "https://ligue1.com/fr/articles/l1_article_5797-"),
        "status": "OFFICIAL_DATED_ARTICLE_PARTIAL_FOR_REVIEW",
        "captured_at_utc": "2026-10-17T10:00:00+00:00",
        "article_fixture_dates": ["2026-10-16", "2026-10-17", "2026-10-18"],
        "errors": [], "by_day": {DAYS[0]: [{"home": home, "away": away,
              "kickoff_warsaw": "2026-10-17T18:00:00+02:00"}], DAYS[1]: []}
    }


class PressSeedTests(unittest.TestCase):
    def test_articles_prefill_only_positive_days_and_never_sign(self):
        source = draft()
        before = copy.deepcopy(source)
        report = seed(source, {league: official(league)
                               for league in ("ita.1", "fra.1")})
        self.assertEqual(source, before)
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertEqual(report["publication"], "DIAGNOSTIC / NO PLAY")
        self.assertIsNone(report["approval"])
        for league in ("ita.1", "fra.1"):
            row = report["days"]["2026-10-17"][league]
            self.assertEqual(len(row["fixtures"]), 1)
            self.assertEqual(row["organizer_source_catalogue_kind"],
                             "DATED_ORGANIZER_ARTICLE_PARTIAL")
            self.assertTrue(row["organizer_source_not_full_day"])
            self.assertFalse(row["full_day_checked"])
            self.assertIsNone(row["reviewer"])
            blank = report["days"]["2026-10-18"][league]
            self.assertEqual(blank["fixtures"], [])
            self.assertIsNone(blank["confirmed_zero_matches"])
            self.assertNotIn("organizer_facts_source", blank)

    def test_existing_conflicting_data_never_overwritten(self):
        x = draft()
        x["days"]["2026-10-17"]["ita.1"]["fixtures"] = [{
            "home": "Bologna", "away": "Inter",
            "kickoff": "2026-10-17T19:00:00+02:00"}]
        report = seed(x, {"ita.1": official("ita.1")})
        self.assertEqual(report["days"]["2026-10-17"]["ita.1"]["fixtures"][0]["kickoff"],
                         "2026-10-17T19:00:00+02:00")
        self.assertGreater(
            report["organizer_live_seed_summary"]["discrepancies_against_existing_research"]["ita.1"], 0)

    def test_wrong_scope_refused(self):
        row = official("fra.1")
        row["days"] = ["2026-10-17"]
        with self.assertRaises(ValueError):
            seed(draft(), {"fra.1": row})


if __name__ == "__main__":
    unittest.main()
