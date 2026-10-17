import copy
import unittest

from tools.kb21_official_inventory_prefill import prefill


def make():
    template = {"days": {"2026-10-18": {
        "eng.1": {"organizer_url": "https://premierleague.com", "captured_at": None,
                  "reviewer": None, "full_day_checked": False, "fixtures": [],
                  "confirmed_zero_matches": None},
        "por.1": {"organizer_url": "https://ligaportugal.pt", "captured_at": None,
                  "reviewer": None, "full_day_checked": False, "fixtures": [],
                  "confirmed_zero_matches": None}
    }}, "approval": None}
    research = {"schema": "kb21-official-research-v1",
                "status": "OFFICIAL_WEB_RESEARCH_UNSIGNED",
                "date_scope": ["2026-10-18"],
                "days": {"2026-10-18": {
                    "eng.1": {
                        "source_kind": "OFFICIAL_ORGANIZER_PAGE_WEB_RESEARCH",
                        "official_source_url": "https://premierleague.com",
                        "full_round_source_found": True,
                        "official_fixture_list_extracted": True,
                        "fixtures": [{"home": "Club A", "away": "Club B",
                                      "kickoff": "2026-10-18T15:00:00+02:00"}]
                    },
                    "por.1": {
                        "source_kind": "OFFICIAL_CLUB_MATCH_PAGE_PARTIAL",
                        "official_source_url": "https://gilvicentefc.pt",
                        "full_round_source_found": False,
                        "official_fixture_list_extracted": False,
                        "fixtures": [],
                    }
                }}}
    return template, research


class InventoryPrefillTests(unittest.TestCase):
    def test_research_prefills_but_never_certifies_or_signs(self):
        t, r = make()
        original = copy.deepcopy(t)
        result = prefill(t, r)
        self.assertEqual(t, original)
        self.assertEqual(result["research_fixtures_prefilled"], 1)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIsNone(result["approval"])
        day = result["days"]["2026-10-18"]
        self.assertEqual(len(day["eng.1"]["fixtures"]), 1)
        self.assertFalse(day["eng.1"]["full_day_checked"])
        self.assertIsNone(day["eng.1"]["captured_at"])
        self.assertIsNone(day["por.1"]["confirmed_zero_matches"])
        self.assertFalse(day["por.1"]["research_full_round_source_found"])
        self.assertEqual(day["por.1"]["organizer_url"], "https://ligaportugal.pt")

    def test_signed_inputs_rejected(self):
        t, r = make()
        t["approval"] = {"reviewer": "Someone"}
        with self.assertRaises(ValueError):
            prefill(t, r)
        t["approval"] = None
        t["days"]["2026-10-18"]["eng.1"]["reviewer"] = "Someone"
        with self.assertRaises(ValueError):
            prefill(t, r)

    def test_stale_date_scope_rejected(self):
        t, r = make()
        r["date_scope"] = ["2026-10-19"]
        with self.assertRaises(ValueError):
            prefill(t, r)


if __name__ == "__main__":
    unittest.main()
