import unittest
from github_models.public_results import parse_csv

CSV = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nE0,01/11/2026,Arsenal,Chelsea,2,1\nE0,05/11/2026,Leeds,Everton,,\n"

class PublicHistoryTests(unittest.TestCase):
    def test_conservative_completion_bound(self):
        rows = parse_csv(CSV, league_code="E0", season="2627",
                         observed_at_utc="2026-11-05T22:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published_at_utc"], "2026-11-05T22:00:00Z")
        self.assertEqual(rows[0]["completed_at_utc"], "2026-11-03T00:00:00Z")

    def test_never_uses_unobserved_future_scores(self):
        rows = parse_csv(CSV, league_code="E0", season="2627",
                         observed_at_utc="2026-11-02T12:00:00Z")
        self.assertEqual(rows, [])
