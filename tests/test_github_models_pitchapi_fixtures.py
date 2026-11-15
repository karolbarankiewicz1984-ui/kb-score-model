import json
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from github_models.pitchapi_fixtures import collect, SCHEMA
from github_models.reviewed_resolver import resolve_reviewed

NOW = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)


def match(identity="m1", kickoff="2026-11-06T16:00:00Z", **changes):
    result = dict(id=identity, time_utc=kickoff,
                  league=dict(id="l_4WFCIZ", name="Premier League"),
                  home_team=dict(id="t_cov", name="Coventry City"),
                  away_team=dict(id="t_hull", name="Hull City"))
    result.update(changes)
    return result


def client_for(matches, metadata=None):
    client = SimpleNamespace(date=SimpleNamespace(get=Mock(return_value=SimpleNamespace(matches=matches))),
                             leagues=SimpleNamespace(get=Mock(return_value=metadata or dict(id="l_4WFCIZ", name="Premier League", country_code="ENG"))))
    return client


class ResearchPitchapiCollectorTests(unittest.TestCase):
    def collect_one(self, client, **kwargs):
        return collect(client, start_date="2026-11-06", days=1, clock=lambda: NOW, **kwargs)[0]

    def test_uncapped_fixture_only_collection_preserves_provider_identity(self):
        client = client_for([match("m" + str(i)) for i in range(125)])
        payload = self.collect_one(client)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["source_status"], "ok")
        self.assertEqual(payload["available_upcoming"], 125)
        self.assertEqual(payload["fixtures_collected"], 125)
        self.assertEqual(client.date.get.call_args.args, ("2026-11-06",))
        self.assertEqual(client.date.get.call_args.kwargs, dict(status="upcoming"))
        client.leagues.get.assert_called_once_with("l_4WFCIZ")
        row = payload["fixtures"][0]
        self.assertEqual((row["home_team_id"], row["away_team_id"]), ("t_cov", "t_hull"))
        self.assertEqual((row["raw_home"], row["home"]), ("Coventry City", "Coventry City"))
        self.assertNotIn("home_recent", row)
        self.assertFalse(payload["xg_context_collected"])

    def test_current_three_days_and_cached_metadata(self):
        client = client_for([])
        client.date.get.side_effect = [SimpleNamespace(matches=[match("m" + str(i), f"2026-11-0{6+i}T16:00:00Z")]) for i in range(3)]
        payloads = collect(client, clock=lambda: NOW)
        self.assertEqual([p["target_date"] for p in payloads], ["2026-11-06", "2026-11-07", "2026-11-08"])
        self.assertEqual(client.date.get.call_count, 3)
        self.assertEqual(client.leagues.get.call_count, 1)
        self.assertEqual([p["fixtures_collected"] for p in payloads], [1, 1, 1])

    def test_snapshot_follows_all_responses_and_excludes_games_starting_during_fetch(self):
        observations = iter([NOW, NOW, NOW, NOW.replace(hour=9), NOW.replace(hour=10)])
        payload = collect(client_for([match(kickoff="2026-11-06T09:30:00Z")]), days=1,
                          clock=lambda: next(observations))[0]
        self.assertEqual(payload["snapshot_utc"], "2026-11-06T10:00:00Z")
        self.assertEqual(payload["fixtures_collected"], 0)
        self.assertEqual(payload["exclusions"], dict(not_future_at_observation=1))

    def test_date_errors_are_diagnostic_not_empty_calendar(self):
        client = client_for([])
        client.date.get.side_effect = RuntimeError("secret_api_key_should_not_escape")
        payload = self.collect_one(client)
        self.assertEqual(payload["source_status"], "source_error")
        self.assertIsNone(payload["available_upcoming"])
        self.assertEqual(payload["errors"], [dict(operation="date_fixtures", query_date="2026-11-06", error_type="RuntimeError")])
        self.assertNotIn("secret_api_key", json.dumps(payload))
        client.leagues.get.assert_not_called()

    def test_metadata_error_is_explicit_and_known_registry_can_resolve(self):
        client = client_for([match()])
        client.leagues.get.side_effect = RuntimeError("private-token")
        payload = self.collect_one(client)
        self.assertEqual(payload["source_status"], "ok")
        self.assertEqual(payload["league_metadata"]["l_4WFCIZ"]["status"], "error")
        row = payload["fixtures"][0]
        self.assertIsNone(row["country_code"])
        self.assertEqual(row["country_identity_source"], "missing_provider_metadata")
        self.assertNotIn("private-token", json.dumps(payload))
        resolved = resolve_reviewed(row, [dict(league="Premier League", home="Coventry", away="Hull")])
        self.assertEqual(resolved["country_code"], "ENG")

    def test_metadata_missing_country_is_not_fabricated(self):
        payload = self.collect_one(client_for([match()], metadata=dict(id="l_4WFCIZ", name="Premier League")))
        self.assertIsNone(payload["fixtures"][0]["country_code"])
        self.assertEqual(payload["fixtures"][0]["identity_blockers"], [])

    def test_metadata_country_alpha2_is_preserved(self):
        item = match(league=dict(id="l_1Isor4", name="Bundesliga"))
        row = self.collect_one(client_for([item], metadata=dict(id="l_1Isor4", name="Bundesliga", country_code="DE")))["fixtures"][0]
        self.assertEqual(row["country_code"], "DE")
        self.assertEqual(row["identity_blockers"], [])

    def test_metadata_identifier_name_and_country_conflicts_remain_blocked(self):
        cases = [
            (dict(id="l_wrong", name="Premier League", country_code="ENG"), "league_metadata_id_conflict"),
            (dict(id="l_4WFCIZ", name="Championship", country_code="ENG"), "league_metadata_name_conflict"),
            (dict(id="l_4WFCIZ", name="Premier League", country_code="RUS"), "competition_country_conflict"),
        ]
        for detail, blocker in cases:
            with self.subTest(detail=detail):
                row = self.collect_one(client_for([match()], metadata=detail))["fixtures"][0]
                self.assertIn(blocker, row["identity_blockers"])
                with self.assertRaisesRegex(ValueError, "provider_identity_blocked"):
                    resolve_reviewed(row, [dict(league="Premier League", home="Coventry", away="Hull")])

    def test_embedded_and_detail_country_conflict(self):
        item = match(league=dict(id="l_4WFCIZ", name="Premier League", country_code="RUS"))
        row = self.collect_one(client_for([item]))["fixtures"][0]
        self.assertIn("league_metadata_country_conflict", row["identity_blockers"])

    def test_duplicate_or_invalid_fixtures_make_source_partial(self):
        for matches in ([match(), match(away_team=dict(id="t_other", name="Other"))], [match(home_team=dict(name="Coventry City"))]):
            with self.subTest(matches=matches):
                payload = self.collect_one(client_for(matches))
                self.assertEqual(payload["source_status"], "partial")
                self.assertTrue(payload["errors"])

    def test_cross_midnight_utc_fixture_is_rebucketed_to_warsaw_day(self):
        client = client_for([])
        client.date.get.side_effect = [SimpleNamespace(matches=[match(kickoff="2026-11-06T23:30:00Z")]),
                                      SimpleNamespace(matches=[]), SimpleNamespace(matches=[])]
        payloads = collect(client, clock=lambda: NOW)
        self.assertEqual([p["fixtures_collected"] for p in payloads], [0, 1, 0])
        self.assertEqual(payloads[1]["fixtures"][0]["provider_query_date"], "2026-11-06")
        self.assertEqual(payloads[1]["fixtures"][0]["provider_response_received_at_utc"], "2026-11-06T08:00:00Z")

    def test_warsaw_midnight_can_require_four_utc_queries(self):
        midnight = NOW.replace(day=5, hour=23, minute=30)
        client = client_for([])
        payloads = collect(client, clock=lambda: midnight)
        self.assertEqual([call.args[0] for call in client.date.get.call_args_list],
                         ["2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"])
        self.assertEqual([p["target_date"] for p in payloads], ["2026-11-06", "2026-11-07", "2026-11-08"])

    def test_consistent_duplicates_across_date_lists_are_deduplicated(self):
        client = client_for([])
        item = match(kickoff="2026-11-06T23:30:00Z")
        client.date.get.side_effect = [SimpleNamespace(matches=[item]), SimpleNamespace(matches=[item]), SimpleNamespace(matches=[])]
        payloads = collect(client, clock=lambda: NOW)
        self.assertEqual([p["fixtures_collected"] for p in payloads], [0, 1, 0])
        self.assertEqual(payloads[1]["available_upcoming"], 1)
        self.assertEqual(payloads[1]["source_status"], "ok")
        self.assertEqual(payloads[1]["exclusions"], dict(duplicate_consistent_provider_fixture=1))

    def test_clock_cannot_precede_a_used_source_response(self):
        observations = iter([NOW, NOW, NOW, NOW.replace(hour=10), NOW.replace(hour=9)])
        payload = collect(client_for([match()]), days=1, clock=lambda: next(observations))[0]
        self.assertEqual(payload["source_status"], "source_error")
        self.assertEqual(payload["fixtures_collected"], 0)
        self.assertEqual(payload["errors"], [dict(operation="observation_clock_order", error_type="ValueError")])

    def test_historical_and_outside_seven_day_requests_rejected_before_api_calls(self):
        client = client_for([])
        for kwargs in (dict(start_date="2026-11-05"), dict(start_date="2026-11-12", days=2), dict(days=8)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                collect(client, clock=lambda: NOW, **kwargs)
        client.date.get.assert_not_called()


    def test_seven_day_horizon_reaches_following_saturday_without_late_leakage(self):
        sunday = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        client = client_for([])
        future = match(identity="saturday", kickoff="2026-11-21T17:30:00Z")
        client.date.get.side_effect = [
            SimpleNamespace(matches=[future] if day == 21 else [])
            for day in range(15, 22)
        ]
        snapshots = collect(client, start_date="2026-11-15", days=7,
                            clock=lambda: sunday)
        self.assertEqual(len(snapshots), 7)
        self.assertEqual([s["target_date"] for s in snapshots],
                         [f"2026-11-{day:02d}" for day in range(15, 22)])
        self.assertEqual([s["fixtures_collected"] for s in snapshots],
                         [0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(snapshots[-1]["fixtures"][0]["pitch_match_id"],
                         "saturday")
        self.assertEqual(client.date.get.call_count, 7)
        self.assertEqual(client.leagues.get.call_count, 1)


    def test_invalid_today_row_does_not_poison_verified_saturday(self):
        sunday = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        broken = match(identity="bad", kickoff="2026-11-15T17:00:00Z",
                       home_team=dict(name="No ID"))
        saturday = match(identity="sat", kickoff="2026-11-21T17:30:00Z")
        client = client_for([])
        client.date.get.side_effect = [
            SimpleNamespace(matches=[broken] if day == 15 else
                            [saturday] if day == 21 else [])
            for day in range(15, 22)
        ]
        snapshots = collect(client, start_date="2026-11-15", days=7,
                            clock=lambda: sunday)
        self.assertEqual(snapshots[0]["source_status"], "partial")
        self.assertEqual(snapshots[0]["fixtures_collected"], 0)
        self.assertTrue(all(p["source_status"] == "ok" for p in snapshots[1:]))
        self.assertEqual(snapshots[-1]["fixtures_collected"], 1)
        self.assertEqual(snapshots[-1]["fixtures"][0]["pitch_match_id"], "sat")


    def test_one_failed_utc_query_does_not_hide_saturday(self):
        sunday = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        client = client_for([])
        sat = match(identity="sat", kickoff="2026-11-21T17:30:00Z")
        def source(day, *, status):
            if day == "2026-11-15":
                raise RuntimeError("unavailable")
            return SimpleNamespace(matches=[sat] if day == "2026-11-21" else [])
        client.date.get.side_effect = source
        snapshots = collect(client, days=7, start_date="2026-11-15",
                            clock=lambda: sunday)
        self.assertEqual([p["source_status"] for p in snapshots],
                         ["source_error", "source_error", "ok", "ok", "ok", "ok", "ok"])
        self.assertEqual(snapshots[-1]["fixtures_collected"], 1)
        self.assertEqual(snapshots[0]["errors"][0]["query_date"], "2026-11-15")
        self.assertNotIn("date_fixtures", json.dumps(snapshots[-1]["errors"]))

    def test_unparseable_kickoff_blocks_possible_two_local_dates_only(self):
        sunday = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        broken = match(identity="bad", kickoff="unparseable")
        saturday = match(identity="sat", kickoff="2026-11-21T17:30:00Z")
        client = client_for([])
        client.date.get.side_effect = [
            SimpleNamespace(matches=[broken] if day == 15 else
                            [saturday] if day == 21 else [])
            for day in range(15, 22)
        ]
        snapshots = collect(client, start_date="2026-11-15", days=7,
                            clock=lambda: sunday)
        self.assertEqual([s["source_status"] for s in snapshots],
                         ["partial", "partial", "ok", "ok", "ok", "ok", "ok"])
        self.assertEqual(snapshots[-1]["fixtures_collected"], 1)

    def test_seven_day_midnight_horizon_can_span_eight_utc_dates(self):
        local_morning = NOW.replace(day=5, hour=23, minute=30)
        client = client_for([])
        snapshots = collect(client, days=7, clock=lambda: local_morning)
        self.assertEqual([p["target_date"] for p in snapshots],
                         [f"2026-11-{day:02d}" for day in range(6, 13)])
        self.assertEqual([call.args[0] for call in client.date.get.call_args_list],
                         [f"2026-11-{day:02d}" for day in range(5, 13)])

    def test_seven_day_source_failure_is_not_treated_as_empty_future_saturday(self):
        sunday = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        client = client_for([])
        def source(day, *, status):
            if day == "2026-11-21":
                raise ConnectionError("unavailable")
            return SimpleNamespace(matches=[])
        client.date.get.side_effect = source
        snapshots = collect(client, start_date="2026-11-15", days=7,
                            clock=lambda: sunday)
        saturday = snapshots[-1]
        self.assertEqual(saturday["source_status"], "source_error")
        self.assertIsNone(saturday["available_upcoming"])
        self.assertEqual(saturday["errors"][0]["query_date"], "2026-11-21")

    def test_timezone_is_required_for_the_observation_clock(self):
        with self.assertRaisesRegex(ValueError, "timezone_invalid"):
            collect(client_for([]), clock=lambda: NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
