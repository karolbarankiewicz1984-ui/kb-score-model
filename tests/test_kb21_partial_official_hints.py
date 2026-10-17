"""The six weak official sources must remain notes, not signed fixtures."""
import copy
import unittest

from tools.kb21_partial_official_hints import attach
from tools.kb21_official_uefa_articles import SOURCES as UEFA
from tools.kb21_official_belgium import SOURCE as BELGIUM
from tools.kb21_official_uefa_qualifiers_cycle import SOURCE as QUALIFIERS, EDITION
from tools.kb21_official_review import OFFICIAL_PAGES

DAYS = ["2026-10-18", "2026-10-19"]
CAPTURE = "2026-10-17T14:00:00+00:00"


def draft():
    return {
        "days": {day: {code: {
            "organizer_url": url, "captured_at": None,
            "reviewer": None, "full_day_checked": False,
            "confirmed_zero_matches": None, "fixtures": []
        } for code, url in OFFICIAL_PAGES.items()} for day in DAYS},
        "daily_approvals": {day: None for day in DAYS},
        "approval": None,
    }


def uefa(code="uefa.nations", include=True):
    return {
        "schema": "kb21-official-uefa-league-phase-v1",
        "league_id": code, "official_url": UEFA[code],
        "days": DAYS, "captured_at_utc": CAPTURE,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "kickoff_timezone_verified": False, "full_calendar_verified": False,
        "status": "OFFICIAL_LEAGUE_PHASE_ARTICLE_PARTIAL_FOR_REVIEW",
        "errors": [], "by_day": {DAYS[0]: [{
            "league_id": code, "home": "Poland", "away": "Sweden",
            "date_printed": DAYS[0], "printed_kickoff": "20:45",
            "kickoff_timezone_verified": False,
        }] if include else [], DAYS[1]: []},
    }


def belgium():
    return {
        "schema": "kb21-official-belgium-selected-round-v1",
        "league_id": "bel.1", "official_url": BELGIUM,
        "days": DAYS, "captured_at_utc": CAPTURE,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "kickoff_timezone_verified": False, "full_calendar_verified": False,
        "date_verified": False,
        "status": "OFFICIAL_SELECTED_ROUND_UNDATED_FOR_REVIEW",
        "errors": [], "by_day": {day: [] for day in DAYS},
        "undated_fixtures": [{
            "home": "Ghent", "away": "Antwerp", "selected_round": 9,
            "date_warsaw": None, "kickoff_warsaw": None
        }],
    }


def qualifiers():
    return {
        "schema": "kb21-official-uefa-2026-qualifiers-cycle-v1",
        "league_id": "fifa.worldq.uefa",
        "edition": EDITION, "official_url": QUALIFIERS,
        "days": DAYS, "captured_at_utc": CAPTURE,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "kickoff_timezone_verified": False, "full_calendar_verified": False,
        "date_verified": False, "confirmed_zero_matches": False,
        "status": "DOCUMENTED_HISTORICAL_CYCLE_ONLY", "errors": [],
        "by_day": {day: [] for day in DAYS},
        "day_cycle_status": {day:
            "AFTER_DOCUMENTED_WORLD_CUP_2026_QUALIFICATION_CYCLE"
            for day in DAYS},
        "documented_last_playoff_day": "2026-03-31",
    }


