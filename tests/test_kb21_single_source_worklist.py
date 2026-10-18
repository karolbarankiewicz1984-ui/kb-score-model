"""The two-day KB21 worklist must preserve every provider candidate, with no PLAY."""
from copy import deepcopy
from datetime import timedelta
import unittest

from tests.test_kb21_single_source_form import base_calendar, TeamsClient, NOW
from tools.kb21_single_source_form import build_source_pack
from tools.kb21_single_source_worklist import build, render_day


def inputs():
    manifest, calendars = base_calendar()
    form = build_source_pack(manifest, calendars, TeamsClient(), "test", now=NOW)
    form_manifest = {key: value for key, value in form.items() if key != "days"}
    forms = {item["day"]: item for item in form["days"]}
    return manifest, calendars, form_manifest, forms


class WorklistTests(unittest.TestCase):
    def test_every_candidate_is_preserved_with_no_model_scores(self):
        m, c, fm, forms = inputs()
        report = build(m, c, fm, forms)
        self.assertEqual(report["total_candidates"], 2)
        self.assertEqual(report["total_with_factual_goal_history"], 2)
        self.assertEqual(report["automatic_p_model_count"], 0)
        self.assertEqual(report["automatic_play_count"], 0)
        self.assertFalse(report["register_writes"])
        self.assertEqual(report["kb21_n_effect"], 0)
        for day in report["days"]:
            self.assertEqual(len(day["records"]), 1)
            row = day["records"][0]
            self.assertEqual(row["status"], "AWAITING_HUMAN_PREMARKET_ASSESSMENT")
            self.assertTrue(row["factual_goal_history_available"])
            self.assertIsNone(row["assessment_template"]["p_model"])
            self.assertIsNone(row["assessment_template"]["freeze_at"])
            self.assertIsNone(row["sport_score"])
            self.assertIsNone(row["original_kb21_p_model"])
            self.assertIsNone(row["decision"])
            self.assertFalse(row["safe_to_publish_play"])
            self.assertIn("NO PLAY", render_day(day))

    def test_not_just_the_bounded_five_form_matches(self):
        m, c, fm, forms = inputs()
        day = m["dates"][1]
        source = deepcopy(c[day]["candidates"][0])
        source["fixture_id"] += 789
        source["home"] = "Other Home"
        source["away"] = "Other Away"
        source["home_team_id"] = 982
        source["away_team_id"] = 983
        c[day]["provider_events"].append(source)
        c[day]["candidates"].append(source)
        c[day]["pre_match_fixtures"] += 1
        c[day]["provider_total_events"] += 1
        report = build(m, c, fm, forms)
        self.assertEqual(report["total_candidates"], 3)
        other = report["days"][1]["records"][1]
        self.assertFalse(other["factual_goal_history_available"])
        self.assertIsNone(other["factual_goal_history_not_xg"])
        self.assertIsNone(other["assessment_template"]["market"])

    def test_refuse_foreign_candidate(self):
        m, c, fm, forms = inputs()
        c[m["dates"][0]]["candidates"][0]["home"] = "Altered Club"
        with self.assertRaisesRegex(ValueError, "not identical"):
            build(m, c, fm, forms)

    def test_refuse_promoted_history_derived_pmodel(self):
        m, c, fm, forms = inputs()
        forms[m["dates"][0]]["matches"][0]["analyst_assessment"]["P_model_pre_odds"] = .95
        with self.assertRaisesRegex(ValueError, "contaminated"):
            build(m, c, fm, forms)

    def test_refuse_spliced_history_fixture(self):
        m, c, fm, forms = inputs()
        forms[m["dates"][0]]["matches"][0]["home_team_id"] = 99999
        with self.assertRaisesRegex(ValueError, "not in provider"):
            build(m, c, fm, forms)

    def test_refuse_auto_scoring_promotion(self):
        m, c, fm, forms = inputs()
        fm["scoring_fields_filled_automatically"] = 1
        with self.assertRaisesRegex(ValueError, "promoted"):
            build(m, c, fm, forms)

    def test_refuse_multi_source_gate(self):
        m, c, fm, forms = inputs()
        m["provider_count"] = 2
        with self.assertRaisesRegex(ValueError, "multi-source"):
            build(m, c, fm, forms)

    def test_late_creation_never_allows_retroactive_freeze(self):
        m, c, fm, forms = inputs()
        fm["generated_at_utc"] = (NOW + timedelta(days=10)).isoformat()
        report = build(m, c, fm, forms)
        self.assertTrue(all(
            row["status"] == "KICKOFF_PASSED_NO_LATE_FREEZE"
            for day in report["days"] for row in day["records"]))
        self.assertEqual(report["automatic_play_count"], 0)


if __name__ == "__main__":
    unittest.main()
