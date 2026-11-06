"""Numerical and leakage contracts for independently generated research markets."""
import copy
from datetime import datetime, timedelta, timezone
import math
import unittest

from github_models.elo_engine import eligible_history, predict_elo, train_elo
from github_models.event_markets import MIN_LEAGUE, MIN_TEAM, THRESHOLDS, poisson_over, run
from github_models.event_parser import parse_events
from github_models.public_results import parse_csv
from multimodel_v2.dixon_coles_shadow import normalize_dixon_probabilities


FREEZE = "2026-11-06T10:00:00Z"
FIXTURE = {"fixture_id": "next", "league": "Premier League", "country_code": "ENG",
           "home": "A", "away": "B", "kickoff_utc": "2026-11-08T15:00:00Z"}


def samples(count=60, *, zero=False):
    scores, events = [], []
    for index in range(count):
        day = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
        stamp = day.isoformat()
        common = dict(league="Premier League", home="A", away="B",
                      completed_at_utc=stamp, published_at_utc=stamp)
        scores.append(dict(common, fixture_id=f"past-{index}",
                           home_goals=0 if zero else 2, away_goals=0 if zero else 1))
        events.append(dict(common, match_date=day.date().isoformat(),
                           source_provider="football-data.co.uk",
                           events={"corners": [0, 0] if zero else [5, 4],
                                   "cards": [0, 0] if zero else [2, 1],
                                   "fouls": [0, 0] if zero else [10, 9]}))
    return scores, events


class PoissonNumericalTests(unittest.TestCase):
    def test_independent_reference_values_and_tiny_tail(self):
        # scipy.stats.poisson.sf reference values recorded at full precision.
        references = ((2.7, 2.5, .5063755089265384),
                      (30, 22.5, .9194309789050202),
                      (1000, 999.5, .5042052441802155),
                      (1_000_000, 999999.5, .5001329807608725),
                      (1e-10, 1.5, 4.9999999996666536e-21))
        for rate, line, expected in references:
            with self.subTest(rate=rate, line=line):
                actual = poisson_over(rate, line)
                self.assertTrue(math.isfinite(actual))
                self.assertAlmostEqual(actual / expected, 1, places=7)

    def test_zero_rate_is_deterministic(self):
        self.assertEqual(poisson_over(0, .5), 0)
        self.assertEqual(poisson_over(0, 25.5), 0)

    def test_tail_is_monotone_in_line_and_rate(self):
        for lines in THRESHOLDS.values():
            for rate in (.01, 1, 3, 10, 30, 1000):
                probabilities = [poisson_over(rate, line) for line in lines]
                self.assertEqual(probabilities, sorted(probabilities, reverse=True))
                self.assertTrue(all(0 <= value <= 1 for value in probabilities))
        for line in (.5, 2.5, 22.5):
            probabilities = [poisson_over(rate, line) for rate in (0, .01, 1, 3, 10, 30, 1000)]
            self.assertEqual(probabilities, sorted(probabilities))

    def test_invalid_rates_and_push_lines_fail_explicitly(self):
        for rate in (-1, float("inf"), float("nan"), True, None, "2"):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                poisson_over(rate, 2.5)
        for line in (-.5, 0, 2, 2.25, float("inf"), float("nan"), True, None):
            with self.subTest(line=line), self.assertRaises(ValueError):
                poisson_over(2, line)


class ResearchMarketInvariantTests(unittest.TestCase):
    def test_all_four_count_markets_have_complementary_ordered_probabilities(self):
        scores, events = samples()
        result = run({"fixtures": [FIXTURE]}, scores, events, FREEZE)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(len(result["markets"]), 24)
        pairs = {}
        for row in result["markets"]:
            self.assertEqual(row["probability_status"], "uncalibrated_research")
            self.assertEqual(row["league_n"], 60)
            self.assertTrue(math.isfinite(row["probability"]))
            self.assertTrue(0 <= row["probability"] <= 1)
            pairs.setdefault((row["market"], row["line"]), {})[row["selection"]] = row["probability"]
            if row["market"] == "cards":
                self.assertEqual(row["statistic"], "yellow_cards")
        for pair in pairs.values():
            self.assertAlmostEqual(pair["over"] + pair["under"], 1, places=12)
        for market, lines in THRESHOLDS.items():
            over = [pairs[market, line]["over"] for line in lines]
            self.assertEqual(over, sorted(over, reverse=True))

    def test_zero_observed_totals_generate_valid_probabilities(self):
        scores, events = samples(zero=True)
        result = run({"fixtures": [FIXTURE]}, scores, events, FREEZE)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(len(result["markets"]), 24)
        for row in result["markets"]:
            self.assertEqual(row["probability"], float(row["selection"] == "under"))

    def test_duplicate_observations_do_not_inflate_sample_thresholds(self):
        scores, events = samples(count=30)
        result = run({"fixtures": [FIXTURE]}, scores + scores, events + events, FREEZE)
        self.assertEqual(result["markets"], [])
        self.assertEqual(len(result["blockers"]), 4)
        self.assertTrue(all(row["league_n"] == 30 for row in result["blockers"]))
        self.assertEqual((MIN_LEAGUE, MIN_TEAM), (60, 8))

    def test_future_and_invalid_statistics_do_not_change_existing_forecasts(self):
        scores, events = samples()
        baseline = run({"fixtures": [FIXTURE]}, scores, events, FREEZE)
        future = dict(scores[0], fixture_id="future", home_goals=500,
                      published_at_utc="2026-11-07T10:00:00Z")
        premature = dict(scores[0], fixture_id="premature", home_goals=500,
                         published_at_utc="2024-01-01T10:00:00Z")
        bad_events = []
        for index, value in enumerate((True, .5, float("nan"), -1, 10**1000)):
            row = copy.deepcopy(events[0])
            row.update(match_date=f"invalid-{index}", events={market: [value, 0] for market in ("cards", "corners", "fouls")})
            bad_events.append(row)
        future_event = copy.deepcopy(events[0])
        future_event.update(match_date="future", published_at_utc="2026-11-07T10:00:00Z")
        actual = run({"fixtures": [FIXTURE]}, scores + [future, premature],
                     events + bad_events + [future_event], FREEZE)
        self.assertEqual(actual, baseline)

    def test_conflicting_duplicate_statistics_remove_the_observation(self):
        scores, events = samples()
        conflicting = copy.deepcopy(events[0])
        conflicting["events"] = {market: [999, 999] for market in ("cards", "corners", "fouls")}
        result = run({"fixtures": [FIXTURE]}, scores, events + [conflicting], FREEZE)
        self.assertEqual({row["market"] for row in result["markets"]}, {"goals"})
        self.assertEqual({row["market"] for row in result["blockers"]}, {"cards", "corners", "fouls"})
        self.assertTrue(all(row["league_n"] == 59 for row in result["blockers"]))

    def test_started_fixtures_never_generate_markets(self):
        scores, events = samples()
        fixture = dict(FIXTURE, kickoff_utc=FREEZE)
        self.assertEqual(run({"fixtures": [fixture]}, scores, events, FREEZE)["markets"], [])


