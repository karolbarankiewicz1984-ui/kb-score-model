"""Signed mock fixtures exercise the signoff validator, NOT true official site verification."""
import copy
import unittest

from tools.kb21_calendar_signoff import validate, inventory_template
from tools.kb21_calendar_coverage import SCOPE
from tools.kb21_official_review import OFFICIAL_PAGES


def sample():
    date = "2026-10-18"
    status = [{"league": code, "status": "OK"} for code in SCOPE]
    q = {
        "days": [date],
        "source_status": {date: status},
        "fixtures": [{
            "date_warsaw": date, "fixture_id": "eng.1:111",
            "fixture": "Home FC - Away FC",
            "kickoff": "2026-10-18T18:00:00+02:00",
            "assessment": {"p_model": None}
        }]
    }
    rows = {
        code: {"organizer_url": url, "captured_at": "2026-10-17T13:00:00+02:00",
               "reviewer": "manual official reviewer", "full_day_checked": True,
               "confirmed_zero_matches": True, "fixtures": []}
        for code, url in OFFICIAL_PAGES.items()
    }
    rows["eng.1"]["fixtures"] = [{
        "home": "Home FC", "away": "Away FC",
        "kickoff": "2026-10-18T18:00:00+02:00"
    }]
    rows["eng.1"]["confirmed_zero_matches"] = False
    i = {"days": {date: rows}, "approval": {
        "reviewer": "final manual signoff", "approved_at": "2026-10-17T15:00:00+02:00",
        "attests_independent_official_review": True}}
    return q, i


