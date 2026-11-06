"""Cross-path identity and temporal regression for the isolated research models."""
import unittest
from unittest.mock import patch

from github_models.coverage_audit import audit
from github_models.predict import run
from github_models.settlement import settle, source_match_date
from github_models.market_settlement import settle_markets
from github_models.settle import settle as settle_exact
from github_models.kb3_history_bridge import import_verified_results

FREEZE = "2026-11-05T08:00:00Z"
NOW = "2026-11-09T08:00:00Z"
FIXTURE = dict(fixture_id="pitch-match", league="Premier League", country_code="ENG",
               home="Manchester United", away="Chelsea", kickoff_utc="2026-11-06T18:00:00Z")


def history_row(i, **changes):
    row = dict(fixture_id=f"history-{i}", league="Premier League", home="Man United", away="Chelsea",
               home_goals=2, away_goals=1, completed_at_utc="2026-10-30T20:00:00Z",
               published_at_utc="2026-11-04T07:00:00Z")
    row.update(changes)
    return row


def outcome(**changes):
    row = history_row("result", fixture_id="fdco:2627:E0:2026-11-06:Man United:Chelsea",
                      completed_at_utc="2026-11-08T00:00:00Z", published_at_utc="2026-11-08T07:00:00Z",
                      events={"corners": [5, 4], "cards": [1, 2], "fouls": [9, 11]})
    row.update(changes)
    return row


def prediction(**changes):
    row = dict(fixture_id="pitch-match", model_id="github-elo", frozen_at_utc=FREEZE,
               p_home=.5, p_draw=.25, p_away=.25)
    row.update(changes)
    return row


def market_prediction(**changes):
    row = dict(fixture_id="pitch-match", frozen_at_utc=FREEZE, market="corners", line=8.5,
               selection="over", probability=.6)
    row.update(changes)
    return row


