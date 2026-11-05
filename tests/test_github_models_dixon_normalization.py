import unittest
from multimodel_v2.dixon_coles_shadow import normalize_dixon_probabilities

class DixonColesNormalizationTests(unittest.TestCase):
    def test_rounding_does_not_break_strict_contract(self):
        p = normalize_dixon_probabilities(dict(home_win=.4333, draw=.2666, away_win=.3000))
        self.assertAlmostEqual(sum(p), 1.0, places=12)
        self.assertTrue(all(0 <= x <= 1 for x in p))

    def test_invalid_values_fail(self):
        with self.assertRaisesRegex(ValueError, "invalid_dixon_coles_probabilities"):
            normalize_dixon_probabilities(dict(home_win=-.1, draw=.3, away_win=.8))
