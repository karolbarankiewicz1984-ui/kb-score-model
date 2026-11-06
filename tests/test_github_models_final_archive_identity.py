import unittest

from github_models.competition_identity import canonicalize, country_code, league_for_label
from github_models.reviewed_resolver import resolve_reviewed


class FinalArchiveIdentityTests(unittest.TestCase):
    def test_actual_final_country_source_spellings(self):
        cases = [
            ("Super League", "l_20pNSc", "CHN", "Henan", "Shenzhen Peng City", "Chinese Super League", "Henan Songshan Longmen", "Shenzhen Xinpengcheng"),
            ("Veikkausliiga", "l_3Ci5Cg", "FIN", "Oulu", "KuPS", "Veikkausliiga", "AC Oulu", "KuPS"),
            ("Premier Division", "l_1eJSA7", "IRL", "St Patrick's Athletic", "Drogheda United", "Irish Premier Division", "St. Patricks", "Drogheda"),
            ("Eliteserien", "l_0uqFK8", "NOR", "Hamarkameratene", "KFUM", "Eliteserien", "HamKam", "KFUM Oslo"),
            ("Super League", "l_4d6Bwl", "SUI", "FC Zürich", "Grasshopper", "Swiss Super League", "Zurich", "Grasshoppers"),
        ]
        for raw, identity, country, home, away, league, htarget, atarget in cases:
            with self.subTest(identity=identity):
                fixture = dict(league=raw, league_id=identity, country_code=country, home=home, away=away)
                result = resolve_reviewed(fixture, [dict(league=league, home=htarget, away=atarget)])
                self.assertEqual((result["league"], result["home"], result["away"]), (league, htarget, atarget))
                self.assertEqual(canonicalize(result), result)

    def test_verified_swiss_second_division_id_does_not_invent_missing_history(self):
        fixture = dict(league="Challenge League", league_id="l_4auCPk", country_code="SUI",
                       home="Winterthur", away="Etoile Carouge")
        canonical = canonicalize(fixture)
        self.assertEqual((canonical["league"], canonical["country_code"]), ("Swiss Challenge League", "CHE"))
        with self.assertRaisesRegex(ValueError, "unmatched_home_team:Winterthur"):
            resolve_reviewed(canonical, [])

    def test_generic_super_league_requires_its_own_verified_country(self):
        for country, league in (("GRC", "Super League"), ("CHN", "Chinese Super League"), ("SUI", "Swiss Super League")):
            with self.subTest(country=country):
                self.assertEqual(league_for_label("Super League", country), league)
                self.assertEqual(canonicalize(dict(league="Super League", country_code=country))["league"], league)

    def test_shared_super_league_ids_cannot_cross_countries(self):
        for identity, wrong_country in (("l_20pNSc", "GRC"), ("l_4d6Bwl", "CHN"), ("l_3xwVF2", "SUI")):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "competition_country_conflict"):
                canonicalize(dict(league="Super League", league_id=identity, country_code=wrong_country))

    def test_swiss_metadata_is_normalized_but_filename_is_not_a_country_code(self):
        self.assertEqual(country_code("SUI"), "CHE")
        self.assertEqual(country_code("Switzerland"), "CHE")
        self.assertIsNone(country_code("SWZ"))
        self.assertEqual(canonicalize(dict(league="Super League", league_id="l_4d6Bwl", country_code="SUI"))["country_code"], "CHE")

    def test_chinese_fixture_never_uses_swiss_or_greek_team_history(self):
        fixture = dict(league="Super League", league_id="l_20pNSc", home="Basel", away="Young Boys")
        history = [dict(league="Swiss Super League", home="Basel", away="Young Boys")]
        with self.assertRaisesRegex(ValueError, "unmatched_home_team"):
            resolve_reviewed(fixture, history)

    def test_unreviewed_identifiers_and_missing_country_remain_blocked(self):
        with self.assertRaisesRegex(ValueError, "competition_id_not_verified"):
            canonicalize(dict(league="Super League", league_id="l_unreviewed", country_code="SUI"))
        with self.assertRaisesRegex(ValueError, "country_not_verified"):
            resolve_reviewed(dict(league="Super League", home="Basel", away="Young Boys"),
                             [dict(league="Swiss Super League", home="Basel", away="Young Boys")])

    def test_new_aliases_do_not_hide_candidate_collisions(self):
        history = [dict(league="Eliteserien", home="Hamarkameratene", away="Viking"),
                   dict(league="Eliteserien", home="HamKam", away="Viking")]
        fixture = dict(league="Eliteserien", league_id="l_0uqFK8", home="Hamarkameratene", away="Viking")
        with self.assertRaisesRegex(ValueError, "ambiguous_home_team"):
            resolve_reviewed(fixture, history)


if __name__ == '__main__':
    unittest.main()
