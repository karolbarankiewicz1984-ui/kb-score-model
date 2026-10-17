import unittest
from tools.kb21_dfl_compare import compare, render


def queue():
    return {"days": ["2026-10-17", "2026-10-18"],
            "fixtures": [
                {"fixture_id": "ger.1:100", "fixture": "Hamburg SV - VfB Stuttgart",
                 "kickoff": "2026-10-17T15:30:00+02:00",
                 "date_warsaw": "2026-10-17"},
                {"fixture_id": "ger.1:200", "fixture": "Bayern Munich - RB Leipzig",
                 "kickoff": "2026-10-17T18:30:00+02:00",
                 "date_warsaw": "2026-10-17"},
                {"fixture_id": "ger.1:300", "fixture": "Leverkusen - Freiburg",
                 "kickoff": "2026-10-18T15:30:00+02:00",
                 "date_warsaw": "2026-10-18"},
                {"fixture_id": "eng.1:999", "fixture": "Everton - Chelsea",
                 "kickoff": "2026-10-17T13:30:00+02:00",
                 "date_warsaw": "2026-10-17"},
            ]}


def dfl():
    def game(h, a, kickoff):
        return {"home": h, "away": a, "kickoff_utc": kickoff,
                "kickoff_warsaw": kickoff, "matchday": 6}
    return {"schema": "kb21-official-bundesliga-media-v1",
            "league_id": "ger.1",
            "official_url": "https://products.bundesliga.com/fixtures",
            "status": "OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW",
            "days": ["2026-10-17", "2026-10-18"],
            "by_day": {
                "2026-10-17": [
                    game("Hamburger SV", "VfB Stuttgart", "2026-10-17T13:30:00Z"),
                    game("FC Bayern München", "RB Leipzig", "2026-10-17T16:30:00Z"),
                ],
                "2026-10-18": [
                    game("Bayer 04 Leverkusen", "Sport-Club Freiburg",
                         "2026-10-18T13:30:00Z"),
                ],
            }}


class DflCompareTests(unittest.TestCase):
    def test_organizer_names_kickoff_and_utc_aliases_match(self):
        r = compare(queue(), dfl())
        self.assertEqual(r["days"]["2026-10-17"]["matched"], 2)
        self.assertEqual(r["days"]["2026-10-18"]["matched"], 1)
        self.assertEqual(r["calendar_gate"], "BLOCKED")
        self.assertFalse(r["full_day_coverage_verified"])
        self.assertIn("NO PLAY", render(r))

    def test_dfl_missing_matchday_is_not_false_complete(self):
        q, source = queue(), dfl()
        source["by_day"]["2026-10-18"] = []
        r = compare(q, source)["days"]["2026-10-18"]
        self.assertEqual(r["comparisons"][0]["status"],
                         "NOT_ON_EXTRACTED_DFL_MATCHDAY")
        self.assertEqual(r["matched"], 0)
        self.assertFalse(r["organizer_full_day_verified"])

    def test_dfl_kickoff_difference_never_matches(self):
        q, source = queue(), dfl()
        source["by_day"]["2026-10-17"][0]["kickoff_utc"] = "2026-10-17T13:50:00Z"
        r = compare(q, source)["days"]["2026-10-17"]
        self.assertEqual(r["comparisons"][0]["status"], "KICKOFF_DISAGREEMENT")
        self.assertEqual(r["matched"], 1)

    def test_extra_official_match_reported(self):
        q, source = queue(), dfl()
        q["fixtures"] = [x for x in q["fixtures"] if x["fixture_id"] != "ger.1:100"]
        r = compare(q, source)["days"]["2026-10-17"]
        self.assertEqual(r["statuses"]["DFL_ONLY"], 1)
        self.assertEqual(r["dfl_only"][0]["home"], "Hamburger SV")

    def test_wrong_source_dates_rejected(self):
        source = dfl()
        source["days"] = ["2026-10-18"]
        with self.assertRaises(ValueError):
            compare(queue(), source)


if __name__ == "__main__":
    unittest.main()
