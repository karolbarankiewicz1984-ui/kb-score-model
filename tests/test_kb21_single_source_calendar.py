"""One API / two Warsaw dates. Provider errors fail closed, not 'zero games'."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tools.kb21_single_source_calendar import (
    _page, _event, analyst_inputs, build, collect_for_day, dates, write_report,
)

NOW = datetime(2026, 10, 18, 3, 26, tzinfo=timezone.utc)
TODAY, TOMORROW = "2026-10-18", "2026-10-19"


def fixture(ident, day=TODAY, kickoff="14:00", status="NS", league="Premier League",
            country="England", league_id=39):
    return {
        "fixture": {
            "id": ident, "date": day + "T" + kickoff + ":00+02:00",
            "status": {"short": status, "long": status},
        },
        "league": {"id": league_id, "name": league, "country": country,
                   "season": 2026, "round": "Regular Season - 8"},
        "teams": {
            "home": {"id": 1, "name": "Arsenal"},
            "away": {"id": 2, "name": "Chelsea"},
        },
    }


def wrapper(day, page, total, rows, errors=None):
    return {
        "get": "fixtures",
        "parameters": {
            "date": day, "timezone": "Europe/Warsaw", "page": str(page)},
        "errors": [] if errors is None else errors,
        "results": len(rows), "paging": {"current": page, "total": total},
        "response": deepcopy(rows),
    }


class MockClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, base, key, endpoint, **params):
        self.calls.append((base, key, endpoint, params))
        if endpoint != "fixtures":
            raise AssertionError("Unexpected second source / endpoint")
        k = params["date"], params.get("page", 1)
        if k not in self.responses:
            raise AssertionError("Missing mock page " + str(k))
        return deepcopy(self.responses[k]), {}


def fake():
    return MockClient({
        (TODAY, 1): wrapper(TODAY, 1, 1, [
            fixture(11),
            fixture(12, kickoff="01:00"),        # already started
            fixture(13, status="PST"),           # postponed
            fixture(14, league="Second Division", league_id=999), # out-of-scope
        ]),
        (TOMORROW, 1): wrapper(TOMORROW, 1, 1, [
            fixture(15, day=TOMORROW),
        ]),
    })


class SingleSourceCalendarTests(unittest.TestCase):
    def test_exactly_today_and_tomorrow_warsaw(self):
        self.assertEqual(dates(now=NOW), [TODAY, TOMORROW])
        self.assertEqual(dates(TODAY, now=NOW), [TODAY, TOMORROW])
        with self.assertRaisesRegex(ValueError, "TODAY"):
            dates("2026-10-17", now=NOW)
        with self.assertRaisesRegex(ValueError, "TODAY"):
            dates("2026-10-20", now=NOW)
        # UTC date late night already belongs to NEXT Warsaw date.
        self.assertEqual(dates(now=datetime(
            2026, 10, 18, 22, 30, tzinfo=timezone.utc)),
            [TOMORROW, "2026-10-20"])
        with self.assertRaisesRegex(ValueError, "Timezone-aware"):
            dates(now=datetime(2026, 10, 18, 1))

    def test_only_one_source_and_no_auto_score(self):
        client = fake()
        report = build(now=NOW, client=client, key="not-real")
        self.assertEqual(report["dates"], [TODAY, TOMORROW])
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all("page" not in r[3] for r in client.calls))
        self.assertEqual({r[2] for r in client.calls}, {"fixtures"})
        self.assertEqual({r[3]["timezone"] for r in client.calls},
                         {"Europe/Warsaw"})
        self.assertEqual(report["provider_count"], 1)
        self.assertEqual(report["single_source_gate"], "PASS_SOURCE")
        self.assertEqual(report["total_provider_events"], 5)
        self.assertEqual(report["total_research_candidates"], 2)
        self.assertFalse(report["safe_to_publish_play"])
        self.assertFalse(report["kb21_n_written"])
        self.assertEqual(report["legacy_149_missing_checks"],
                         "HISTORICAL_OLD_POLICY_NOT_REPAIRED")
        first = report["days"][0]
        self.assertEqual(first["pre_match_fixtures"], 1)
        reasons = {item["fixture_id"]: item["candidate_status"]
                   for item in first["provider_events"]}
        self.assertEqual(reasons[11], "CANDIDATE")
        self.assertEqual(reasons[12], "KICKOFF_ALREADY_STARTED")
        self.assertEqual(reasons[13], "NOT_SCHEDULED_STATUS_PST")
        self.assertEqual(reasons[14], "OUTSIDE_KB21_COMPETITION_SCOPE")
        self.assertEqual(first["candidates"][0]["fixture_id"], 11)
        inputs = analyst_inputs(first)
        self.assertEqual(inputs["pre_match_fixtures"], 1)
        self.assertEqual(inputs["source"], "API-Football")
        self.assertIsNone(inputs["candidates"][0]["p_model"])
        self.assertIsNone(inputs["candidates"][0]["kb21_sport_score"])
        self.assertEqual(inputs["candidates"][0]["api_goal_rates"], {})
        self.assertFalse(inputs["candidates"][0]["freeze_allowed"])

    def test_true_empty_response_is_valid_no_candidates_not_global_zero(self):
        source = MockClient({(TODAY, 1): wrapper(TODAY, 1, 0, [])})
        data = collect_for_day(TODAY, source, "key", NOW)
        self.assertEqual(data["single_source_gate"], "PASS_SOURCE")
        self.assertEqual(data["provider_total_events"], 0)
        self.assertEqual(data["pre_match_fixtures"], 0)
        self.assertTrue(data["not_in_provider_means_out_of_scope"])
        self.assertFalse(data["provider_coverage_completeness_claim"])

    def test_api_failure_never_converted_to_empty_schedule(self):
        source = MockClient({
            (TODAY, 1): wrapper(TODAY, 1, 1, [], errors={"token": "expired"}),
            (TOMORROW, 1): wrapper(TOMORROW, 1, 1, []),
        })
        with self.assertRaisesRegex(ValueError, "API error"):
            build(now=NOW, client=source, key="bad")
        with self.assertRaisesRegex(RuntimeError, "missing|Missing"):
            build(now=NOW, client=source, key="")
        self.assertEqual(len(source.calls), 1) # invalid first date halts second

    def test_lost_pagination_page_fails_the_entire_capture(self):
        source = MockClient({
            (TODAY, 1): wrapper(TODAY, 1, 2, [fixture(11)]),
            (TODAY, 2): wrapper(TODAY, 2, 3, [fixture(12)]),
        })
        with self.assertRaisesRegex(ValueError, "unexpectedly paginated"):
            collect_for_day(TODAY, source, "key", NOW)
        self.assertEqual(len(source.calls), 1)

    def test_bad_timezone_wrong_day_or_duplicate_fixtures_fail(self):
        p = wrapper(TODAY, 1, 1, [])
        p["parameters"]["timezone"] = "UTC"
        with self.assertRaisesRegex(ValueError, "wrong date/timezone"):
            _page(p, TODAY, 1)
        with self.assertRaisesRegex(ValueError, "wrong Warsaw day"):
            _event(fixture(15, day=TOMORROW), TODAY, NOW)
        source = MockClient({
            (TODAY, 1): wrapper(TODAY, 1, 1, [fixture(11), fixture(11)])
        })
        with self.assertRaisesRegex(ValueError, "duplicate ID"):
            collect_for_day(TODAY, source, "key", NOW)

    def test_missing_results_and_invalid_scheduled_fixture_fail_closed(self):
        p = wrapper(TODAY, 1, 1, [fixture(11)])
        del p["results"]
        with self.assertRaisesRegex(ValueError, "results count"):
            _page(p, TODAY, 1)
        bad = fixture(22)
        bad["teams"]["home"]["name"] = None
        with self.assertRaisesRegex(ValueError, "missing team names"):
            _event(bad, TODAY, NOW)
        invalid = fixture(23)
        invalid["fixture"]["date"] = "not-a-time"
        with self.assertRaisesRegex(ValueError, "invalid/wrong Warsaw day"):
            _event(invalid, TODAY, NOW)

    def test_two_day_artifacts_have_factual_read_only_inputs(self):
        r = build(now=NOW, client=fake(), key="key")
        with tempfile.TemporaryDirectory() as folder:
            write_report(r, folder)
            files = list(Path(folder).iterdir())
            self.assertEqual(len(files), 7) # 2 day json/md/input + manifest
            for day in (TODAY, TOMORROW):
                x = json.loads((Path(folder) / (
                    "KB21_INPUT_" + day + ".json")).read_text(encoding="utf-8"))
                self.assertFalse(x["register_writes"])
                self.assertFalse(x["safe_to_publish_play"])
                self.assertEqual(x["pre_match_fixtures"], 1)
                md = (Path(folder) / (
                    "KB21_API_CALENDAR_" + day + ".md")).read_text(encoding="utf-8")
                self.assertIn("API-Football", md)
                self.assertIn("API-Football", md)


if __name__ == "__main__":
    unittest.main()
