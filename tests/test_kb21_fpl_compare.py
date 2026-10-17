import copy
import unittest
from tools.kb21_fpl_compare import compare, render


def queue():
    return {"days": ["2026-10-17", "2026-10-18"],
            "calendar_gate": "BLOCKED",
            "fixtures": [
                {"fixture_id": "eng.1:7", "fixture": "Man City - Ipswich Town",
                 "kickoff": "2026-10-17T16:00:00+02:00",
                 "date_warsaw": "2026-10-17"},
                {"fixture_id": "eng.1:8", "fixture": "Everton - Chelsea",
                 "kickoff": "2026-10-17T13:30:00+02:00",
                 "date_warsaw": "2026-10-17"},
                {"fixture_id": "eng.1:9", "fixture": "Bournemouth - Sunderland",
                 "kickoff": "2026-10-18T15:00:00+02:00",
                 "date_warsaw": "2026-10-18"},
                {"fixture_id": "tur.1:10", "fixture": "Galatasaray - Besiktas",
                 "kickoff": "2026-10-17T17:00:00+02:00",
                 "date_warsaw": "2026-10-17"},
            ]}


def fpl():
    def item(id, h, a, time, day):
        return {"fixture_id": id, "league_id": "eng.1",
                "home": h, "away": a, "kickoff_utc": time,
                "kickoff_warsaw": time, "date_warsaw": day,
                "home_team_id": id, "away_team_id": id+1,
                "started": False, "finished": False, "kickoff_provisional": False}
    return {"schema": "kb21-official-premier-league-fpl-v1",
            "league_id": "eng.1",
            "days": ["2026-10-17", "2026-10-18"],
            "captured_at_utc": "2026-10-17T09:00:00+00:00",
            "season_full_380_catalogue": True,
            "by_day": {
                "2026-10-17": [
                    item(21, "Manchester City", "Ipswich Town",
                         "2026-10-17T14:00:00+00:00", "2026-10-17"),
                    item(22, "Everton", "Chelsea",
                         "2026-10-17T11:30:00+00:00", "2026-10-17"),
                ],
                "2026-10-18": [
                    item(23, "Bournemouth", "Sunderland",
                         "2026-10-18T13:00:00+00:00", "2026-10-18"),
                ],
            }}


class FplCompareTests(unittest.TestCase):
    def test_matching_teams_alias_and_kickoff_with_other_league_ignored(self):
        q, o = queue(), fpl()
        old = copy.deepcopy(q)
        report = compare(q, o)
        self.assertEqual(report["days"]["2026-10-17"]["identical_club_and_kickoff_count"], 2)
        self.assertEqual(report["days"]["2026-10-18"]["identical_club_and_kickoff_count"], 1)
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertFalse(report["full_organizer_day_signed"])
        self.assertEqual(report["publication"], "DIAGNOSTIC / NO PLAY")
        self.assertEqual(q, old)
        self.assertIn("NO PLAY", render(report))

    def test_detects_time_conflict_but_does_not_modify_esports(self):
        q, o = queue(), fpl()
        o["by_day"]["2026-10-17"][1]["kickoff_utc"] = "2026-10-17T12:00:00Z"
        record = compare(q, o)["days"]["2026-10-17"]
        issue = next(x for x in record["comparisons"] if x["espn_fixture_id"] == "eng.1:8")
        self.assertEqual(issue["status"], "KICKOFF_DISAGREEMENT")
        self.assertEqual(record["identical_club_and_kickoff_count"], 1)
        self.assertEqual(record["calendar_gate"], "BLOCKED")

    def test_detects_fpl_only_match_missing_in_esports(self):
        q, o = queue(), fpl()
        q["fixtures"] = [x for x in q["fixtures"] if x["fixture_id"] != "eng.1:8"]
        record = compare(q, o)["days"]["2026-10-17"]
        self.assertEqual(len(record["official_only"]), 1)
        self.assertEqual(record["statuses"]["FPL_ONLY"], 1)
        self.assertEqual(record["official_only"][0]["fpl_fixture_id"], 22)

    def test_same_names_wrong_league_and_duplicate_esports_rejected(self):
        q, o = queue(), fpl()
        q["fixtures"].append(copy.deepcopy(q["fixtures"][0]))
        record = compare(q, o)["days"]["2026-10-17"]
        self.assertEqual(record["statuses"]["AMBIGUOUS_DUPLICATE_ESPN_FIXTURE"], 1)
        self.assertEqual(record["identical_club_and_kickoff_count"], 1)
        self.assertEqual(record["espn_fixture_count"], 3)

    def test_missing_fpl_day_fails_closed(self):
        q, o = queue(), fpl()
        o["by_day"].pop("2026-10-18")
        with self.assertRaises(ValueError):
            compare(q, o)
        o = fpl()
        o["days"] = ["2026-10-17"]
        with self.assertRaises(ValueError):
            compare(q, o)

    def test_provisional_kickoff_never_matches_as_confirmed(self):
        q, o = queue(), fpl()
        o["by_day"]["2026-10-18"][0]["kickoff_provisional"] = True
        record = compare(q, o)["days"]["2026-10-18"]
        self.assertEqual(record["comparisons"][0]["status"],
                         "ORGANIZER_KICKOFF_PROVISIONAL")
        self.assertEqual(record["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
