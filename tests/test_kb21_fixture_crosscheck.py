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
        check = result["fixtures"][0]["independent_crosscheck"]
        self.assertEqual(check["status"], "START_TIME_CONFLICT")
        self.assertEqual(check["time_discrepancy"]["provider_match_id"], 333)
        self.assertIsNone(check["provider_match_id"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")

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

    def test_explicit_club_aliases_reconcile_genuine_same_match(self):
        pairs = [
            ("eng.1", "PL", "Fulham - Hull City", "Fulham FC", "Hull City AFC"),
            ("esp.1", "PD", "Espanyol - Atlético Madrid",
             "RCD Espanyol de Barcelona", "Club Atlético de Madrid"),
            ("ita.1", "SA", "Bologna - Internazionale",
             "Bologna FC 1909", "FC Internazionale Milano"),
            ("ger.1", "BL1", "Hamburg SV - VfB Stuttgart",
             "Hamburger SV", "VfB Stuttgart"),
            ("ned.1", "DED", "Sparta Rotterdam - Willem II",
             "Sparta Rotterdam", "Willem II Tilburg"),
            ("fra.1", "FL1", "Troyes - Lens",
             "ES Troyes AC", "Racing Club de Lens"),
        ]
        for idx, (league, code, label, home, away) in enumerate(pairs, 1):
            with self.subTest(league=league):
                fixture = queue_fixture(name=label, league=league,
                                        event_id=str(idx),
                                        kick="2026-10-17T20:45:00+02:00")
                external = {"date": "2026-10-17",
                            "provider": "football-data.org",
                            "requested_competitions": [code],
                            "fixtures": [{
                                "provider_match_id": idx, "competition_code": code,
                                "home_team": home, "away_team": away,
                                "kickoff_utc": "2026-10-17T18:45:00Z",
                            }]}
                res = crosscheck({"days": ["2026-10-17"], "fixtures": [fixture]},
                                 {"2026-10-17": external})
                check = res["fixtures"][0]["independent_crosscheck"]
                self.assertEqual(check["status"], "MATCHED_FOR_REVIEW")
                self.assertFalse(check["official_verified"])
                self.assertEqual(res["calendar_gate"], "BLOCKED")

    def test_betis_barcelona_actual_kickoff_conflict_retains_evidence(self):
        fixture = queue_fixture(name="Real Betis - Barcelona",
                                league="esp.1", event_id="401882846",
                                kick="2026-10-17T18:00:00+02:00")
        external = {
            "provider": "football-data.org", "date": "2026-10-17",
            "requested_competitions": ["PD"],
            "fixtures": [{
                "provider_match_id": 600012, "competition_code": "PD",
                "home_team": "Real Betis Balompié", "away_team": "FC Barcelona",
                "kickoff_utc": "2026-10-17T16:30:00Z",
            }],
        }
        result = crosscheck({"days": ["2026-10-17"], "fixtures": [fixture]},
                            {"2026-10-17": external})
        row = result["fixtures"][0]["independent_crosscheck"]
        self.assertEqual(row["status"], "START_TIME_CONFLICT")
        self.assertEqual(row["time_discrepancy"]["provider_match_id"], 600012)
        self.assertEqual(row["time_discrepancy"]["provider_kickoff_utc"],
                         "2026-10-17T16:30:00Z")
        self.assertIsNone(row["provider_match_id"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_same_clubs_in_wrong_provider_league_never_match(self):
        fixture = queue_fixture(name="Bologna - Internazionale",
                                league="ita.1", event_id="111",
                                kick="2026-10-17T18:00:00+02:00")
        external = {"provider": "football-data.org", "date": "2026-10-17",
                    "requested_competitions": ["SA"],
                    "fixtures": [{
                        "provider_match_id": 1, "competition_code": "PL",
                        "home_team": "Bologna FC 1909",
                        "away_team": "FC Internazionale Milano",
                        "kickoff_utc": "2026-10-17T16:00:00Z"
                    }]}
        result = crosscheck({"days": ["2026-10-17"], "fixtures": [fixture]},
                            {"2026-10-17": external})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"],
                         "NO_NAME_TIME_MATCH")

    def test_bad_provider_or_date_never_matches(self):
        q = {"days": ["2026-10-17"], "fixtures": [queue_fixture()]}
        wrong = snapshot()
        wrong["date"] = "2026-10-18"
        result = crosscheck(q, {"2026-10-17": wrong})
        self.assertEqual(result["fixtures"][0]["independent_crosscheck"]["status"],
                         "INVALID_OR_MISMATCHED_INDEPENDENT_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
