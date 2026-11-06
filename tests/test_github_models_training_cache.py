"""Reuse exact verified fits without reusing forecasts or weakening guards."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from github_models.predict import run
from multimodel_v2.dixon_coles_shadow import forecast_dixon_coles


FREEZE = "2026-11-07T10:00:00Z"
FIXTURE = dict(fixture_id="f1", league="Premier League", country_code="ENG",
               home="A", away="B", kickoff_utc="2026-11-08T16:00:00Z")
HISTORY = [dict(fixture_id=f"old-{index}", league="Premier League", home="A", away="B",
                home_goals=index + 1, away_goals=0,
                completed_at_utc=f"2026-11-0{index+1}T16:00:00Z",
                published_at_utc=f"2026-11-0{index+1}T18:00:00Z",
                home_xg=1.2, away_xg=.6, xg_published_at_utc="2026-11-04T08:00:00Z")
           for index in range(2)]


class ArrayInput:
    """A deterministic input container keeps optional-dependency tests offline."""
    def __init__(self, values, dtype=None):
        self.values = tuple(values)
        kind = dtype.__name__ if dtype is not None else type(self.values[0]).__name__
        self.dtype = SimpleNamespace(str=kind)
        self.shape = (len(self.values),)

    def copy(self):
        return self

    def sum(self):
        return sum(self.values)

    def tobytes(self):
        return json.dumps(self.values).encode()


class CountingModel:
    fits = 0
    invalid = False

    def __init__(self, *, seed, xg_weight):
        if seed != 42:
            raise AssertionError("model_seed_changed")
        self.xg_weight = xg_weight

    def fit(self, **inputs):
        type(self).fits += 1
        self.inputs = {key: value.copy() for key, value in inputs.items()}

    def predict(self, home, away):
        if type(self).invalid:
            return dict(home_win=.9, draw=.9, away_win=.9)
        # A deterministic, input-sensitive fake isolates cache behavior from
        # dependency availability and the optimizer's execution time.
        home_probability = .35 + .01 * (int(self.inputs['home_goals'].sum()) % 8)
        if home == "B":
            home_probability += .1
        return dict(home_win=home_probability, draw=.25, away_win=.75-home_probability)


class TrainingCacheTests(unittest.TestCase):
    def setUp(self):
        CountingModel.fits = 0
        CountingModel.invalid = False
        numpy = SimpleNamespace(array=ArrayInput, datetime64=lambda value, unit: value.isoformat() + unit)
        self.dependency = patch.dict("sys.modules", {
            "dixon_coles": SimpleNamespace(DixonColesModel=CountingModel), "numpy": numpy})
        self.dependency.start()
        self.addCleanup(self.dependency.stop)

    def forecast(self, history=None, fixture=None, **options):
        parameters = dict(frozen_at_utc=FREEZE, model_version="pinned-research-v1", min_matches=2)
        parameters.update(options)
        return forecast_dixon_coles(HISTORY if history is None else history,
                                   FIXTURE if fixture is None else fixture, **parameters)

    def test_fit_shared_between_fixtures_but_predictions_remain_specific(self):
        cache = {}
        first = self.forecast(fitted_cache=cache)
        second = self.forecast(fixture=dict(FIXTURE, fixture_id="f2", home="B", away="A"), fitted_cache=cache)
        self.assertEqual(CountingModel.fits, 1)
        self.assertNotEqual(first["fixture_id"], second["fixture_id"])
        self.assertNotEqual(first["p_home"], second["p_home"])
        self.assertEqual(first, self.forecast())
        self.assertEqual(CountingModel.fits, 2)

    def test_default_without_cache_preserves_independent_fits(self):
        self.assertEqual(self.forecast(), self.forecast())
        self.assertEqual(CountingModel.fits, 2)

    def test_key_binds_freeze_version_and_quality_parameters(self):
        cache = {}
        self.forecast(fitted_cache=cache)
        self.forecast(fitted_cache=cache, frozen_at_utc="2026-11-07T11:00:00+01:00")
        self.assertEqual(CountingModel.fits, 1)  # the same normalized instant
        self.forecast(fitted_cache=cache, frozen_at_utc="2026-11-07T10:01:00Z")
        self.forecast(fitted_cache=cache, model_version="another-pinned-version")
        self.forecast(fitted_cache=cache, min_matches=1)
        self.forecast(fitted_cache=cache, xg_weight=.5)
        self.assertEqual(CountingModel.fits, 5)

    def test_key_binds_ordered_goals_names_dates_and_publication(self):
        cache = {}
        self.forecast(fitted_cache=cache)
        mutations = [
            ("home_goals", 4), ("away_goals", 1), ("home", "C"),
            ("completed_at_utc", "2026-11-01T15:00:00Z"),
            ("published_at_utc", "2026-11-01T19:00:00Z"),
        ]
        for key, value in mutations:
            altered = deepcopy(HISTORY)
            altered[0][key] = value
            self.forecast(altered, fitted_cache=cache)
        self.forecast(list(reversed(HISTORY)), fitted_cache=cache)
        self.assertEqual(CountingModel.fits, 7)

    def test_key_binds_xg_inputs_and_availability(self):
        cache = {}
        self.forecast(fitted_cache=cache, xg_weight=.5)
        for field, value in (("home_xg", 2.5), ("away_xg", .9),
                             ("xg_published_at_utc", "2026-11-04T09:00:00Z")):
            altered = deepcopy(HISTORY)
            altered[0][field] = value
            self.forecast(altered, fitted_cache=cache, xg_weight=.5)
        self.assertEqual(CountingModel.fits, 4)

    def test_key_isolated_by_league(self):
        cache = {}
        self.forecast(fitted_cache=cache)
        other = [dict(row, league="Another League") for row in HISTORY]
        self.forecast(other, dict(FIXTURE, league="Another League"), fitted_cache=cache)
        self.assertEqual(CountingModel.fits, 2)

    def test_lookahead_quality_and_kickoff_guards_still_run_on_hits(self):
        cache = {}
        self.forecast(fitted_cache=cache)
        future = deepcopy(HISTORY)
        future[0]["published_at_utc"] = "2026-11-09T18:00:00Z"
        with self.assertRaisesRegex(ValueError, "insufficient_verified_training_matches"):
            self.forecast(future, fitted_cache=cache)
        bad_goals = deepcopy(HISTORY)
        bad_goals[0]["home_goals"] = -1
        with self.assertRaisesRegex(ValueError, "invalid_training_goals"):
            self.forecast(bad_goals, fitted_cache=cache)
        with self.assertRaisesRegex(ValueError, "freeze_must_precede_kickoff"):
            self.forecast(fixture=dict(FIXTURE, kickoff_utc=FREEZE), fitted_cache=cache)
        self.assertEqual(CountingModel.fits, 1)

    def test_xg_lookahead_is_not_hidden_by_cached_fit(self):
        cache = {}
        self.forecast(fitted_cache=cache, xg_weight=.5)
        future = deepcopy(HISTORY)
        future[0]["xg_published_at_utc"] = "2026-11-08T08:00:00Z"
        with self.assertRaisesRegex(ValueError, "xg_not_published_before_freeze"):
            self.forecast(future, fitted_cache=cache, xg_weight=.5)
        self.assertEqual(CountingModel.fits, 1)

    def test_irrelevant_source_metadata_does_not_change_behavior(self):
        cache = {}
        expected = self.forecast(fitted_cache=cache)
        altered = deepcopy(HISTORY)
        altered[0].update(home_xg=float("nan"), irrelevant_metadata=object())
        self.assertEqual(self.forecast(altered, fitted_cache=cache), expected)
        self.assertEqual(CountingModel.fits, 1)

    def test_invalid_predictions_and_failed_fits_are_never_cached(self):
        cache = {}
        CountingModel.invalid = True
        with self.assertRaisesRegex(ValueError, "invalid_dixon_coles_probabilities"):
            self.forecast(fitted_cache=cache)
        self.assertEqual(cache, {})
        CountingModel.invalid = False
        self.forecast(fitted_cache=cache)
        self.assertEqual(CountingModel.fits, 2)
        cache.clear()
        with patch.object(CountingModel, "fit", side_effect=RuntimeError("fit_failed")):
            with self.assertRaisesRegex(RuntimeError, "fit_failed"):
                self.forecast(fitted_cache=cache)
        self.assertEqual(cache, {})

    def test_pipeline_cache_lifetime_is_one_invocation(self):
        history = [dict(HISTORY[index % 2], fixture_id=f"past-{index}") for index in range(35)]
        queue = dict(fixtures=[FIXTURE, dict(FIXTURE, fixture_id="f2", home="B", away="A")])
        first = run(queue, history, as_of_utc=FREEZE)
        self.assertEqual(CountingModel.fits, 1)
        second = run(queue, history, as_of_utc=FREEZE)
        self.assertEqual(CountingModel.fits, 2)
        self.assertEqual(first, second)
        self.assertEqual(len(first["predictions"]), 4)


if __name__ == "__main__":
    unittest.main()
