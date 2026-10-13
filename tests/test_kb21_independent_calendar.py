import unittest
from tools.kb21_independent_calendar import match_fixtures

class CalendarComparisonTests(unittest.TestCase):
    def test_matching_fixture_is_review_only(self):
        api={"date":"2030-01-01","candidates":[{"fixture_id":9,"event":"A - B","home_team":"Team A","away_team":"Team B","home_team_id":10,"away_team_id":20,"kickoff_utc":"2030-01-01T12:00:00Z"}]}
        other={"provider":"licensed independent calendar","fixtures":[{"home_team":"Team A","away_team":"Team B","home_team_id":101,"away_team_id":202,"provider_match_id":909,"kickoff_utc":"2030-01-01T12:02:00Z","source_url":"https://example.org/match/9"}]}
        result=match_fixtures(api,other)
        self.assertTrue(result["rows"][0]["independent_match"])
        self.assertFalse(result["rows"][0]["official_verified"])
        self.assertFalse(result["rows"][0]["freeze_allowed"])
        self.assertEqual(result["kb_n_effect"],0)
    def test_reject_stale_independent_snapshot(self):
        with self.assertRaises(ValueError):
            match_fixtures({"date":"2030-01-02","candidates":[]},
                           {"date":"2030-01-01","provider":"independent","fixtures":[]})
    def test_reject_same_provider(self):
        with self.assertRaises(ValueError):
            match_fixtures({"candidates":[]},{"provider":"API-Football","fixtures":[]})
    def test_duplicate_is_not_verified(self):
        api={"candidates":[{"fixture_id":9,"home_team_id":10,"away_team_id":20,"kickoff_utc":"2030-01-01T12:00:00Z"}]}
        row={"home_team_id":10,"away_team_id":20,"kickoff_utc":"2030-01-01T12:00:00Z","source_url":"https://example.org/9"}
        result=match_fixtures(api,{"provider":"independent","fixtures":[row,row]})
        self.assertFalse(result["rows"][0]["independent_match"])
if __name__=="__main__":unittest.main()
