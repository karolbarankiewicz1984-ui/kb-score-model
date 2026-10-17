import unittest
from tools.kb21_official_press_compare import compare, render


def source(league="ita.1", kickoff="2026-10-17T15:00:00+02:00"):
    return {
        "schema": "kb21-official-press-fixtures-v1", "league_id": league,
        "days": ["2026-10-17"], "official_url": "https://en.legaseriea.it/",
        "days_outside_article_range": [], "errors": [],
        "by_day": {"2026-10-17": [
            {"home": "Bologna" if league == "ita.1" else "RC Strasbourg Alsace",
             "away": "Internazionale" if league == "ita.1" else "Paris Saint-Germain",
             "kickoff_utc": kickoff, "kickoff_warsaw": kickoff}
        ]}
    }


def queue(league="ita.1", kickoff="2026-10-17T15:00:00+02:00"):
    match = ("Bologna - Inter" if league == "ita.1"
             else "Strasbourg - PSG")
    return {"days": ["2026-10-17"], "fixtures": [
        {"fixture_id": league + ":100", "fixture": match,
         "date_warsaw": "2026-10-17", "kickoff": kickoff}
    ]}


class PressCrosscheckTests(unittest.TestCase):
    def test_serie_a_and_french_aliases_match_but_not_approved(self):
        for league in ("ita.1", "fra.1"):
            with self.subTest(league=league):
                report = compare(queue(league), source(league))
                self.assertEqual(
                    report["days"]["2026-10-17"]["identical_fixture_count"], 1
                )
                self.assertEqual(report["calendar_gate"], "BLOCKED")
                self.assertFalse(report["human_approved"])
                self.assertIn("NO PLAY", render(report))

    def test_conflicting_kickoff_is_explicit(self):
        report = compare(queue(kickoff="2026-10-17T15:30:00+02:00"), source())
        day = report["days"]["2026-10-17"]
        self.assertEqual(day["identical_fixture_count"], 0)
        self.assertEqual(day["statuses"]["KICKOFF_CONFLICT"], 1)

    def test_missing_organizer_fixture_is_not_a_verified_empty_day(self):
        s = source()
        s["by_day"]["2026-10-17"] = []
        report = compare(queue(), s)
        self.assertEqual(
            report["days"]["2026-10-17"]["statuses"]["MISSING_IN_ORGANIZER_ARTICLE"],
            1
        )
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_article_only_match_and_outside_article_range(self):
        s = source()
        s["days_outside_article_range"] = ["2026-10-17"]
        report = compare({"days": ["2026-10-17"], "fixtures": []}, s)
        self.assertEqual(report["days"]["2026-10-17"]["statuses"]["ORGANIZER_ONLY"], 1)
        self.assertIn("2026-10-17", render(report))

    def test_date_missing_inside_press_window_visible_in_report(self):
        info = source("fra.1")
        info["days_without_article_fixture_evidence"] = ["2026-10-17"]
        report = compare(queue("fra.1"), info)
        self.assertEqual(report["days_without_article_fixture_evidence"],
                         ["2026-10-17"])
        self.assertIn("NIE potwierdzono 0 spotkań", render(report))
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_mismatched_source_scope_fails(self):
        s = source()
        s["days"] = ["2026-10-18"]
        with self.assertRaises(ValueError):
            compare(queue(), s)


if __name__ == "__main__":
    unittest.main()
