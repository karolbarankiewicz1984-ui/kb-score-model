"""Conservative cache regression: performance without altering match settlement."""
import unittest
from unittest.mock import patch
from github_models.settlement import CachedHistoricalPool, matching_outcomes


class CachedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {"fixture_id": "x", "league": "La Liga 2",
                        "home": "Eibar", "away": "Cadiz",
                        "kickoff_utc": "2026-11-15T17:30:00Z"}
        self.identity = {"league": "La Liga 2", "home": "Eibar", "away": "Cadiz"}
        self.cutoff = "2026-11-16T18:00:00Z"

    def test_replays_identical_evidence_with_only_one_resolution(self):
        data = [{"sample": 1}]
        cache = CachedHistoricalPool(data)
        evidence = [{"home_goals": 2, "away_goals": 1}]
        with patch("github_models.settlement.matching_outcomes", return_value=evidence) as real:
            self.assertEqual(cache.lookup(self.fixture, as_of_utc=self.cutoff,
                                         resolved_identity=self.identity), evidence)
            self.assertEqual(cache.lookup(dict(self.fixture), as_of_utc=self.cutoff,
                                         resolved_identity=dict(self.identity)), evidence)
            self.assertEqual(real.call_count, 1)
            args, kwargs = real.call_args
            self.assertIs(args[1], data)
            self.assertEqual(kwargs["as_of_utc"], self.cutoff)
        self.assertEqual((cache.hits, cache.misses), (1, 1))

    def test_cutoff_identity_and_pool_are_isolated(self):
        with patch("github_models.settlement.matching_outcomes", return_value=[]) as real:
            pool = CachedHistoricalPool([])
            pool.lookup(self.fixture, as_of_utc=self.cutoff)
            pool.lookup(self.fixture, as_of_utc="2026-11-17T18:00:00Z")
            pool.lookup({**self.fixture, "home": "Other"},
                        as_of_utc=self.cutoff)
            CachedHistoricalPool([]).lookup(self.fixture, as_of_utc=self.cutoff)
            self.assertEqual(real.call_count, 4)

    def test_failure_is_replayed_not_silently_converted(self):
        pool = CachedHistoricalPool([])
        with patch("github_models.settlement.matching_outcomes",
                   side_effect=ValueError("multiple_verified_outcomes")) as real:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, "multiple_verified_outcomes"):
                    pool.lookup(self.fixture, as_of_utc=self.cutoff)
            self.assertEqual(real.call_count, 1)

    def test_dispatch_respects_normal_pool_and_cached_pool(self):
        # Empty history produces the same unresolved-team error on either path.
        with self.assertRaises(ValueError) as plain:
            matching_outcomes(self.fixture, [], as_of_utc=self.cutoff)
        with self.assertRaises(ValueError) as cached:
            matching_outcomes(self.fixture, CachedHistoricalPool([]),
                              as_of_utc=self.cutoff)
        self.assertEqual(str(plain.exception), str(cached.exception))


if __name__ == "__main__":
    unittest.main()
