import unittest
from unittest.mock import patch
from github_models.predict import run

FIXTURE = dict(fixture_id="future1", league="Premier League", home="Man United",
               away="Chelsea", kickoff_utc="2026-11-07T15:00:00Z")
HISTORY = [dict(fixture_id=f"old{i}", league="Premier League", home="Man United",
                away="Chelsea", home_goals=2, away_goals=1,
                completed_at_utc="2026-10-30T20:00:00Z",
                published_at_utc="2026-11-05T07:00:00Z") for i in range(35)]

class DixonColesRunnerTests(unittest.TestCase):
    def test_independent_models_both_requested(self):
        with patch("github_models.predict.predict_dixon_coles",
                   return_value=dict(fixture_id="future1", model_id="callumfm-dixon-coles",
                                     p_home=.5, p_draw=.25, p_away=.25)) as dc:
            result = run(dict(fixtures=[FIXTURE]), HISTORY,
                         as_of_utc="2026-11-05T08:00:00Z")
        self.assertEqual({r["model_id"] for r in result["predictions"]},
                         {"github-elo", "callumfm-dixon-coles"})
        dc.assert_called_once()
        self.assertEqual(len(result["blockers"]), 1)
        self.assertEqual(result["blockers"][0]["model"], "xgboost")
