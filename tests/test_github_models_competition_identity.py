import unittest
from github_models.competition_identity import canonicalize
from github_models.team_mapping import resolve

class CompetitionIdentityTests(unittest.TestCase):
    def test_english_league_id_resolves_without_country_field(self):
        fixture = dict(league="Premier League", league_id="l_4WFCIZ", country_code=None,
                       home="Chelsea", away="Arsenal")
        history = [dict(league="Premier League",home="Chelsea",away="Arsenal")]
        self.assertEqual(resolve(canonicalize(fixture),history)["home"],"Chelsea")

    def test_russian_premier_league_not_misclassified(self):
        fixture = dict(league="Premier League",league_id="l_2Mh0jT",
                       home="Chelsea",away="Arsenal")
        self.assertRaisesRegex(ValueError,"country_not_verified",
            resolve,canonicalize(fixture),
            [dict(league="Premier League",home="Chelsea",away="Arsenal")])

    def test_country_conflict_blocks(self):
        self.assertRaisesRegex(ValueError,"competition_country_conflict",canonicalize,
            dict(league="Serie A",league_id="l_0ALvwF",country_code="BRA"))

    def test_laliga_name_normalization(self):
        self.assertEqual(canonicalize(dict(league="LaLiga",league_id="l_0ErfuF"))["league"],"La Liga")
