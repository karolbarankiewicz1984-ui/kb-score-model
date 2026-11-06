import unittest
from github_models.reviewed_resolver import resolve_reviewed
from github_models.competition_identity import canonicalize

class ReviewedAliasesTests(unittest.TestCase):
    def test_verified_alias_resolves(self):
        fixture = dict(league="LaLiga",league_id="l_0ErfuF",home="Deportivo Alavés",away="Real Betis")
        history = [dict(league="La Liga",home="Alaves",away="Betis")]
        result = resolve_reviewed(canonicalize(fixture),history)
        self.assertEqual((result["home"],result["away"]),("Alaves","Betis"))

    def test_no_approximate_match(self):
        fixture = dict(league="LaLiga",league_id="l_0ErfuF",home="Unknown Alaves",away="Real Betis")
        history = [dict(league="La Liga",home="Alaves",away="Betis")]
        self.assertRaisesRegex(ValueError,"unmatched_home_team",resolve_reviewed,canonicalize(fixture),history)
