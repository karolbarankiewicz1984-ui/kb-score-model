"""KB21 factual match evidence, without invented rating or bookmaker data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from tools.kb21_form_evidence import evidence, side_note
from tests.test_kb21_single_source_form import (
    NOW, base_calendar, TeamsClient, build_source_pack,
)


def game(fid, days_ago, gf, ga, venue="home", status="FT", home_id=10, away_id=20):
    if venue == "home":
        goals = {"home": gf, "away": ga}
    else:
        goals = {"home": ga, "away": gf}
        home_id, away_id = away_id, home_id
    return {
        "fixture": {"id": fid, "date": (NOW - timedelta(days=days_ago)).isoformat(),
                    "status": {"short": status}},
        "teams": {"home": {"id": home_id, "name": "Team"},
                  "away": {"id": away_id, "name": "Other"}},
        "goals": goals,
    }


class EvidenceTests(unittest.TestCase):
    def test_last_five_ft_and_venue_split_are_factual(self):
        rows = [
            game(1, 1, 2, 0, "home"), game(2, 4, 0, 1, "away"),
            game(3, 8, 1, 1, "home"), game(4, 12, 3, 0, "home"),
            game(5, 16, 1, 2, "away"), game(6, 20, 1, 0, "away"),
        ]
        report = evidence(rows, 10, NOW)
        self.assertEqual(report["last_5_ft"]["games"], 5)
        self.assertEqual(report["last_5_ft"]["wins"], 2)
        self.assertEqual(report["last_5_ft"]["draws"], 1)
        self.assertEqual(report["last_5_ft"]["losses"], 2)
        self.assertEqual(report["last_5_ft"]["points_per_game"], 1.4)
        self.assertEqual(report["home_ft"]["games"], 3)
        self.assertEqual(report["away_ft"]["games"], 3)
        self.assertEqual(report["home_ft"]["goals_for_per_game"], 2.0)
        self.assertEqual(report["away_ft"]["goals_against_per_game"], 1.0)
        self.assertEqual(report["days_since_previous_kickoff"], 1.0)
        self.assertEqual(report["previous_ft_matches"][0]["fixture_id"], 1)
        self.assertEqual(report["previous_ft_matches"][0]["venue"], "home")
        self.assertIn("2W/1D/2L", side_note(report, "home"))
        self.assertTrue(report["venue_split_minimum_three"]["away"])
        for field in ("structural_strength_0_35", "current_quality_0_35",
                      "matchup_context_0_30", "original_p_model"):
            self.assertIsNone(report[field])
        self.assertTrue(report["data_is_pre_market"])
        self.assertFalse(report["safe_to_publish_play"])

    def test_second_team_away_result_is_reversed(self):
        one = game(11, 3, 2, 0, "home")
        report = evidence([one], 20, NOW)
        self.assertEqual(report["previous_ft_matches"][0]["result"], "L")
        self.assertEqual(report["previous_ft_matches"][0]["goals_for"], 0)
        self.assertEqual(report["previous_ft_matches"][0]["goals_against"], 2)
        self.assertEqual(report["previous_ft_matches"][0]["venue"], "away")

    def test_extra_time_is_excluded_from_90minute_form(self):
        rows = [game(21, 2, 4, 3, status="AET"),
                game(22, 5, 1, 0),
                game(23, 6, 1, 0, status="PEN")]
        report = evidence(rows, 10, NOW)
        self.assertEqual(report["last_10_ft"]["games"], 1)
        self.assertEqual(report["excluded"]["not_ft"], 2)
        self.assertIn("próbka zbyt mała", side_note(report, "home"))

    def test_no_ft_is_missing_not_automatic_zero(self):
        report = evidence([game(3, 1, 0, 0, status="NS")], 10, NOW)
        self.assertIsNone(report["last_5_ft"])
        self.assertIsNone(report["last_10_ft"])
        self.assertIsNone(report["days_since_previous_kickoff"])
        self.assertIn("brak zakończonych", side_note(report, "home"))

    def test_duplicate_history_id_is_refused(self):
        row = game(11, 2, 2, 1)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            evidence([row, deepcopy(row)], 10, NOW)

    def test_late_finished_data_refused(self):
        row = game(9, -1, 2, 1)
        with self.assertRaisesRegex(ValueError, "after evidence capture"):
            evidence([row], 10, NOW)

    def test_naive_kickoff_is_refused(self):
        row = game(9, 3, 2, 1)
        row["fixture"]["date"] = "2026-10-16T18:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            evidence([row], 10, NOW)

    def test_incomplete_scores_are_not_treated_as_zero(self):
        row = game(9, 3, 2, 1)
        row["goals"]["home"] = None
        report = evidence([row], 10, NOW)
        self.assertIsNone(report["last_10_ft"])
        self.assertEqual(report["excluded"]["missing_goals"], 1)

    def test_boolean_goals_are_not_real_scores(self):
        row = game(9, 3, 2, 1)
        row["goals"]["home"] = True
        report = evidence([row], 10, NOW)
        self.assertIsNone(report["last_10_ft"])

    def test_source_team_mismatch_is_not_fabricated(self):
        row = game(9, 3, 2, 1, home_id=22, away_id=23)
        report = evidence([row], 10, NOW)
        self.assertEqual(report["excluded"]["missing_team"], 1)
        self.assertIsNone(report["last_10_ft"])

    def test_recent_ft_only_and_sample_boundary(self):
        rows = [game(i+1, i+1, 1, 0) for i in range(12)]
        report = evidence(rows, 10, NOW)
        self.assertEqual(report["source_rows"], 12)
        self.assertEqual(report["ft_rows_used"], 10)
        self.assertEqual(len(report["previous_ft_matches"]), 10)
        with self.assertRaisesRegex(ValueError, "<=12"):
            evidence(rows + [game(50, 22, 1, 0)], 10, NOW)

    def test_integration_reuses_exact_two_api_calls_without_odds(self):
        manifest, docs = base_calendar()
        client = TeamsClient()
        run = build_source_pack(manifest, docs, client, "key", now=NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(run["api_team_history_calls"], 2)
        self.assertEqual(run["fixtures_with_two_preprice_sport_evidence_packs"], 2)
        self.assertEqual(run["scoring_fields_filled_automatically"], 0)
        for day in run["days"]:
            match = day["matches"][0]
            for side in ("home", "away"):
                data = match["history"][side]["sport_evidence"]
                self.assertEqual(data["source_endpoint"],
                                 "/fixtures?team=ID&last=12")
                self.assertEqual(data["last_5_ft"]["games"], 5)
                self.assertEqual(data["ft_rows_used"], 10)
                self.assertFalse(data["safe_to_publish_play"])
                self.assertIsNone(data["original_p_model"])
            self.assertIsNone(match["analyst_assessment"]["P_model_pre_odds"])
            self.assertFalse(match["freeze_allowed"])

    def test_invalid_time_and_team_identity_fail_closed(self):
        row = game(20, 2, 1, 0)
        row["teams"]["away"]["id"] = 10
        with self.assertRaisesRegex(ValueError, "team identity"):
            evidence([row], 10, NOW)
        with self.assertRaisesRegex(ValueError, "aware cutoff"):
            evidence([], 10, datetime(2026, 10, 18))

if __name__ == "__main__":
    unittest.main()