class IdentityIntegrationTests(unittest.TestCase):
    def test_forecast_and_audit_use_only_names_available_at_freeze(self):
        history = [history_row(i) for i in range(35)]
        history.append(history_row("future", home="Manchester United", published_at_utc=NOW))
        with patch("github_models.predict.predict_dixon_coles", return_value=prediction(model_id="dc")):
            result = run({"fixtures": [FIXTURE]}, history, as_of_utc=FREEZE)
        self.assertEqual(len(result["predictions"]), 2)
        self.assertEqual(result["predictions"][0]["resolved_identity"]["home"], "Man United")
        report = audit({"fixtures": [FIXTURE]}, history, as_of_utc=FREEZE)
        self.assertEqual(report["verified_training_matches"], 35)
        self.assertEqual(report["by_league"]["Premier League"]["identity_ready"], 1)

    def test_future_history_cannot_satisfy_audit_sample_gates(self):
        history = [history_row(i, published_at_utc=NOW) for i in range(35)]
        report = audit({"fixtures": [FIXTURE]}, history, as_of_utc=FREEZE)
        self.assertEqual(report["elo_ready"], 0)
        self.assertEqual(report["dixon_coles_history_ready"], 0)
        self.assertEqual(report["identity_ready"], 0)

    def test_started_fixture_is_not_reported_as_ready(self):
        report = audit({"fixtures": [dict(FIXTURE, kickoff_utc=FREEZE)]},
                       [history_row(i) for i in range(35)], as_of_utc=FREEZE)
        self.assertEqual(report["fixtures"][0]["reason"], "prediction_not_prematch")

    def test_model_invalid_probability_output_is_blocked(self):
        with patch("github_models.predict.predict_elo", return_value=prediction(p_home=float("nan"))), \
             patch("github_models.predict.predict_dixon_coles", return_value=prediction(model_id="dc")):
            result = run({"fixtures": [FIXTURE]}, [history_row(i) for i in range(35)], as_of_utc=FREEZE)
        self.assertEqual([p["model_id"] for p in result["predictions"]], ["dc"])
        self.assertEqual(result["blocker_summary"]["elo: invalid_probabilities"], 1)

    def test_queue_duplicate_ids_are_rejected_before_overwrite(self):
        with self.assertRaisesRegex(ValueError, "duplicate_or_invalid_fixture_identity"):
            run({"fixtures": [FIXTURE, dict(FIXTURE, away="Arsenal")]}, [], as_of_utc=FREEZE)

    def test_settlement_uses_provider_league_id_when_country_missing(self):
        fixture = dict(FIXTURE, league_id="l_4WFCIZ")
        fixture.pop("country_code")
        result = settle({"predictions": [prediction()]}, {"fixtures": [fixture]}, [outcome()], NOW)
        self.assertEqual(result["settlements"][0]["status"], "settled")
        self.assertEqual(result["settlements"][0]["actual"], "1")

    def test_both_settlement_paths_require_exact_source_day(self):
        wrong_day = outcome(fixture_id="fdco:2627:E0:2026-11-07:Man United:Chelsea")
        score = settle({"predictions": [prediction()]}, {"fixtures": [FIXTURE]}, [wrong_day], NOW)
        event = settle_markets({"markets": [market_prediction()]}, {"fixtures": [FIXTURE]}, [], [wrong_day], NOW)
        self.assertEqual(score["settlements"][0]["status"], "pending")
        self.assertEqual(event["settlements"][0]["status"], "pending")

    def test_arbitrary_completion_time_is_not_treated_as_match_date(self):
        undated = outcome(fixture_id="another-provider-id")
        with self.assertRaisesRegex(ValueError, "historical_match_date_unverified"):
            source_match_date(undated)
        result = settle({"predictions": [prediction()]}, {"fixtures": [FIXTURE]}, [undated], NOW)
        self.assertEqual(result["settlements"][0]["status"], "pending")

    def test_contradictory_explicit_and_provider_dates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "historical_match_date_conflict"):
            source_match_date(outcome(match_date="2026-11-07"))

    def test_duplicate_verified_outcomes_remain_ambiguous(self):
        score = settle({"predictions": [prediction()]}, {"fixtures": [FIXTURE]}, [outcome(), outcome()], NOW)
        event = settle_markets({"markets": [market_prediction()]}, {"fixtures": [FIXTURE]}, [], [outcome(), outcome()], NOW)
        self.assertEqual(score["settlements"][0]["status"], "ambiguous")
        self.assertEqual(event["settlements"][0]["status"], "ambiguous")

    def test_future_publication_and_nonfinal_outcomes_are_not_settled(self):
        for row in (outcome(published_at_utc="2026-11-10T07:00:00Z"), outcome(status="SCHEDULED")):
            with self.subTest(row=row):
                report = settle({"predictions": [prediction()]}, {"fixtures": [FIXTURE]}, [row], NOW)
                self.assertNotEqual(report["settlements"][0]["status"], "settled")

    def test_frozen_canonical_identity_cannot_be_replaced_by_queue(self):
        frozen = dict(league="Premier League", country_code="ENG", home="Arsenal", away="Chelsea")
        report = settle({"predictions": [prediction(resolved_identity=frozen)]},
                        {"fixtures": [FIXTURE]}, [outcome()], NOW)
        self.assertEqual(report["settlements"][0]["reason"], "frozen_fixture_identity_mismatch")

    def test_forecast_preserves_native_team_id_spellings_and_provider(self):
        fixture = dict(FIXTURE, home_team_id="pitch-home", away_team_id="pitch-away",
                       source_provider="PitchAPI")
        with patch("github_models.predict.predict_dixon_coles", return_value=prediction(model_id="dc")):
            result = run({"fixtures": [fixture]}, [history_row(i) for i in range(35)], as_of_utc=FREEZE)
        self.assertEqual(len(result["predictions"]), 2)
        for forecast in result["predictions"]:
            frozen = forecast["resolved_identity"]
            self.assertEqual(frozen["home_team_id"], "pitch-home")
            self.assertEqual(frozen["away_team_id"], "pitch-away")
            self.assertEqual(frozen["source_provider"], "PitchAPI")
            self.assertNotIn("home_id", frozen)

    def test_same_provider_team_key_aliases_preserve_identity_across_settlement(self):
        frozen = dict(league="Premier League", country_code="ENG", home="Man United", away="Chelsea",
                      home_id="pitch-home", away_id="pitch-away", source_provider="PitchAPI")
        fixture = dict(FIXTURE, home_team_id="pitch-home", away_team_id="pitch-away",
                       source_provider="PitchAPI")
        # football-data IDs are a different namespace; names and exact match
        # date bridge providers without asserting any equivalence of IDs.
        result = outcome(source_provider="football-data.co.uk", home_id="fdco-home", away_id="fdco-away")
        score = settle({"predictions": [prediction(resolved_identity=frozen)]},
                       {"fixtures": [fixture]}, [result], NOW)
        event = settle_markets({"markets": [market_prediction(resolved_identity=frozen)]},
                              {"fixtures": [fixture]}, [result], [result], NOW)
        self.assertEqual(score["settlements"][0]["status"], "settled")
        self.assertEqual(event["settlements"][0]["status"], "settled")

    def test_postfreeze_native_team_id_or_provider_tampering_is_blocked(self):
        frozen = dict(league="Premier League", country_code="ENG", home="Man United", away="Chelsea",
                      home_team_id="pitch-home", away_team_id="pitch-away", source_provider="PitchAPI")
        original = dict(FIXTURE, home_team_id="pitch-home", away_team_id="pitch-away", source_provider="PitchAPI")
        for change in ({"home_team_id": "replaced-home"}, {"away_team_id": None},
                       {"source_provider": "football-data.co.uk"}, {"source_provider": None}):
            with self.subTest(change=change):
                fixture = dict(original, **change)
                score = settle({"predictions": [prediction(resolved_identity=frozen)]},
                               {"fixtures": [fixture]}, [outcome()], NOW)
                event = settle_markets({"markets": [market_prediction(resolved_identity=frozen)]},
                                      {"fixtures": [fixture]}, [outcome()], [outcome()], NOW)
                self.assertEqual(score["settlements"][0]["reason"], "frozen_fixture_identity_mismatch")
                self.assertEqual(event["settlements"][0]["reason"], "frozen_fixture_identity_mismatch")

    def test_all_event_totals_settle_from_same_exact_identity(self):
        for market in ("goals", "corners", "cards", "fouls"):
            with self.subTest(market=market):
                report = settle_markets({"markets": [market_prediction(market=market)]},
                    {"fixtures": [FIXTURE]}, [outcome()], [outcome()], NOW)
                self.assertEqual(report["settlements"][0]["status"], "settled")

    def test_unsupported_event_line_and_direction_fail(self):
        for change in ({"selection": "sideways"}, {"line": 8}, {"line": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                settle_markets({"markets": [market_prediction(**change)]}, {"fixtures": [FIXTURE]}, [], [], NOW)

    def test_nan_boolean_or_negative_probabilities_are_rejected(self):
        for value in (float("nan"), True, -.1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_probabilities"):
                settle({"predictions": [prediction(p_home=value)]}, {"fixtures": [FIXTURE]}, [outcome()], NOW)

    def test_exact_id_settlement_does_not_overwrite_duplicate_outcomes(self):
        verified = dict(fixture_id="pitch-match", status="FINISHED", home_goals=2, away_goals=1,
                        published_at_utc=NOW)
        self.assertEqual(settle_exact([prediction()], [verified, dict(verified, home_goals=0)]), {})
        self.assertEqual(settle_exact([prediction(p_home=float("nan"))], [verified]), {})

    def test_exact_id_settlement_requires_prematch_and_available_results(self):
        verified = dict(fixture_id="pitch-match", status="FINISHED", home_goals=2, away_goals=1,
                        completed_at_utc="2026-11-06T20:00:00Z", published_at_utc="2026-11-07T07:00:00Z")
        valid = prediction(kickoff_utc=FIXTURE["kickoff_utc"])
        self.assertEqual(settle_exact([valid], [verified], as_of_utc=NOW)["github-elo"]["n"], 1)
        self.assertEqual(settle_exact([dict(valid, frozen_at_utc=NOW)], [verified], as_of_utc=NOW), {})
        self.assertEqual(settle_exact([valid], [dict(verified, published_at_utc="2026-11-10T08:00:00Z")], as_of_utc=NOW), {})

    def test_bridge_preserves_explicit_date_and_identity_metadata(self):
        row = dict(outcome(match_date="2026-11-06", country_code="ENG"), status="FINISHED",
                   source_provider="football-data.co.uk", source_record_id="line-1")
        report = import_verified_results([row], as_of_utc=NOW)
        self.assertEqual(report["accepted"][0]["match_date"], "2026-11-06")
        self.assertEqual(report["accepted"][0]["country_code"], "ENG")

    def test_bridge_excludes_every_version_of_duplicate_source_record(self):
        row = dict(outcome(match_date="2026-11-06", country_code="ENG"), status="FINISHED",
                   source_provider="football-data.co.uk", source_record_id="duplicate-line")
        report = import_verified_results([row, dict(row, home_goals=0)], as_of_utc=NOW)
        self.assertEqual(report["accepted_count"], 0)
        self.assertEqual(report["rejection_reasons"]["duplicate_source_record"], 2)


if __name__ == "__main__":
    unittest.main()
