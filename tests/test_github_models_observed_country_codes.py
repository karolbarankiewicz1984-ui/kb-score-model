"""Country codes observed in real PitchAPI metadata, not invented ISO guesses."""
import unittest

from github_models.competition_identity import canonicalize, country_code
from github_models.reviewed_resolver import resolve_reviewed


class ObservedCountryCodeTests(unittest.TestCase):
    def test_all_actual_metadata_country_codes_except_int_normalize(self):
        # Complete code inventory from the 65 league receipts in run 42189744814.
        observed = "ARG AUS AUT BEL BOL BRA CAN CHI CHN COL CRO CZE DEN ECU ENG ESP FIN FRA GER GRE IND INT ISR ITA JPN KOR KSA LVA MEX NED NOR PAR PER POL POR QAT ROU RUS SCO SRB SUI SVK SWE THA TUR UAE USA VEN".split()
        replacements = dict(CHI="CHL", CRO="HRV", DEN="DNK", GER="DEU", GRE="GRC", KSA="SAU",
                            NED="NLD", PAR="PRY", POR="PRT", SUI="CHE", UAE="ARE")
        for raw in observed:
            with self.subTest(code=raw):
                if raw == "INT":
                    self.assertIsNone(country_code(raw))
                else:
                    expected = replacements.get(raw, raw)
                    self.assertEqual(country_code(raw), expected)
                    self.assertEqual(country_code(expected), expected)

    def test_valid_country_metadata_does_not_create_league_history(self):
        fixture = dict(league="HNL", league_id="l_2tFk9k", country_code="CRO", home="Slaven Koprivnica", away="Istra 1961")
        canonical = canonicalize(fixture)
        self.assertEqual(canonical["country_code"], "HRV")
        self.assertEqual(canonical["league_id"], "l_2tFk9k")
        with self.assertRaisesRegex(ValueError, "unmatched_home_team:Slaven Koprivnica"):
            resolve_reviewed(canonical, [])

    def test_unrecognized_and_international_codes_stay_unverified(self):
        for raw in ("XYZ", "INT", "UK", "GB"):
            with self.subTest(code=raw):
                self.assertIsNone(country_code(raw))
                with self.assertRaisesRegex(ValueError, "country_not_verified"):
                    canonicalize(dict(league="Premier League", country_code=raw))

    def test_recognized_fifa_code_cannot_bypass_a_known_competition_country(self):
        with self.assertRaisesRegex(ValueError, "competition_country_conflict"):
            canonicalize(dict(league="Premier League", league_id="l_4WFCIZ", country_code="CRO"))
        with self.assertRaisesRegex(ValueError, "competition_id_not_verified"):
            canonicalize(dict(league="Premier League", league_id="l_unreviewed", country_code="ENG"))


if __name__ == "__main__":
    unittest.main()
