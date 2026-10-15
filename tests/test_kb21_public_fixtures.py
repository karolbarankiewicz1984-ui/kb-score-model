import unittest
from tools.kb21_public_fixtures import parse_events


class PublicFixtureTests(unittest.TestCase):
    def test_extracts_home_away_and_kickoff(self):
        payload = {"leagues": [{"name": "Test League"}], "events": [{"id": "123", "date": "2026-10-16T17:00Z",
            "competitions": [{"competitors": [
                {"homeAway": "away", "team": {"displayName": "Visitors"}},
                {"homeAway": "home", "team": {"displayName": "Hosts"}}]}]}]}
        events = parse_events(payload, "eng.1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["home"], "Hosts")
        self.assertEqual(events[0]["away"], "Visitors")
        self.assertEqual(events[0]["kickoff"], "2026-10-16T17:00Z")

    def test_skips_incomplete_fixture(self):
        self.assertEqual(parse_events({"events": [{"date": "2026-10-16T17:00Z", "competitions": []}]}, "eng.1"), [])


if __name__ == "__main__":
    unittest.main()
