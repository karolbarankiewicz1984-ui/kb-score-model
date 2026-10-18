"""Increase genuine KB21 team-form evidence while staying inside fixed API budgets."""
from copy import deepcopy
import unittest

from tests.test_kb21_single_source_form import base_calendar, TeamsClient, NOW
from tools.kb21_single_source_form import build_source_pack, shortlist


def many_games(extra_each=11):
    manifest, days = base_calendar()
    for day_index, day in enumerate(manifest["dates"]):
        original = days[day]["candidates"][0]
        for idx in range(extra_each):
            row = deepcopy(original)
            row["fixture_id"] = 10000 + 100*day_index + idx
            row["home"] = "Test Home " + str(day_index) + "/" + str(idx)
            row["away"] = "Test Away " + str(day_index) + "/" + str(idx)
            row["home_team_id"] = 10000 + 200*day_index + 2*idx
            row["away_team_id"] = 10000 + 200*day_index + 2*idx + 1
            days[day]["provider_events"].append(row)
            days[day]["candidates"].append(row)
        days[day]["provider_total_events"] = len(days[day]["provider_events"])
        days[day]["pre_match_fixtures"] = len(days[day]["candidates"])
    return manifest, days


class BudgetedHistoryTests(unittest.TestCase):
    def test_doubles_daily_coverage_explicitly(self):
        manifest, days = many_games()
        client = TeamsClient()
        result = build_source_pack(manifest, days, client, "secret", now=NOW,
                                   max_per_day=10, max_history_calls=40,
                                   quota_reserve=25)
        self.assertEqual(result["historical_form_sampled"], 20)
        self.assertEqual([len(d["matches"]) for d in result["days"]], [10, 10])
        self.assertLessEqual(result["api_team_history_calls"], 40)
        self.assertEqual(result["api_team_history_calls"], len(client.calls))
        self.assertEqual(result["fixtures_with_two_valid_goal_histories"], 20)
        self.assertEqual(result["shadow_goal_forecasts_prepared"], 20)
        self.assertEqual(result["scoring_fields_filled_automatically"], 0)
        self.assertFalse(result["kb21_n_written"])
        self.assertFalse(result["safe_to_publish_play"])
        self.assertEqual(result["api_history_query_budget"], 40)
        for block in result["days"]:
            for row in block["matches"]:
                self.assertIsNone(row["analyst_assessment"]["P_model_pre_odds"])
                self.assertIsNone(row["analyst_assessment"]["sport_score_0_100"])
                self.assertFalse(row["freeze_allowed"])

    def test_global_call_cap_never_overspends(self):
        manifest, days = many_games()
        client = TeamsClient()
        result = build_source_pack(manifest, days, client, "secret", now=NOW,
                                   max_per_day=10, max_history_calls=4,
                                   quota_reserve=0)
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(result["api_team_history_calls"], 4)
        self.assertEqual(result["history_fetch_stop_reason"], "HISTORY_CALL_BUDGET_REACHED")
        self.assertGreater(result["team_history_queries_skipped"], 0)
        self.assertEqual(result["historical_form_sampled"], 20)
        self.assertLess(result["fixtures_with_two_valid_goal_histories"], 20)
        self.assertFalse(result["safe_to_publish_play"])
        unavailable = [side["status"] for group in result["days"]
                       for match in group["matches"]
                       for side in match["history"].values()]
        self.assertIn("HISTORY_CALL_BUDGET_REACHED", unavailable)

    def test_full_37_candidate_calendar_within_live_call_budget(self):
        manifest, days = base_calendar()
        for day_index, extra in enumerate((6, 29)):
            day = manifest["dates"][day_index]
            original = days[day]["candidates"][0]
            for index in range(extra):
                match = deepcopy(original)
                match["fixture_id"] = 500000 + 100*day_index + index
                match["home"] = "Home " + str(day_index) + ":" + str(index)
                match["away"] = "Away " + str(day_index) + ":" + str(index)
                match["home_team_id"] = 100000 + 200*day_index + index*2
                match["away_team_id"] = 100000 + 200*day_index + index*2+1
                days[day]["provider_events"].append(match)
                days[day]["candidates"].append(match)
            days[day]["provider_total_events"] = len(days[day]["provider_events"])
            days[day]["pre_match_fixtures"] = len(days[day]["candidates"])
        client = TeamsClient()
        report = build_source_pack(manifest, days, client, "secret", now=NOW,
                                   max_per_day=30, max_history_calls=80,
                                   quota_reserve=25)
        self.assertEqual(report["historical_form_sampled"], 37)
        self.assertEqual([len(d["matches"]) for d in report["days"]], [7, 30])
        self.assertEqual(report["fixtures_with_two_valid_goal_histories"], 37)
        self.assertEqual(report["shadow_goal_forecasts_prepared"], 37)
        self.assertLessEqual(report["api_team_history_calls"], 80)
        self.assertEqual(report["api_team_history_calls"], len(client.calls))
        self.assertFalse(report["safe_to_publish_play"])

    def test_daily_provider_quota_reserve_prevents_followup_requests(self):
        manifest, days = many_games()
        class LowQuotaClient(TeamsClient):
            def get(self, *args, **kwargs):
                payload, headers = super().get(*args, **kwargs)
                remaining = 26 - len(self.calls)
                return payload, {"x-ratelimit-requests-remaining": str(remaining)}
        client = LowQuotaClient()
        result = build_source_pack(manifest, days, client, "secret", now=NOW,
                                   max_per_day=10, max_history_calls=40,
                                   quota_reserve=25)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result["api_daily_remaining_last_seen"], 25)
        self.assertEqual(result["history_fetch_stop_reason"],
                         "DAILY_API_QUOTA_RESERVE_REACHED")
        self.assertGreater(result["team_history_queries_skipped"], 0)
        self.assertEqual(result["shadow_goal_forecasts_prepared"], 0)

    def test_absent_quota_header_remains_bounded(self):
        manifest, days = many_games()
        client = TeamsClient()
        report = build_source_pack(manifest, days, client, "secret", now=NOW,
                                   max_per_day=12, max_history_calls=8)
        self.assertEqual(report["historical_form_sampled"], 24)
        self.assertEqual(report["api_team_history_calls"], 8)
        self.assertIsNone(report["api_daily_remaining_last_seen"])
        self.assertGreater(report["team_history_queries_skipped"], 0)

    def test_bad_quota_header_fails_closed(self):
        manifest, days = base_calendar()
        class BadQuota(TeamsClient):
            def get(self, *args, **kwargs):
                payload, _ = super().get(*args, **kwargs)
                return payload, {"x-ratelimit-requests-remaining": "UNRELIABLE"}
        with self.assertRaisesRegex(ValueError, "Unusable API daily"):
            build_source_pack(manifest, days, BadQuota(), "secret", now=NOW)

    def test_strict_limits_and_default_unchanged(self):
        manifest, days = many_games()
        selected = shortlist(manifest, days, now=NOW)
        self.assertEqual([len(x["games"]) for x in selected], [5, 5])
        selected = shortlist(manifest, days, now=NOW, max_per_day=10)
        self.assertEqual([len(x["games"]) for x in selected], [10, 10])
        for limit in (0, 31, True, 100):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    shortlist(manifest, days, now=NOW, max_per_day=limit)
        for value in (0, -1, 100, True, "40"):
            with self.subTest(budget=value):
                with self.assertRaisesRegex(ValueError, "max_history_calls"):
                    build_source_pack(manifest, days, TeamsClient(), "secret",
                                      now=NOW, max_history_calls=value)
        for value in (-1, True, 1001, "25"):
            with self.subTest(reserve=value):
                with self.assertRaisesRegex(ValueError, "quota_reserve"):
                    build_source_pack(manifest, days, TeamsClient(), "secret",
                                      now=NOW, quota_reserve=value)


if __name__ == "__main__":
    unittest.main()
