import unittest
from tools.kb21_official_source_seed import seed


def draft():
    return {
        "days": {day: {
            "tur.1": {"fixtures": [], "reviewer": None,
                      "captured_at": None, "full_day_checked": False,
                      "confirmed_zero_matches": None}}
            for day in ("2026-10-17", "2026-10-18")},
        "approval": None,
    }


def source():
    return {
        "schema": "kb21-official-tff-superlig-v1", "league_id": "tur.1",
        "days": ["2026-10-17", "2026-10-18"],
        "status": "OFFICIAL_TFF_MATCHWEEK_PARTIAL_FOR_REVIEW",
        "errors": [], "unconfirmed_zero_dates": ["2026-10-18"],
        "official_url": "https://www.tff.org/?pageID=198",
        "captured_at_utc": "2026-10-17T11:00:00+00:00",
        "by_day": {
            "2026-10-17": [{
                "home": "GENÇLERBİRLİĞİ", "away": "GALATASARAY A.Ş.",
                "kickoff_warsaw": "2026-10-17T15:00:00+02:00",
            }],
            "2026-10-18": [],
        },
    }


class TFFSeedTests(unittest.TestCase):
    def test_facts_only_never_review_or_no_game_claim(self):
        report = seed(draft(), {"tur.1": source()})
        row = report["days"]["2026-10-17"]["tur.1"]
        self.assertEqual(row["fixtures"][0]["home"], "GENÇLERBİRLİĞİ")
        self.assertEqual(row["organizer_source_catalogue_kind"],
                         "TFF_VISIBLE_MATCHWEEK_PARTIAL")
        self.assertTrue(row["organizer_source_not_full_day"])
        self.assertFalse(row["full_day_checked"])
        self.assertIsNone(row["reviewer"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertIsNone(report["approval"])
        missing = report["days"]["2026-10-18"]["tur.1"]
        self.assertEqual(missing["fixtures"], [])
        self.assertIsNone(missing["confirmed_zero_matches"])

    def test_incomplete_page_cannot_prefill(self):
        data = source()
        data["status"] = "OFFICIAL_TFF_UNAVAILABLE_OR_INCOMPLETE"
        report = seed(draft(), {"tur.1": data})
        self.assertEqual(report["days"]["2026-10-17"]["tur.1"]["fixtures"], [])
        self.assertNotIn("tur.1", report["organizer_live_seed_summary"]["fixtures_prefilled"])


if __name__ == "__main__":
    unittest.main()