class PartialEvidenceTests(unittest.TestCase):
    def test_six_sources_add_hints_not_fixtures_or_approval(self):
        original = draft()
        preserved = copy.deepcopy(original)
        sources = {code: uefa(code, include=(code == "uefa.nations"))
                   for code in UEFA}
        sources["bel.1"] = belgium()
        sources["fifa.worldq.uefa"] = qualifiers()
        result = attach(original, sources)
        self.assertEqual(original, preserved)
        self.assertEqual(result["partial_official_hints_summary"]["sources_attached"], 6)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIsNone(result["approval"])
        self.assertTrue(all(value is None for value in result["daily_approvals"].values()))
        for day in DAYS:
            for code, entry in result["days"][day].items():
                self.assertEqual(entry["fixtures"], [])
                self.assertFalse(entry["full_day_checked"])
                self.assertIsNone(entry["captured_at"])
                self.assertIsNone(entry["reviewer"])
                self.assertIsNone(entry["confirmed_zero_matches"])
        nations = result["days"][DAYS[0]]["uefa.nations"]["partial_official_source_hints"]
        self.assertEqual(nations["fixture_hints"][0]["home"], "Poland")
        self.assertFalse(nations["fixture_hints"][0]["clock_verified"])
        self.assertFalse(nations["organizer_full_day_attested"])
        belg = result["days"][DAYS[1]]["bel.1"]["partial_official_source_hints"]
        self.assertIsNone(belg["fixture_hints"][0]["date_warsaw"])
        self.assertFalse(belg["confirmed_no_matches"])
        qual = result["days"][DAYS[0]]["fifa.worldq.uefa"]["partial_official_source_hints"]
        self.assertFalse(qual["fixture_hints"][0]["zero_games_certified"])

    def test_no_uefa_fixture_on_selected_day_never_certifies_zero(self):
        result = attach(draft(), {"uefa.europa": uefa("uefa.europa", False)})
        day = result["days"][DAYS[0]]["uefa.europa"]
        self.assertEqual(day["partial_official_source_hints"]["fixture_hints"], [])
        self.assertIsNone(day["confirmed_zero_matches"])
        self.assertFalse(day["full_day_checked"])

    def test_existing_research_fixtures_preserved(self):
        x = draft()
        x["days"][DAYS[0]]["uefa.nations"]["fixtures"] = [
            {"home": "Other Club", "away": "Rival",
             "kickoff": "2026-10-18T12:00:00+02:00"}]
        result = attach(x, {"uefa.nations": uefa()})
        self.assertEqual(result["days"][DAYS[0]]["uefa.nations"]["fixtures"],
                         x["days"][DAYS[0]]["uefa.nations"]["fixtures"])

    def test_bad_source_scope_clock_or_organizer_url_rejected(self):
        source = uefa()
        source["days"] = [DAYS[0]]
        with self.assertRaisesRegex(ValueError, "scope invalid"):
            attach(draft(), {"uefa.nations": source})
        source = uefa()
        source["by_day"][DAYS[0]][0]["kickoff_timezone_verified"] = True
        with self.assertRaisesRegex(ValueError, "Unsafe UEFA"):
            attach(draft(), {"uefa.nations": source})
        source = uefa()
        source["official_url"] = "https://example.org/fake"
        with self.assertRaisesRegex(ValueError, "scope invalid"):
            attach(draft(), {"uefa.nations": source})

    def test_no_signed_or_preverified_review(self):
        x = draft()
        x["daily_approvals"][DAYS[0]] = {"reviewer": "person"}
        with self.assertRaisesRegex(ValueError, "signed daily"):
            attach(x, {"uefa.nations": uefa()})
        x = draft()
        x["days"][DAYS[1]]["bel.1"]["full_day_checked"] = True
        with self.assertRaisesRegex(ValueError, "reviewed slot"):
            attach(x, {"bel.1": belgium()})

    def test_belgian_source_with_invented_dates_is_rejected(self):
        source = belgium()
        source["undated_fixtures"][0]["date_warsaw"] = DAYS[0]
        with self.assertRaisesRegex(ValueError, "not dated"):
            attach(draft(), {"bel.1": source})

    def test_qualifiers_cycle_cannot_certify_zero(self):
        source = qualifiers()
        source["confirmed_zero_matches"] = True
        with self.assertRaisesRegex(ValueError, "cannot attest"):
            attach(draft(), {"fifa.worldq.uefa": source})


if __name__ == "__main__":
    unittest.main()
