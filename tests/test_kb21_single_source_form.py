"""Actual finished API team history, no fabricated original KB21 sport scores."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
import json
import tempfile
from pathlib import Path

from tools.kb21_single_source_calendar import build as calendar, DAY_SCHEMA
from tests.test_kb21_single_source_calendar import fake, NOW, TODAY, TOMORROW, fixture, wrapper, MockClient
from tools.kb21_single_source_form import shortlist, build_source_pack, _history, render_pdf

def base_calendar():
    source = calendar(now=NOW, client=fake(), key="testing")
    return {
        k: v for k, v in source.items() if k != "days"
    }, {row["date"]: json.loads(json.dumps(row)) for row in source["days"]}


def match_record(ident, team, days_ago=2):
    dt = NOW - timedelta(days=days_ago)
    return {
        "fixture": {
            "id": ident, "date": dt.isoformat(),
            "status": {"short": "FT"},
        },
        "teams": {
            "home": {"id": team, "name": "Selected FC"},
            "away": {"id": team + 1000, "name": "Opponent FC"},
        },
        "goals": {"home": 2, "away": 1},
    }


def past_response(team):
    rows = [match_record(team * 100 + i, team, i + 2) for i in range(10)]
    return {"errors": [], "results": len(rows), "response": rows}


class TeamsClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
    def get(self, base, key, endpoint, **params):
        self.calls.append((endpoint, params))
        if endpoint != "fixtures" or set(params) != {"team", "last"}:
            raise AssertionError("Unexpected extra source")
        if params["last"] != 12:
            raise AssertionError("Expected bounded last12 history")
        team = params["team"]
        if self.fail:
            return {"errors": {"request": "invalid"}, "response": []}, {}
        return past_response(team), {}


class RealFormTests(unittest.TestCase):
    def test_same_provider_real_goal_history_without_scoring(self):
        m, docs = base_calendar()
        client = TeamsClient()
        result = build_source_pack(m, docs, client, "key", now=NOW)
        self.assertEqual(result["dates"], [TODAY, TOMORROW])
        self.assertEqual(result["historical_form_sampled"], 2)
        self.assertEqual(result["api_team_history_calls"], 2)
        self.assertEqual(len(client.calls), 2)  # Same two teams in both games
        self.assertTrue(all(x[0] == "fixtures" for x in client.calls))
        self.assertFalse(result["safe_to_publish_play"])
        self.assertFalse(result["kb21_n_written"])
        self.assertEqual(result["scoring_fields_filled_automatically"], 0)
        for day in result["days"]:
            row = day["matches"][0]
            self.assertTrue(row["both_sides_have_factual_goal_rates"])
            self.assertEqual(row["history"]["home"]["last_completed_games"]
                             ["sample_size"], 10)
            self.assertEqual(row["history"]["home"]["last_completed_games"]
                             ["goals_for_per_match"], 2.0)
            self.assertEqual(row["history"]["away"]["last_completed_games"]
                             ["goals_against_per_match"], 1.0)
            self.assertIsNone(row["analyst_assessment"]["sport_score_0_100"])
            self.assertIsNone(row["analyst_assessment"]["P_model_pre_odds"])
            self.assertEqual(row["form_metric"],
                             "ACTUAL_COMPLETED_MATCH_GOALS_NOT_XG")

    def test_shadow_probabilities_reuse_existing_diagnostic_not_kb21_pmodel(self):
        from tools.kb21_api_diagnostic import diagnose
        m, docs = base_calendar()
        result = build_source_pack(m, docs, TeamsClient(), "key", now=NOW)
        self.assertEqual(result["shadow_goal_forecasts_prepared"], 2)
        self.assertEqual(result["scoring_fields_filled_automatically"], 0)
        self.assertFalse(result["safe_to_publish_play"])
        for day in result["days"]:
            for match in day["matches"]:
                rates = {
                    side: match["history"][side]["last_completed_games"]
                    for side in ("home", "away")
                }
                expected = diagnose({"api_goal_rates": rates})
                shadow = match["experimental_goal_model"]
                self.assertEqual(shadow["diagnostic_probabilities"],
                                 expected["diagnostic_probabilities"])
                self.assertEqual(shadow["goal_rate_estimates"],
                                 expected["goal_rate_estimates"])
                self.assertEqual(shadow["status"], "EXPLORATORY_API_ONLY")
                self.assertIsNone(shadow["p_model"])
                self.assertIsNone(shadow["original_kb21_p_model"])
                self.assertFalse(shadow["model_is_historically_validated"])
                self.assertEqual(shadow["role"],
                                 "SHADOW_CALIBRATION_ONLY_NOT_KB21_P_MODEL")
                self.assertIsNone(match["analyst_assessment"]["P_model_pre_odds"])
                self.assertIsNone(match["analyst_assessment"]["sport_score_0_100"])
                self.assertIsNone(match["selection"])
                self.assertIsNone(match["odds"])
                self.assertFalse(match["freeze_allowed"])

    def test_missing_team_history_has_no_experimental_probability(self):
        m, docs = base_calendar()
        class SparseTeamsClient(TeamsClient):
            def get(self, base, key, endpoint, **params):
                if params.get("team") == 2:
                    return {"errors": [], "results": 0, "response": []}, {}
                return super().get(base, key, endpoint, **params)
        result = build_source_pack(m, docs, SparseTeamsClient(), "key", now=NOW)
        self.assertEqual(result["shadow_goal_forecasts_prepared"], 0)
        for day in result["days"]:
            record = day["matches"][0]
            self.assertFalse(record["both_sides_have_factual_goal_rates"])
            self.assertEqual(record["experimental_goal_model"]["status"],
                             "INSUFFICIENT_HISTORY")
            self.assertIsNone(record["experimental_goal_model"]["p_model"])
            self.assertNotIn("diagnostic_probabilities",
                             record["experimental_goal_model"])

    def test_stale_or_modified_fixture_can_not_gain_history(self):
        m, docs = base_calendar()
        docs[TODAY]["candidates"][0]["home"] = "Other FC"
        with self.assertRaisesRegex(ValueError, "not identical"):
            shortlist(m, docs, now=NOW)
        m, docs = base_calendar()
        docs[TODAY]["single_source_gate"] = "BLOCKED"
        with self.assertRaisesRegex(ValueError, "integrity error"):
            shortlist(m, docs, now=NOW)
        m, docs = base_calendar()
        m["provider_count"] = 2
        with self.assertRaisesRegex(ValueError, "two signed"):
            shortlist(m, docs, now=NOW)

    def test_after_kickoff_never_queries_finished_game(self):
        m, docs = base_calendar()
        now = datetime(2026, 10, 19, 19, tzinfo=timezone.utc)
        client = TeamsClient()
        result = build_source_pack(m, docs, client, "key", now=now)
        self.assertEqual(result["historical_form_sampled"], 0)
        self.assertEqual(client.calls, [])
        self.assertFalse(result["safe_to_publish_play"])

    def test_api_history_failure_never_equals_empty_source(self):
        m, docs = base_calendar()
        with self.assertRaisesRegex(ValueError, "history request failed"):
            build_source_pack(m, docs, TeamsClient(fail=True), "key", now=NOW)

    def test_source_not_completed_goals_is_not_fake_history(self):
        cutoff = NOW
        record = match_record(3, 1)
        record["fixture"]["status"]["short"] = "NS"
        p = {"errors": [], "results": 1, "response": [record]}
        self.assertIsNone(_history(p, 1, cutoff + timedelta(days=2), cutoff))
        record["fixture"]["status"]["short"] = "FT"
        record["fixture"]["date"] = (NOW + timedelta(days=1)).isoformat()
        p = {"errors": [], "results": 1, "response": [record]}
        with self.assertRaisesRegex(ValueError, "future/late"):
            _history(p, 1, cutoff + timedelta(days=2), cutoff)

    def test_shortlist_does_not_select_out_of_provider(self):
        m, docs = base_calendar()
        phantom = deepcopy(docs[TODAY]["candidates"][0])
        phantom["fixture_id"] = 9999
        docs[TODAY]["candidates"].append(phantom)
        docs[TODAY]["pre_match_fixtures"] += 1
        with self.assertRaisesRegex(ValueError, "not identical"):
            shortlist(m, docs, now=NOW)

    def test_compact_actual_data_pdf_contains_no_automated_betting_score(self):
        m, docs = base_calendar()
        form = build_source_pack(m, docs, TeamsClient(), "key", now=NOW)
        with tempfile.TemporaryDirectory() as folder:
            for entry in form["days"]:
                pdf = Path(folder) / ("KB21_FORM_" + entry["day"] + ".pdf")
                render_pdf(entry, pdf)
                self.assertTrue(pdf.exists())
                self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
                self.assertGreater(pdf.stat().st_size, 1800)
                for x in entry["matches"]:
                    self.assertEqual(x["experimental_goal_model"]["status"],
                                     "EXPLORATORY_API_ONLY")
                    self.assertIsNone(x["analyst_assessment"]["P_model_pre_odds"])
                    self.assertIsNone(x["analyst_assessment"]["sport_score_0_100"])

    def test_cap_is_strict_and_deterministic(self):
        m, docs = base_calendar()
        doc = docs[TOMORROW]
        template = deepcopy(doc["candidates"][0])
        for i in range(2, 12):
            e = deepcopy(template)
            e["fixture_id"] = 1000 + i
            e["home"] = "Home" + str(i)
            e["away"] = "Away" + str(i)
            e["home_team_id"] = 200 + i
            e["away_team_id"] = 300 + i
            doc["provider_events"].append(e)
            doc["candidates"].append(e)
        doc["pre_match_fixtures"] = len(doc["candidates"])
        doc["provider_total_events"] = len(doc["provider_events"])
        selected = shortlist(m, docs, now=NOW)
        self.assertEqual(selected[1]["shortlisted_for_real_team_history"], 5)
        self.assertEqual(selected[1]["skipped_from_shortlist"], 6)
        with self.assertRaises(ValueError):
            shortlist(m, docs, now=NOW, max_per_day=100)

if __name__ == "__main__":
    unittest.main()
