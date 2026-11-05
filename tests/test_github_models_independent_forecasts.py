import unittest
from github_models.elo_engine import predict_elo, train_elo
from github_models.predict import run

FREEZE = "2026-11-05T08:00:00Z"
FIXTURE = dict(fixture_id="f-next", league="L", home="A", away="B",
               kickoff_utc="2026-11-05T18:00:00Z")
def record(i, completed="2026-10-31T19:00:00Z", published="2026-10-31T20:00:00Z"):
    return dict(fixture_id=f"f{i}", league="L", home="A", away="B",
                home_goals=2, away_goals=1, completed_at_utc=completed,
                published_at_utc=published)

class IndependentForecastTests(unittest.TestCase):
    def test_real_elo_forecast_is_normalized(self):
        row = predict_elo([record(i) for i in range(6)], FIXTURE, frozen_at_utc=FREEZE)
        self.assertAlmostEqual(sum(row[k] for k in ("p_home", "p_draw", "p_away")), 1)
        self.assertEqual(row["probability_status"], "uncalibrated_research")

    def test_future_publication_excluded(self):
        history = [record(i, published="2026-11-06T20:00:00Z") for i in range(6)]
        with self.assertRaisesRegex(ValueError, "insufficient_verified_team_history"):
            predict_elo(history, FIXTURE, frozen_at_utc=FREEZE)

    def test_missing_history_yields_blockers_not_fabricated_picks(self):
        output = run(dict(fixtures=[FIXTURE]), [], as_of_utc=FREEZE)
        self.assertEqual(output["predictions"], [])
        self.assertEqual(len(output["blockers"]), 3)
        self.assertTrue(output["production_multimodel_unchanged"])
