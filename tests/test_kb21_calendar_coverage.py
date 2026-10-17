import unittest
from tools.kb21_calendar_coverage import summarize, render


def fixture(league, status):
    return {"fixture_id": f"{league}:11", "date_warsaw": "2026-10-17",
            "independent_crosscheck": {"status": status}}


def queue():
    return {"days": ["2026-10-17"],
            "source_status": {"2026-10-17": [
                {"league": "eng.1", "status": "OK", "events": 1},
                {"league": "esp.1", "status": "OK", "events": 0}
            ]},
            "fixtures": [fixture("eng.1", "MATCHED_FOR_REVIEW")]}


def snapshot():
    return {"provider": "football-data.org", "date": "2026-10-17",
            "requested_competitions": ["PL", "PD"],
            "fixtures": [{"competition_code": "PL", "provider_match_id": 33}]}


class CalendarCoverageTests(unittest.TestCase):
    def test_matching_providers_never_clear_official_calendar_gate(self):
        result = summarize(queue(), {"2026-10-17": snapshot()})
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertFalse(result["official_organizer_verified"])
        core = result["days"]["2026-10-17"]["core_leagues"]
        premier = next(x for x in core if x["league_id"] == "eng.1")
        self.assertEqual(premier["status"], "TWO_PROVIDER_CANDIDATE_AGREEMENT_REVIEW")
        self.assertFalse(premier["full_coverage_verified"])
        self.assertIn("CALENDAR GATE BLOCKED", render(result))

    def test_both_providers_empty_is_not_proof_no_games(self):
        result = summarize(queue(), {"2026-10-17": snapshot()})
        laliga = next(x for x in result["days"]["2026-10-17"]["core_leagues"]
                      if x["league_id"] == "esp.1")
        self.assertEqual(laliga["status"], "BOTH_PROVIDERS_EMPTY_OFFICIAL_REVIEW_NEEDED")

    def test_missing_provider_scope_not_reported_as_missing_fixture(self):
        snap = snapshot()
        snap["requested_competitions"] = ["PL"]
        result = summarize(queue(), {"2026-10-17": snap})
        laliga = next(x for x in result["days"]["2026-10-17"]["core_leagues"]
                      if x["league_id"] == "esp.1")
        self.assertEqual(laliga["status"], "SECOND_PROVIDER_OUT_OF_SCOPE")
        self.assertIsNone(laliga["independent_provider_candidates"])

    def test_source_error_is_clearly_visible(self):
        q = queue()
        q["source_status"]["2026-10-17"][0]["status"] = "ERROR"
        result = summarize(q, {"2026-10-17": snapshot()})
        premier = result["days"]["2026-10-17"]["core_leagues"][0]
        self.assertEqual(premier["status"], "ESPN_SOURCE_ERROR")

    def test_missing_source_snapshot_requires_review(self):
        result = summarize(queue(), {})
        self.assertFalse(result["days"]["2026-10-17"]["independent_provider_available"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