class CalendarSignoffTests(unittest.TestCase):
    def test_complete_signed_official_inventory_manual_only(self):
        queue, inventory = sample()
        result = validate(queue, inventory)
        self.assertEqual(result["status"], "MANUALLY_APPROVED_CALENDAR")
        self.assertEqual(result["calendar_gate"], "PASS_MANUAL")
        self.assertTrue(result["manual_source_attestation"])
        self.assertFalse(result["safe_to_publish_play"])
        self.assertEqual(result["publication"], "DIAGNOSTIC / NO PLAY")
        self.assertIsNone(queue["fixtures"][0]["assessment"]["p_model"])

    def test_missing_signoff_never_autoclears(self):
        q, i = sample()
        i.pop("approval")
        result = validate(q, i)
        self.assertEqual(result["status"], "READY_FOR_MANUAL_APPROVAL")
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertTrue(result["ready_for_approval"])

    def test_missing_one_league_blocks_even_when_no_fixtures(self):
        q, i = sample()
        i["days"]["2026-10-18"].pop("bel.1")
        r = validate(q, i)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any("bel.1" in e for e in r["errors"]))

    def test_missing_game_blocks_false_completion(self):
        q, i = sample()
        i["days"]["2026-10-18"]["eng.1"]["fixtures"] = []
        r = validate(q, i)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any("FIXTURE_COUNT_DIFFERENCE" in e for e in r["errors"]))

    def test_empty_without_organizer_confirmation_blocks(self):
        q, i = sample()
        i["days"]["2026-10-18"]["bel.1"]["confirmed_zero_matches"] = None
        self.assertEqual(validate(q, i)["status"], "BLOCKED")

    def test_wrong_time_and_after_kickoff_capture_blocks(self):
        q, i = sample()
        i["days"]["2026-10-18"]["eng.1"]["fixtures"][0]["kickoff"] = "2026-10-18T20:00:00+02:00"
        self.assertIn("MATCH_IDENTITY_OR_TIME_DISAGREEMENT",
                      " ".join(validate(q, i)["errors"]))
        q, i = sample()
        i["days"]["2026-10-18"]["eng.1"]["captured_at"] = "2026-10-18T19:00:00+02:00"
        self.assertEqual(validate(q, i)["status"], "BLOCKED")

    def test_esports_source_failure_and_unnamed_reviewer_block(self):
        q, i = sample()
        q["source_status"]["2026-10-18"][0]["status"] = "ERROR"
        i["days"]["2026-10-18"]["ita.1"]["reviewer"] = ""
        self.assertEqual(validate(q, i)["status"], "BLOCKED")

    def test_template_keeps_every_competition_unapproved(self):
        from tools.kb21_official_review import build as review_build
        from tools.kb21_calendar_coverage import CORE, SCOPE
        coverage = {"days": {"2026-10-18": {
            "core_leagues": [{"league_id": key, "status": "ESPN_SOURCE_STATUS_UNKNOWN",
                              "espn_candidates": 0, "independent_provider_candidates": None,
                              "crossmatched": 0} for key in CORE],
            "other_competitions": []
        }}}
        template = inventory_template(review_build(coverage))
        self.assertEqual(len(template["days"]["2026-10-18"]), len(SCOPE))
        self.assertIsNone(template["approval"])
        self.assertIsNone(template["days"]["2026-10-18"]["eng.1"]["captured_at"])
        self.assertFalse(template["days"]["2026-10-18"]["eng.1"]["full_day_checked"])

    def test_date_mismatch_fails(self):
        q, i = sample()
        i["days"]["2026-10-19"] = copy.deepcopy(i["days"]["2026-10-18"])
        self.assertEqual(validate(q, i)["status"], "BLOCKED")


    def test_official_club_alias_does_not_falsely_block(self):
        q, i = sample()
        q["fixtures"][0]["fixture"] = "Newcastle - Aston Villa"
        i["days"]["2026-10-18"]["eng.1"]["fixtures"][0].update({
            "home": "Newcastle United", "away": "Aston Villa"
        })
        r = validate(q, i)
        self.assertEqual(r["calendar_gate"], "PASS_MANUAL")
        self.assertEqual(r["errors"], [])

    def test_signoff_after_first_kickoff_is_rejected(self):
        q, i = sample()
        i["approval"]["approved_at"] = "2026-10-18T19:00:00+02:00"
        result = validate(q, i)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIn("FINAL_APPROVAL_AFTER_FIRST_KICKOFF", result["errors"])

    def test_signoff_cannot_predate_source_capture(self):
        q, i = sample()
        i["approval"]["approved_at"] = "2026-10-17T12:00:00+02:00"
        result = validate(q, i)
        self.assertIn("FINAL_APPROVAL_PREDATES_OFFICIAL_SOURCE_CAPTURE", result["errors"])

    def test_official_espn_kickoff_disagreement_needs_signed_actual_api_evidence(self):
        q, i = sample()
        q["fixtures"][0]["fixture_id"] = "esp.1:123"
        q["fixtures"][0]["fixture"] = "Real Betis - Barcelona"
        q["fixtures"][0]["kickoff"] = "2026-10-18T18:00:00+02:00"
        i["days"]["2026-10-18"]["eng.1"]["fixtures"] = []
        i["days"]["2026-10-18"]["eng.1"]["confirmed_zero_matches"] = True
        i["days"]["2026-10-18"]["esp.1"]["fixtures"] = [{
            "home": "Real Betis", "away": "FC Barcelona",
            "kickoff": "2026-10-18T18:30:00+02:00"
        }]
        i["days"]["2026-10-18"]["esp.1"]["confirmed_zero_matches"] = False
        # All information must have a legitimate pre-start observation.
        signed = {"fixture_id": "esp.1:123",
                  "third_source_fixture_id": 1570413,
                  "reviewer": "independent reviewer",
                  "reason": "Official 18:30 and API snapshot agree, ESPN cached 18:00"}
        i["days"]["2026-10-18"]["esp.1"]["time_discrepancies"] = [signed]
        api = {"date": "2026-10-18", "source": "API-Football",
               "snapshot_utc": "2026-10-18T08:00:00Z",
               "candidates": [{
                   "fixture_id": 1570413, "league_country": "Spain", "league": "La Liga",
                   "home_team": "Real Betis", "away_team": "FC Barcelona",
                   "kickoff_utc": "2026-10-18T16:30:00Z"
               }]}
        no_api = validate(q, i)
        self.assertEqual(no_api["calendar_gate"], "BLOCKED")
        self.assertIn("KICKOFF_CONFLICT_REQUIRES_PREMATCH_THIRD_SOURCE_AND_MANUAL_REVIEW",
                      " ".join(no_api["errors"]))
        proof = validate(q, i, third_party_snapshots={"2026-10-18": api})
        self.assertEqual(proof["calendar_gate"], "PASS_MANUAL")
        self.assertEqual(proof["errors"], [])
        self.assertFalse(proof["safe_to_publish_play"])
        late = copy.deepcopy(api)
        late["snapshot_utc"] = "2026-10-18T19:00:00+02:00"
        self.assertEqual(validate(q, i, {"2026-10-18": late})["calendar_gate"], "BLOCKED")
        wrong = copy.deepcopy(api)
        wrong["candidates"][0]["kickoff_utc"] = "2026-10-18T16:00:00Z"
        self.assertEqual(validate(q, i, {"2026-10-18": wrong})["calendar_gate"], "BLOCKED")

    def test_undocumented_extra_kickoff_resolution_is_rejected(self):
        q, i = sample()
        i["days"]["2026-10-18"]["eng.1"]["time_discrepancies"] = [{
            "fixture_id": "eng.1:111", "third_source_fixture_id": 777,
            "reviewer": "someone", "reason": "No actual kickoff conflict documented"
        }]
        result = validate(q, i)
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertIn("UNUSED_OR_DUPLICATE_KICKOFF_RESOLUTIONS", " ".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
