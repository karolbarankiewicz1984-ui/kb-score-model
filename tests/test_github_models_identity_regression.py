"""Cross-provider identity regressions: aliases never bypass identity conflicts."""
import unittest

from github_models.competition_identity import canonicalize, COMPETITIONS
from github_models.reviewed_resolver import resolve_reviewed
from github_models.team_mapping import resolve


class IdentityRegressionTests(unittest.TestCase):
    def fixture(self, **changes):
        return dict(dict(league="Premier League", league_id="l_4WFCIZ",
                         home="Coventry City", away="Hull City"), **changes)

    def test_missing_country_comes_from_observed_id(self):
        result = resolve_reviewed(self.fixture(), [dict(league="Premier League", home="Coventry", away="Hull")])
        self.assertEqual((result["country_code"], result["home"], result["away"]), ("ENG", "Coventry", "Hull"))

    def test_supported_league_labels_and_country_spellings(self):
        cases = [("Liga Portugal", "l_4QexZg", "PT", "Primeira Liga"),
                 ("First Division A", "l_2L6d1F", "Belgium", "Jupiler Pro League"),
                 ("Süper Lig", "l_0S1uaf", "Türkiye", "Super Lig"),
                 ("Premiership", "l_1LMdEO", "Scotland", "Premiership"),
                 ("Bundesliga", "l_1Isor4", "GER", "Bundesliga")]
        for label, identity, country, expected in cases:
            with self.subTest(league=label):
                row = canonicalize(dict(league=label, league_id=identity, country_code=country))
                self.assertEqual(row["league"], expected)
                self.assertEqual(row["country_code"], COMPETITIONS[identity][1])

    def test_generic_country_not_inferred_from_team_names(self):
        with self.assertRaisesRegex(ValueError, "country_not_verified"):
            resolve(dict(league="Premier League", home="Chelsea", away="Arsenal"),
                    [dict(league="Premier League", home="Chelsea", away="Arsenal")])

    def test_country_and_id_conflict_even_with_matching_teams(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            resolve(self.fixture(country_code="BRA"), [dict(league="Premier League", home="Coventry", away="Hull")])

    def test_conflicting_country_fields_block(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(self.fixture(country_code="ENG", country="Spain"))

    def test_known_id_cannot_override_wrong_competition_label(self):
        with self.assertRaisesRegex(ValueError, "competition_name_conflict"):
            canonicalize(self.fixture(league="Championship"))

    def test_unknown_id_cannot_be_upgraded_with_familiar_country(self):
        with self.assertRaisesRegex(ValueError, "competition_id_not_verified"):
            canonicalize(self.fixture(league_id="l_unreviewed", country_code="ENG"))

    def test_foreign_namesake_cannot_be_upgraded_with_familiar_country(self):
        for identity in ("l_2Mh0jT", "l_46aZMC", "l_3UiOcj"):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "competition_country_conflict"):
                canonicalize(self.fixture(league_id=identity, country_code="ENG"))

    def test_chinese_super_league_is_not_greece(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(league="Super League", league_id="l_20pNSc", country_code="GRC"))

    def test_uk_does_not_prove_english_competition(self):
        with self.assertRaisesRegex(ValueError, "country_not_verified"):
            canonicalize(self.fixture(league_id=None, country_code="UK"))

    def test_known_competition_id_can_refine_uk_wide_metadata(self):
        self.assertEqual(canonicalize(self.fixture(country_code="GB"))["country_code"], "ENG")
        self.assertEqual(canonicalize(dict(league="Premiership", league_id="l_1LMdEO", country_code="GBR"))["country_code"], "SCO")

    def test_exact_and_alias_candidates_collide(self):
        history = [dict(league="Premier League", home="Coventry City", away="Hull"),
                   dict(league="Premier League", home="Coventry", away="Hull")]
        with self.assertRaisesRegex(ValueError, "ambiguous_home_team"):
            resolve_reviewed(self.fixture(), history)

    def test_normalization_collision_is_not_resolved_by_alias_retry(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull"),
                   dict(league="Premier League", home="Coventry!", away="Hull")]
        with self.assertRaisesRegex(ValueError, "ambiguous_home_team"):
            resolve_reviewed(self.fixture(), history)

    def test_alias_cannot_cross_league_boundary(self):
        with self.assertRaisesRegex(ValueError, "unmatched_home_team"):
            resolve(self.fixture(), [dict(league="Championship", home="Coventry", away="Hull")])

    def test_youth_or_womens_team_does_not_lose_identity_tokens(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull")]
        for name in ("Coventry City U21", "Coventry City Women", "Unknown Coventry City"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unmatched_home_team"):
                resolve(self.fixture(home=name), history)

    def test_resolved_sides_must_differ(self):
        with self.assertRaisesRegex(ValueError, "fixture_teams_not_distinct"):
            resolve(self.fixture(home="Hull", away="Hull City"),
                    [dict(league="Premier League", home="Coventry", away="Hull")])

    def test_original_fixture_is_unchanged_and_canonicalization_idempotent(self):
        fixture = self.fixture(home_id="pitch:home", away_id="pitch:away")
        original = dict(fixture)
        canonical = canonicalize(fixture)
        self.assertEqual(canonicalize(canonical), canonical)
        resolve(canonical, [dict(league="Premier League", home="Coventry", away="Hull")])
        self.assertEqual(fixture, original)

    def test_historical_country_conflict_blocks(self):
        with self.assertRaisesRegex(ValueError, "history_competition_country_conflict"):
            resolve(self.fixture(), [dict(league="Premier League", country_code="RUS", home="Coventry", away="Hull")])

    def test_supplied_team_identifiers_must_be_valid_and_distinct(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull")]
        for ids, message in ((dict(home_id=1, away_id="1"), "fixture_team_ids_not_distinct"),
                             (dict(home_id=True), "fixture_team_id_invalid"),
                             (dict(away_id="   "), "fixture_team_id_invalid")):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, message):
                resolve(self.fixture(**ids), history)

    def test_alternate_team_id_fields_are_checked(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull")]
        for ids, message in ((dict(home_team_id="same", away_team_id="same"), "fixture_team_ids_not_distinct"),
                             (dict(home_id="one", home_team_id="two"), "fixture_team_id_conflict")):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, message):
                resolve(self.fixture(**ids), history)

    def test_same_provider_team_ids_must_agree_with_names(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull",
                        home_team_id="pitch:cov", away_team_id="pitch:hull", source_provider="PitchAPI")]
        with self.assertRaisesRegex(ValueError, "fixture_team_id_name_conflict"):
            resolve(self.fixture(home_team_id="pitch:hull", source_provider="PitchAPI"), history)
        result = resolve(self.fixture(home_team_id="pitch:cov", source_provider="PitchAPI"), history)
        self.assertEqual(result["home"], "Coventry")

    def test_cross_provider_ids_are_not_equated(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull",
                        home_team_id="other:cov", away_team_id="pitch:cov", source_provider="OtherProvider")]
        result = resolve(self.fixture(home_team_id="pitch:cov", source_provider="PitchAPI"), history)
        self.assertEqual(result["home"], "Coventry")

    def test_multiple_same_provider_ids_for_one_name_are_ambiguous(self):
        history = [dict(league="Premier League", home="Coventry", away="Hull",
                        home_team_id=identity, source_provider="PitchAPI") for identity in ("one", "two")]
        with self.assertRaisesRegex(ValueError, "history_team_id_ambiguous"):
            resolve(self.fixture(home_team_id="one", source_provider="PitchAPI"), history)

    def test_observed_additional_league_aliases(self):
        cases = [
            (dict(league="Liga Portugal", league_id="l_4QexZg", home="Sporting CP", away="Braga"),
             dict(league="Primeira Liga", home="Sp Lisbon", away="Sp Braga")),
            (dict(league="Eredivisie", league_id="l_4H43wr", home="Fortuna Sittard", away="SC Heerenveen"),
             dict(league="Eredivisie", home="For Sittard", away="Heerenveen")),
            (dict(league="Super Lig", league_id="l_0S1uaf", home="Başakşehir", away="Göztepe"),
             dict(league="Super Lig", home="Buyuksehyr", away="Goztep")),
            (dict(league="First Division A", league_id="l_2L6d1F", home="Zulte Waregem", away="KV Mechelen"),
             dict(league="Jupiler Pro League", home="Waregem", away="Mechelen")),
        ]
        for fixture, row in cases:
            with self.subTest(league=fixture["league"]):
                result = resolve_reviewed(fixture, [row])
                self.assertEqual((result["home"], result["away"]), (row["home"], row["away"]))

    def test_reviewed_lower_division_identifiers_and_aliases(self):
        cases = [
            ("Championship", "l_4DWyTT", "Bolton Wanderers", "Derby County", "Championship", "Bolton", "Derby"),
            ("League One", "l_0ahLw8", "Sheffield Wednesday", "Peterborough United", "League One", "Sheffield Weds", "Peterboro"),
            ("League Two", "l_1W6idJ", "Bristol Rovers", "Crewe Alexandra", "League Two", "Bristol Rvs", "Crewe"),
            ("2. Bundesliga", "l_3hvsne", "Dynamo Dresden", "1. FC Nürnberg", "2. Bundesliga", "Dresden", "Nurnberg"),
            ("Serie B", "l_0jy5yE", "LR Vicenza", "Ascoli", "Serie B", "Vicenza", "Ascoli"),
            ("LaLiga2", "l_3kyHLd", "Celta Fortuna", "Burgos CF", "La Liga 2", "Celta B", "Burgos"),
            ("Ligue 2", "l_0275VP", "Annecy FC", "Pau", "Ligue 2", "Annecy", "Pau FC"),
        ]
        for label, identity, home, away, league, htarget, atarget in cases:
            with self.subTest(label=label):
                fixture = dict(league=label, league_id=identity, home=home, away=away)
                result = resolve_reviewed(fixture, [dict(league=league, home=htarget, away=atarget)])
                self.assertEqual((result["home"], result["away"]), (htarget, atarget))

    def test_brazilian_serie_b_cannot_become_italian(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(league="Serie B", league_id="l_3qUkB8", country_code="ITA"))
        with self.assertRaisesRegex(ValueError, "country_not_verified"):
            resolve(dict(league="Serie B", league_id="l_3qUkB8", home="Ascoli", away="Palermo"),
                    [dict(league="Serie B", home="Ascoli", away="Palermo")])

    def test_actual_german_and_spanish_provider_spellings(self):
        cases = [
            (dict(league="Bundesliga", league_id="l_1Isor4", home="1. FC Köln", away="Hamburger SV"),
             dict(league="Bundesliga", home="FC Koln", away="Hamburg")),
            (dict(league="LaLiga", league_id="l_0ErfuF", home="Espanyol", away="Rayo Vallecano"),
             dict(league="La Liga", home="Espanol", away="Vallecano")),
        ]
        for fixture, row in cases:
            with self.subTest(league=fixture["league"]):
                result = resolve_reviewed(fixture, [row])
                self.assertEqual((result["home"], result["away"]), (row["home"], row["away"]))


if __name__ == "__main__":
    unittest.main()
