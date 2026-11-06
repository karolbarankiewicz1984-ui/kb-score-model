import unittest
from github_models.event_parser import parse_events
from github_models.event_markets import poisson_over, run

class MarketTests(unittest.TestCase):
    def test_poisson_complement_and_order(self):
        self.assertGreater(poisson_over(2.7, 1.5), poisson_over(2.7, 2.5))
        self.assertGreaterEqual(poisson_over(2.7, 2.5), 0)
        self.assertLessEqual(poisson_over(2.7, 2.5), 1)

    def test_missing_fouls_not_invented(self):
        csv_text = "Date,HomeTeam,AwayTeam,HC,AC,HY,AY\n01/09/2025,A,B,5,3,2,1\n"
        rows = parse_events(csv_text, "Premier League", "2026-11-06T10:00:00Z")
        self.assertEqual(rows[0]["events"]["corners"], [5,3])
        self.assertEqual(rows[0]["events"]["cards"], [2,1])
        self.assertNotIn("fouls", rows[0]["events"])

    def test_no_fabricated_markets_without_history(self):
        queue = {"fixtures":[{"fixture_id":"a","league":"Premier League","home":"A","away":"B",
            "kickoff_utc":"2026-11-08T10:00:00Z"}]}
        result = run(queue,[],[],"2026-11-06T10:00:00Z")
        self.assertEqual(result["markets"],[])
        self.assertEqual(len(result["blockers"]),4)
