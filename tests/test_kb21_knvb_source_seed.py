import unittest
from tools.kb21_official_source_seed import seed

DAYS = ["2026-10-17", "2026-10-18"]


def draft():
    def entry():
        return {"fixtures": [], "reviewer": None, "captured_at": None,
                "full_day_checked": False, "confirmed_zero_matches": None}
    return {"days": {day: {"ned.1": entry()} for day in DAYS},
            "approval": None}


def knvb():
    return {
        "schema": "kb21-official-knvb-eredivisie-v1",
        "league_id": "ned.1", "days": DAYS,
        "status": "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW",
        "official_url": "https://www.knvb.nl/competities/eredivisie/programma",
        "captured_at_utc": "2026-10-17T09:00:00+00:00",
        "errors": [], "unconfirmed_zero_dates": ["2026-10-18"],
        "by_day": {
            DAYS[0]: [{
                "home": "ADO Den Haag", "away": "PSV",
                "kickoff_warsaw": "2026-10-17T16:30:00+02:00",
            }],
            DAYS[1]: [],
        },
    }


class KNVBSeedTests(unittest.TestCase):
    def test_positive_day_prefills_but_never_signs(self):
        report = seed(draft(), {"ned.1": knvb()})
        row = report["days"][DAYS[0]]["ned.1"]
        self.assertEqual(row["fixtures"][0]["home"], "ADO Den Haag")
        self.assertEqual(row["organizer_source_catalogue_kind"],
                         "KNVB_PUBLIC_PROGRAM_PARTIAL")
        self.assertTrue(row["organizer_source_not_full_day"])
        self.assertIsNone(row["reviewer"])
        self.assertFalse(row["full_day_checked"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertIsNone(report["approval"])
        empty = report["days"][DAYS[1]]["ned.1"]
        self.assertEqual(empty["fixtures"], [])
        self.assertIsNone(empty["confirmed_zero_matches"])

    def test_unreadable_source_does_not_prefill(self):
        bad = knvb()
        bad["status"] = "OFFICIAL_KNVB_UNAVAILABLE_OR_UNREADABLE"
        report = seed(draft(), {"ned.1": bad})
        self.assertEqual(report["days"][DAYS[0]]["ned.1"]["fixtures"], [])
        self.assertNotIn("ned.1", report["organizer_live_seed_summary"]["fixtures_prefilled"])

    def test_existing_disagreement_does_not_get_overwritten(self):
        review = draft()
        review["days"][DAYS[0]]["ned.1"]["fixtures"] = [{
            "home": "ADO Den Haag", "away": "PSV",
            "kickoff": "2026-10-17T17:30:00+02:00",
        }]
        report = seed(review, {"ned.1": knvb()})
        row = report["days"][DAYS[0]]["ned.1"]
        self.assertEqual(row["fixtures"][0]["kickoff"],
                         "2026-10-17T17:30:00+02:00")
        self.assertTrue(row["organizer_data_discrepancies"]["requires_manual_check"])


if __name__ == "__main__":
    unittest.main()
