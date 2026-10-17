import io
import json
import unittest
from datetime import datetime, timezone

from tools.kb21_official_fpl import (
    BASE, TEAM_ENDPOINT, FIXTURE_ENDPOINT,
    _get_json, convert, fetch, render,
)


def bootstrap():
    return {"teams": [{"id": i, "name": f"Official Team {i}"} for i in range(1, 21)]}


def game(i, home=1, away=2, kickoff="2026-10-17T11:30:00Z", provisional=False):
    return {"id": i, "team_h": home, "team_a": away, "kickoff_time": kickoff,
            "event": 7, "started": False, "finished": False,
            "provisional_start_time": provisional}


def make():
    fixtures = [game(i, home=(i%20)+1, away=((i+1)%20)+1,
                     kickoff="2026-08-30T11:30:00Z") for i in range(1, 381)]
    fixtures[6] = game(7, kickoff="2026-10-17T11:30:00Z")
    fixtures[7] = game(8, kickoff="2026-10-18T13:00:00Z")
    fixtures[8] = game(9, kickoff="2026-10-19T19:00:00Z")
    return fixtures


class FakeResponse(io.BytesIO):
    status = 200


class OfficialFplTests(unittest.TestCase):
    def test_full_380_match_catalogue_and_three_warsaw_days(self):
        data = convert(bootstrap(), make(), ["2026-10-17", "2026-10-18", "2026-10-19"],
                       captured_at=datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc))
        self.assertTrue(data["season_full_380_catalogue"])
        self.assertEqual(data["season_fixture_count"], 380)
        self.assertEqual(data["season_team_count"], 20)
        self.assertEqual([len(f) for f in data["by_day"].values()], [1, 1, 1])
        self.assertEqual(data["by_day"]["2026-10-17"][0]["fixture_id"], 7)
        self.assertEqual(data["by_day"]["2026-10-17"][0]["kickoff_warsaw"],
                         "2026-10-17T13:30:00+02:00")
        self.assertEqual(data["calendar_gate"], "BLOCKED")
        self.assertFalse(data["full_calendar_verified"])
        self.assertFalse(data["reviewer_signed"])
        self.assertIn("NO PLAY", render(data))

    def test_missing_kickoff_fails_catalogue_completeness(self):
        fixtures = make()
        fixtures[15]["kickoff_time"] = None
        report = convert(bootstrap(), fixtures, ["2026-10-17"])
        self.assertFalse(report["season_full_380_catalogue"])
        self.assertEqual(report["fixtures_missing_kickoff_count"], 1)
        self.assertFalse(report["full_calendar_verified"])

    def test_provisional_fixture_remains_visible_but_not_full_catalogue(self):
        fixtures = make()
        fixtures[6]["provisional_start_time"] = True
        report = convert(bootstrap(), fixtures, ["2026-10-17"])
        self.assertTrue(report["by_day"]["2026-10-17"][0]["kickoff_provisional"])
        self.assertFalse(report["season_full_380_catalogue"])

    def test_team_and_fixture_identity_validation(self):
        fixtures = make()
        fixtures[0]["team_h"] = 120
        with self.assertRaises(ValueError):
            convert(bootstrap(), fixtures, ["2026-10-17"])
        fixtures = make()
        fixtures[1]["id"] = fixtures[0]["id"]
        with self.assertRaises(ValueError):
            convert(bootstrap(), fixtures, ["2026-10-17"])
        teams = bootstrap()
        teams["teams"][0]["id"] = 2
        with self.assertRaises(ValueError):
            convert(teams, make(), ["2026-10-17"])

    def test_reject_naive_capture_and_bad_date_scope(self):
        with self.assertRaises(ValueError):
            convert(bootstrap(), make(), ["2026-10-17"],
                    captured_at=datetime(2026, 10, 17))
        with self.assertRaises(ValueError):
            convert(bootstrap(), make(), ["2026-10-17", "2026-10-17"])

    def test_public_official_json_only_fixed_vetted_paths(self):
        def opener(req, timeout):
            if req.full_url == TEAM_ENDPOINT:
                return FakeResponse(json.dumps(bootstrap()).encode("utf-8"))
            if req.full_url == FIXTURE_ENDPOINT:
                return FakeResponse(json.dumps(make()).encode("utf-8"))
            raise AssertionError("Unexpected endpoint")
        data = fetch(["2026-10-17", "2026-10-18"], opener=opener,
                     captured_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
        self.assertEqual(len(data["by_day"]), 2)
        self.assertTrue(data["season_full_380_catalogue"])
        with self.assertRaises(ValueError):
            _get_json(BASE + "other/", opener)


if __name__ == "__main__":
    unittest.main()
