import unittest

from tools.kb21_fixture_crosscheck import crosscheck


def queue_fixture(name="Everton - Chelsea", kick="2026-10-17T13:30:00+02:00",
                  league="eng.1", event_id="100"):
    return {"fixture_id": f"{league}:{event_id}", "fixture": name,
            "date_warsaw": "2026-10-17", "kickoff": kick,
            "calendar_gate": "BLOCKED",
            "publication": "DIAGNOSTIC / NO PLAY",
            "assessment": {"p_model": None, "str": None, "qual": None, "match": None}}


def snapshot():
    return {"date": "2026-10-17", "provider": "football-data.org",
            "requested_competitions": ["PL"],
            "fixtures": [{"provider_match_id": 333, "competition_code": "PL",
                          "home_team": "Everton FC", "away_team": "Chelsea FC",
                          "kickoff_utc": "2026-10-17T11:30:00Z"}]}


class CrosscheckTests(unittest.TestCase):
    def test_source_match_is_still_blocked(self):
        q = {"days": ["2026-10-17"], "fixtures": [queue_fixture()]}
        result = crosscheck(q, {"2026-10-17": snapshot()})
        check = result["fixtures"][0]["independent_crosscheck"]
        self.assertEqual(check["status"], "MATCHED_FOR_REVIEW")
        self.assertEqual(check["provider_match_id"], 333)
        self.assertFalse(check["official_verified"])
        self.assertFalse(check["freeze_allowed"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIsNone(result["fixtures"][0]["assessment"]["p_model"])

    def test_wrong_kickoff_is_not_match(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            queue_fixture(kick="2026-10-17T14:30:00+02:00")
        ]}
        result = crosscheck(q, {"2026-10-17": snapshot()})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"], "NO_NAME_TIME_MATCH")

    def test_wrong_league_not_match_even_with_same_teams(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            queue_fixture(league="esp.1")
        ]}
        result = crosscheck(q, {"2026-10-17": snapshot()})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"],
                         "OUTSIDE_PROVIDER_SNAPSHOT_SCOPE")

    def test_no_snapshot_and_unsupported_league_are_not_calendar_failures(self):
        q = {"days": ["2026-10-17", "2026-10-18"], "fixtures": [
            queue_fixture(league="tur.1"), queue_fixture(event_id="200")
        ]}
        result = crosscheck(q, {})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"],
                         "UNSUPPORTED_PROVIDER_LEAGUE_MAPPING")
        self.assertEqual(result["fixtures"][1]["independent_crosscheck"]["status"],
                         "NO_INDEPENDENT_SNAPSHOT")
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_duplicate_provider_match_is_ambiguous(self):
        q = {"days": ["2026-10-17"], "fixtures": [
            queue_fixture(event_id="100"), queue_fixture(event_id="200")
        ]}
        result = crosscheck(q, {"2026-10-17": snapshot()})
        statuses = [f["independent_crosscheck"]["status"] for f in result["fixtures"]]
        self.assertEqual(statuses, ["AMBIGUOUS_MATCH", "AMBIGUOUS_MATCH"])
        self.assertEqual(result["crosscheck_summary"]["2026-10-17"]["statuses"]["AMBIGUOUS_MATCH"], 2)

    def test_bad_provider_or_date_never_matches(self):
        q = {"days": ["2026-10-17"], "fixtures": [queue_fixture()]}
        wrong = snapshot()
        wrong["date"] = "2026-10-18"
        result = crosscheck(q, {"2026-10-17": wrong})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"],
                         "INVALID_OR_MISMATCHED_INDEPENDENT_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
