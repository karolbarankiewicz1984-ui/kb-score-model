import unittest
from github_models.team_mapping import resolve

class TeamMappingTests(unittest.TestCase):
    def test_explicit_alias(self):
        history = [dict(league="Premier League", home="Man United", away="Chelsea")]
        fixture = dict(fixture_id="m1", league="Premier League", country="England",
                       home="Manchester United", away="Chelsea")
        mapped = resolve(fixture, history)
        self.assertEqual(mapped["home"], "Man United")
        self.assertEqual(mapped["away"], "Chelsea")

    def test_no_fuzzy_guessing(self):
        history = [dict(league="Premier League", home="Man United", away="Chelsea")]
        fixture = dict(fixture_id="m1", league="Premier League", country="England",
                       home="Unknown FC", away="Chelsea")
        with self.assertRaisesRegex(ValueError, "unmatched_home_team"):
            resolve(fixture, history)

    def test_unverified_shared_league_name_is_blocked(self):
        history = [dict(league='Premier League', home='Chelsea', away='Arsenal')]
        fixture = dict(league='Premier League', home='Chelsea', away='Arsenal')
        with self.assertRaisesRegex(ValueError, 'country_not_verified'):
            resolve(fixture, history)