class EloAndDixonContractTests(unittest.TestCase):
    def test_elo_1x2_normalization_and_invalid_draw_parameters(self):
        scores, _ = samples()
        forecast = predict_elo(scores, FIXTURE, frozen_at_utc=FREEZE)
        probabilities = [forecast[key] for key in ("p_home", "p_draw", "p_away")]
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities))
        self.assertAlmostEqual(sum(probabilities), 1, places=12)
        self.assertEqual(forecast["probability_status"], "uncalibrated_research")
        for value in (-.1, 1.1, float("nan"), float("inf"), True, None):
            with self.subTest(draw=value), self.assertRaises(ValueError):
                predict_elo(scores, FIXTURE, frozen_at_utc=FREEZE, draw_base=value)

    def test_duplicate_scores_do_not_satisfy_elo_team_gate(self):
        scores, _ = samples(count=1)
        with self.assertRaisesRegex(ValueError, "insufficient_verified_team_history"):
            predict_elo(scores * 60, FIXTURE, frozen_at_utc=FREEZE)

    def test_score_contradictions_and_premature_publications_are_excluded(self):
        scores, _ = samples(count=6)
        conflict = dict(scores[0], home_goals=9)
        premature = dict(scores[1], fixture_id="premature", published_at_utc="2020-01-01T00:00:00Z")
        rows = eligible_history(scores + [conflict, premature], frozen_at_utc=FREEZE)
        self.assertEqual(len(rows), 5)
        self.assertNotIn(scores[0], rows)

    def test_large_finite_elo_advantage_does_not_overflow_logistic(self):
        scores, _ = samples(count=10)
        ratings, counts = train_elo(scores, frozen_at_utc=FREEZE, home_advantage=-1e100)
        self.assertTrue(all(math.isfinite(value) for value in ratings.values()))
        self.assertEqual(counts["Premier League", "A"], 10)

    def test_dixon_only_repairs_rounding_not_invalid_distributions(self):
        valid = normalize_dixon_probabilities({"home_win": .4333, "draw": .2666, "away_win": .3000})
        self.assertAlmostEqual(sum(valid), 1, places=12)
        for values in ((0, 0, 0), (1, 1, 1), (2, 0, 0), (True, 0, 0),
                       (float("nan"), 0, 1), (float("inf"), 0, 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_dixon_probabilities(dict(zip(("home_win", "draw", "away_win"), values)))


class EventParserProvenanceTests(unittest.TestCase):
    def test_observed_date_and_yellow_card_counts_remain_explicit(self):
        text = "Date,HomeTeam,AwayTeam,HY,AY,HR,AR\n01/09/2025,A,B,2,1,1,0\n"
        row = parse_events(text, "Premier League", FREEZE)[0]
        self.assertEqual(row["match_date"], "2025-09-01")
        self.assertEqual(row["source_provider"], "football-data.co.uk")
        self.assertEqual(row["events"]["cards"], [2, 1])
        self.assertEqual((row["home"], row["away"]), ("A", "B"))

    def test_source_identity_matches_final_score_parser_and_rejects_other_division(self):
        text = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC\nE0,01/09/2025,A,B,2,1,5,3\nD1,02/09/2025,C,D,1,1,2,4\n"
        events = parse_events(text, "Premier League", FREEZE, league_code="E0", season="2526")
        scores = parse_csv(text, league_code="E0", season="2526", observed_at_utc=FREEZE)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["fixture_id"], scores[0]["fixture_id"])
        self.assertEqual(events[0]["source_record_id"], scores[0]["source_record_id"])
        self.assertEqual((events[0]["country_code"], events[0]["league_code"]), ("ENG", "E0"))
        with self.assertRaisesRegex(ValueError, "league_code_conflict"):
            parse_events(text, "Bundesliga", FREEZE, league_code="E0", season="2526")

    def test_naive_observation_time_fails_before_parsing(self):
        with self.assertRaisesRegex(ValueError, "timezone_required"):
            parse_events("Date,HomeTeam,AwayTeam\n", "Premier League", "2026-11-06T10:00:00")
