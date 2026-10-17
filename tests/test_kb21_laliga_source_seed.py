import unittest
from tools.kb21_official_source_seed import seed


def source():
    return {"schema": "kb21-official-laliga-matchday-html-v1",
            "league_id": "esp.1", "days": ["2026-10-17", "2026-10-18"],
            "status": "OFFICIAL_PARTIAL_MATCHDAY_WINDOW_FOR_REVIEW",
            "captured_at_utc": "2026-10-17T09:00:00+00:00", "errors": [{"reason": "one missing page"}],
            "by_day": {"2026-10-17": [{"home": "Real Betis", "away": "FC Barcelona",
                "kickoff_warsaw": "2026-10-17T18:30:00+02:00",
                "official_url": "https://www.laliga.com/laliga-easports/resultados/2026-27/jornada-9"}],
                "2026-10-18": []}}


def draft():
    def row():
        return {"fixtures": [], "captured_at": None, "reviewer": None, "full_day_checked": False,
                "confirmed_zero_matches": None}
    return {"days": {"2026-10-17": {"esp.1": row()}, "2026-10-18": {"esp.1": row()}},
            "approval": None}


class LaLigaSeedTests(unittest.TestCase):
    def test_positive_day_only_prefill_and_unsigned_state(self):
        report = seed(draft(), {"esp.1": source()})
        row = report["days"]["2026-10-17"]["esp.1"]
        self.assertEqual(row["fixtures"][0]["home"], "Real Betis")
        self.assertEqual(row["organizer_source_catalogue_kind"], "PARTIAL_LALIGA_ROUND_WINDOW")
        self.assertEqual(row["organizer_source_fetch_issues"], 1)
        self.assertFalse(row["full_day_checked"])
        self.assertIsNone(row["reviewer"])
        self.assertIsNone(report["approval"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        blank = report["days"]["2026-10-18"]["esp.1"]
        self.assertEqual(blank["fixtures"], [])
        self.assertIsNone(blank["confirmed_zero_matches"])
        self.assertNotIn("organizer_facts_source", blank)

    def test_conflicting_existing_research_is_not_overwritten(self):
        review = draft()
        review["days"]["2026-10-17"]["esp.1"]["fixtures"] = [{
            "home": "Real Betis", "away": "Barcelona", "kickoff": "2026-10-17T18:00:00+02:00"}]
        report = seed(review, {"esp.1": source()})
        row = report["days"]["2026-10-17"]["esp.1"]
        self.assertEqual(row["fixtures"][0]["kickoff"], "2026-10-17T18:00:00+02:00")
        self.assertGreater(report["organizer_live_seed_summary"]["discrepancies_against_existing_research"]["esp.1"], 0)

    def test_wrong_schema_never_prefilled(self):
        official = source()
        official["schema"] = "untrusted"
        with self.assertRaises(ValueError):
            seed(draft(), {"esp.1": official})
