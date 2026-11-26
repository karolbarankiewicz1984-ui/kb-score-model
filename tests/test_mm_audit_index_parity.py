"""Parity of indexed audit matching with the unchanged direct path."""
import unittest
from github_models.settlement import CachedHistoricalPool, matching_outcomes

AT = "2026-11-26T18:00:00Z"
FIX = {"fixture_id":"p1","league":"Premier League","country_code":"ENG",
       "home":"Manchester United","away":"Chelsea","kickoff_utc":"2026-11-24T19:00:00Z"}
ROW = {"fixture_id":"fdco:E0:2627:2026-11-24:m","league":"Premier League",
       "country_code":"ENG","home":"Man United","away":"Chelsea",
       "match_date":"2026-11-24","completed_at_utc":"2026-11-24T21:00:00Z",
       "published_at_utc":"2026-11-25T00:00:00Z","home_goals":2,"away_goals":1}

def result(f, rows, at=AT, identity=None):
    try:
        return ("ok", matching_outcomes(f, rows, as_of_utc=at, resolved_identity=identity))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return (type(e), str(e))

class AuditIndexParity(unittest.TestCase):
    def parity(self, rows, f=FIX, at=AT, identity=None):
        pool = CachedHistoricalPool(rows)
        expected = result(f, rows, at, identity)
        self.assertEqual(result(f, pool, at, identity), expected)
        self.assertEqual(result(f, pool, at, identity), expected)
        self.assertEqual(pool.hits, 1)
        return expected

    def test_exact_and_unrelated(self):
        rows = [dict(ROW, league="Ligue 1", country_code="FRA"), ROW]
        self.assertEqual(self.parity(rows), ("ok", [ROW]))

    def test_duplicate_order(self):
        row2 = dict(ROW, fixture_id="another")
        self.assertEqual(self.parity([row2, ROW]), ("ok", [row2, ROW]))

    def test_cutoff_and_invalid_rows(self):
        rows = [dict(ROW, published_at_utc="2026-12-01T00:00:00Z"),
                dict(ROW, status="CANCELLED"), {}, ROW]
        pool = CachedHistoricalPool(rows)
        for at in ("2026-11-24T20:00:00Z", AT, "2026-12-02T00:00:00Z"):
            self.assertEqual(result(FIX, pool, at), result(FIX, rows, at))
        self.assertEqual(len(pool.eligible_by_cutoff), 3)

    def test_alias_collision(self):
        outcome = self.parity([ROW, dict(ROW, home="Manchester United")])
        self.assertIn("ambiguous_home_team", outcome[1])

    def test_country_conflict(self):
        outcome = self.parity([ROW, dict(ROW, country_code="FRA")])
        self.assertEqual(outcome[1], "history_competition_country_conflict")

    def test_frozen_identity_conflict(self):
        self.assertEqual(self.parity([ROW], identity=dict(FIX, home="Other"))[1],
                         "frozen_fixture_identity_mismatch")

    def test_date_and_order(self):
        self.assertEqual(self.parity([ROW, dict(ROW, home="Chelsea", away="Man United"),
             dict(ROW, fixture_id="other", match_date="2026-11-23")]), ("ok", [ROW]))

    def test_provider_native_conflict(self):
        row = dict(ROW, source_provider="pitch", home_id="wrong", away_id="a")
        f = dict(FIX, source_provider="pitch", home_id="h", away_id="a")
        self.assertEqual(self.parity([row], f=f)[1], "fixture_team_id_name_conflict")

if __name__ == "__main__":
    unittest.main()
