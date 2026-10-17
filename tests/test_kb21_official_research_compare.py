import copy
import unittest

from tools.kb21_official_research_compare import compare, render, _team


def source(day, fixtures, league="esp.1"):
    return {"schema": "kb21-official-research-v1", "status": "OFFICIAL_WEB_RESEARCH_UNSIGNED",
            "days": {day: {league: {"competition": "La Liga",
                                   "official_source_url": "https://www.laliga.com/laliga-easports/resultados/2026-27/jornada-9",
                                   "source_reviewer_signed": False, "fixtures": fixtures}}}}


def fixture(home, away, kick):
    return {"home": home, "away": away, "kickoff": kick}


def candidate(home, away, kick, league="esp.1", match_id="123"):
    return {"fixture_id": f"{league}:{match_id}", "fixture": f"{home} - {away}",
            "kickoff": kick, "date_warsaw": "2026-10-17"}


class OfficialResearchCompareTests(unittest.TestCase):
    def test_exact_and_alias_matching_still_unapproved(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            candidate("Espanyol", "Atlético Madrid", "2026-10-17T12:00:00Z")
        ]}
        official = source("2026-10-17", [fixture(
            "RCD Espanyol", "Atlético de Madrid", "2026-10-17T14:00:00+02:00"
        )])
        r = compare(q, official)
        row = r["days"]["2026-10-17"][0]
        self.assertEqual(row["status"], "TWO_SOURCE_REVIEW_CANDIDATE")
        self.assertEqual(row["matched_count"], 1)
        self.assertEqual(r["calendar_gate"], "BLOCKED")
        self.assertFalse(r["organizer_authenticated"])
        self.assertFalse(row["official_full_card_signed"])
        self.assertIn("NO PLAY", render(r))

    def test_la_liga_betis_barcelona_time_conflict(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            candidate("Real Betis", "Barcelona", "2026-10-17T16:00:00Z")
        ]}
        official = source("2026-10-17", [fixture(
            "Real Betis", "FC Barcelona", "2026-10-17T18:30:00+02:00"
        )])
        row = compare(q, official)["days"]["2026-10-17"][0]
        self.assertEqual(row["fixtures"][0]["status"], "START_TIME_CONFLICT")
        self.assertEqual(row["matched_count"], 0)
        self.assertEqual(len(row["unmatched_espn"]), 1)

    def test_two_empty_sources_not_proof_of_no_match(self):
        result = compare({"days": ["2026-10-17"], "fixtures": []},
                         source("2026-10-17", []))
        self.assertEqual(result["days"]["2026-10-17"][0]["status"],
                         "BOTH_EMPTY_NOT_OFFICIALLY_CONFIRMED")
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_missing_espn_fixture_remains_explicit(self):
        q = {"days": ["2026-10-17"], "fixtures": []}
        official = source("2026-10-17", [fixture(
            "Real Betis", "FC Barcelona", "2026-10-17T18:30:00+02:00"
        )])
        row = compare(q, official)["days"]["2026-10-17"][0]
        self.assertEqual(row["fixtures"][0]["status"], "MISSING_FROM_ESPN")

    def test_duplicate_espn_match_does_not_count_as_two_matches(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            candidate("Espanyol", "Atlético Madrid", "2026-10-17T12:00:00Z", match_id="123"),
            candidate("Espanyol", "Atlético Madrid", "2026-10-17T12:00:00Z", match_id="124"),
        ]}
        official = source("2026-10-17", [fixture(
            "RCD Espanyol", "Atlético de Madrid", "2026-10-17T14:00:00+02:00"
        )])
        row = compare(q, official)["days"]["2026-10-17"][0]
        self.assertEqual(row["fixtures"][0]["status"], "AMBIGUOUS_ESPN_IDENTITY")
        self.assertEqual(row["matched_count"], 0)

    def test_rejected_misleading_signed_official_research(self):
        q = {"days": ["2026-10-17"], "fixtures": []}
        official = source("2026-10-17", [])
        official["days"]["2026-10-17"]["esp.1"]["source_reviewer_signed"] = True
        with self.assertRaises(ValueError):
            compare(q, official)

    def test_deutsche_aliases_are_explicit_and_league_specific(self):
        self.assertEqual(_team("ger.1", "Hamburger SV"), _team("ger.1", "Hamburg SV"))
        self.assertNotEqual(_team("ita.1", "Hamburger SV"), _team("ita.1", "Hamburg SV"))

    def test_warsaw_date_mismatch_detected(self):
        q = {"days": ["2026-10-17"], "fixtures": []}
        official = source("2026-10-17", [fixture(
            "Real Betis", "FC Barcelona", "2026-10-18T18:30:00+02:00"
        )])
        row = compare(q, official)["days"]["2026-10-17"][0]
        self.assertEqual(row["fixtures"][0]["status"], "OFFICIAL_RESEARCH_DATE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
