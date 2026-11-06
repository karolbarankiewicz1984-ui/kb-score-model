"""Cross-market identity checks found by the independent repair review."""
import copy
import unittest

from github_models.event_markets import run
from tests.test_github_models_probability_invariants import FREEZE, FIXTURE, samples


class EventIdentitySafetyTests(unittest.TestCase):
    def test_event_forecast_freezes_native_provider_team_identifiers(self):
        scores, events = samples()
        fixture = dict(FIXTURE, source_provider="PitchAPI", home_team_id="t-home", away_team_id="t-away")
        result = run({"fixtures": [fixture]}, scores, events, FREEZE)
        self.assertEqual(len(result["markets"]), 24)
        for row in result["markets"]:
            frozen = row["resolved_identity"]
            self.assertEqual((frozen["source_provider"], frozen["home_team_id"], frozen["away_team_id"]),
                             ("PitchAPI", "t-home", "t-away"))

    def test_duplicate_queue_identity_cannot_emit_duplicate_market_signals(self):
        scores, events = samples()
        duplicate = dict(FIXTURE, home="Different club")
        with self.assertRaisesRegex(ValueError, "duplicate_or_invalid_fixture_identity"):
            run({"fixtures": [FIXTURE, duplicate]}, scores, events, FREEZE)

    def test_foreign_same_name_statistics_cannot_change_english_forecast(self):
        scores, events = samples()
        baseline = run({"fixtures": [FIXTURE]}, scores, events, FREEZE)
        foreign = []
        for row in events:
            altered = copy.deepcopy(row)
            altered.update(country_code="RUS", match_date="foreign-" + row["match_date"],
                           events={market: [1000, 1000] for market in ("corners", "cards", "fouls")})
            foreign.append(altered)
        actual = run({"fixtures": [FIXTURE]}, scores, events + foreign, FREEZE)
        self.assertEqual(actual, baseline)

    def test_foreign_provider_id_without_country_is_not_a_verified_league(self):
        scores, events = samples()
        baseline = run({"fixtures": [FIXTURE]}, scores, events, FREEZE)
        foreign = []
        for row in events:
            altered = copy.deepcopy(row)
            altered.update(league_id="l_2Mh0jT", match_date="foreign-" + row["match_date"],
                           events={market: [1000, 1000] for market in ("corners", "cards", "fouls")})
            foreign.append(altered)
        self.assertEqual(run({"fixtures": [FIXTURE]}, scores, events + foreign, FREEZE), baseline)


if __name__ == "__main__":
    unittest.main()
