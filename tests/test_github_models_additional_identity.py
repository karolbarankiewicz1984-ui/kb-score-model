"""Actual additional-country source spellings with strict competition scopes."""
import unittest

from github_models.competition_identity import canonicalize, country_code, league_for_label
from github_models.reviewed_resolver import resolve_reviewed


class AdditionalCountryIdentityTests(unittest.TestCase):
    def test_live_metadata_identifiers_and_reviewed_source_aliases(self):
        cases = [
            ("Bundesliga", "l_3zsMpo", "AUT", "Rapid Wien", "Austria Wien", "Austrian Bundesliga", "SK Rapid", "Austria Vienna"),
            ("Serie A", "l_1D8Xrl", "BRA", "Flamengo", "Botafogo", "Brazilian Serie A", "Flamengo RJ", "Botafogo RJ"),
            ("Premier League", "l_2Mh0jT", "RUS", "FC Rostov", "Rodina", "Russian Premier League", "FK Rostov", "Rodina Moscow"),
            ("Superligaen", "l_49Zmno", "DEN", "FC København", "OB", "Danish Superliga", "FC Copenhagen", "Odense"),
            ("Liga I", "l_0kSJLz", "ROU", "Rapid Bucureşti", "Universitatea Cluj", "Romanian Superliga", "FC Rapid Bucuresti", "U. Cluj"),
            ("Ekstraklasa", "l_214sqK", "POL", "Legia Warszawa", "Wisła Kraków", "Ekstraklasa", "Legia", "Wisla"),
            ("Allsvenskan", "l_1XsMdH", "SWE", "IFK Göteborg", "Halmstads BK", "Allsvenskan", "Goteborg", "Halmstad"),
            ("J. League", "l_2ApGa4", "JPN", "Urawa Red Diamonds", "Tokyo Verdy", "J1 League", "Urawa Reds", "Verdy"),
            ("Liga MX", "l_3v84VE", "MEX", "CF América", "Chivas", "Liga MX", "Club America", "Guadalajara Chivas"),
            ("MLS", "l_0eg6C9", "USA", "LA Galaxy", "Red Bull New York", "MLS", "Los Angeles Galaxy", "New York Red Bulls"),
            ("Liga Profesional", "l_45VZuL", "ARG", "Estudiantes", "Estudiantes de Río Cuarto", "Liga Profesional", "Estudiantes L.P.", "Estudiantes Rio Cuarto"),
            ("Super League 1", "l_3xwVF2", "GRE", "Olympiacos", "AEK Athens", "Super League", "Olympiakos", "AEK"),
        ]
        for raw, identity, country, home, away, league, htarget, atarget in cases:
            with self.subTest(identity=identity):
                fixture = dict(league=raw, league_id=identity, country_code=country, home=home, away=away)
                result = resolve_reviewed(fixture, [dict(league=league, home=htarget, away=atarget)])
                self.assertEqual((result["league"], result["home"], result["away"]), (league, htarget, atarget))

    def test_explicit_country_disambiguates_shared_labels_without_id(self):
        for raw, country, expected in (("Bundesliga", "AUT", "Austrian Bundesliga"),
                                       ("Bundesliga", "GER", "Bundesliga"),
                                       ("Serie A", "BRA", "Brazilian Serie A"),
                                       ("Serie A", "ITA", "Serie A"),
                                       ("Premier League", "RUS", "Russian Premier League"),
                                       ("Premier League", "ENG", "Premier League"),
                                       ("Superliga", "ROU", "Romanian Superliga"),
                                       ("Superliga", "DEN", "Danish Superliga")):
            with self.subTest(raw=raw, country=country):
                self.assertEqual(canonicalize(dict(league=raw, country_code=country))["league"], expected)
                self.assertEqual(league_for_label(raw, country), expected)

    def test_new_competition_names_cannot_select_another_countrys_history(self):
        fixture = dict(league="Serie A", league_id="l_1D8Xrl", home="Inter", away="Roma")
        with self.assertRaisesRegex(ValueError, "unmatched_home_team"):
            resolve_reviewed(fixture, [dict(league="Serie A", home="Inter", away="Roma")])
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(fixture, country_code="ITA"))

    def test_missing_country_and_id_stay_blocked_for_generic_label(self):
        with self.assertRaisesRegex(ValueError, "country_not_verified"):
            resolve_reviewed(dict(league="Bundesliga", home="Rapid Wien", away="Austria Wien"),
                             [dict(league="Austrian Bundesliga", home="SK Rapid", away="Austria Vienna")])

    def test_ecuador_and_china_are_not_upgraded(self):
        for fixture in (dict(league="Serie A", league_id="l_1dmt9H", country_code="ECU"),
                        dict(league="Super League", league_id="l_20pNSc", country_code="CHN")):
            with self.subTest(fixture=fixture), self.assertRaisesRegex(ValueError, "unsupported_competition_id"):
                canonicalize(fixture)

    def test_known_id_country_conflicts_and_label_conflicts_remain_blocked(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(league="Premier League", league_id="l_2Mh0jT", country_code="ENG"))
        with self.assertRaisesRegex(ValueError, "competition_name_conflict"):
            canonicalize(dict(league="Serie B", league_id="l_1D8Xrl", country_code="BRA"))
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(league="Romanian Superliga", country_code="DNK"))

    def test_country_aliases_include_live_metadata_den(self):
        for value, expected in (("DEN", "DNK"), ("DK", "DNK"), ("PL", "POL"), ("Mexico", "MEX"),
                                ("Japan", "JPN"), ("US", "USA"), ("Romania", "ROU")):
            with self.subTest(value=value):
                self.assertEqual(country_code(value), expected)

    def test_live_remaining_club_spellings(self):
        cases = [
            (dict(league="Superligaen", league_id="l_49Zmno", country_code="DEN", home="Randers FC", away="Nordsjælland"),
             dict(league="Danish Superliga", home="Randers FC", away="Nordsjaelland")),
            (dict(league="2. Bundesliga", league_id="l_3hvsne", home="FC Heidenheim", away="Hannover 96"),
             dict(league="2. Bundesliga", home="Heidenheim", away="Hannover")),
            (dict(league="First Division A", league_id="l_2L6d1F", home="Royal Antwerp", away="Lommel"),
             dict(league="Jupiler Pro League", home="Antwerp", away="Lommel SK")),
        ]
        for fixture, historical in cases:
            with self.subTest(league=fixture["league"]):
                result = resolve_reviewed(fixture, [historical])
                self.assertEqual((result["home"], result["away"]), (historical["home"], historical["away"]))

    def test_reviewed_alias_cannot_hide_two_literal_candidates(self):
        fixture = dict(league="Liga I", league_id="l_0kSJLz", home="Rapid Bucureşti", away="FCSB")
        history = [dict(league="Romanian Superliga", home="Rapid Bucuresti", away="FCSB"),
                   dict(league="Romanian Superliga", home="FC Rapid Bucuresti", away="FCSB")]
        with self.assertRaisesRegex(ValueError, "ambiguous_home_team"):
            resolve_reviewed(fixture, history)


if __name__ == "__main__":
    unittest.main()
