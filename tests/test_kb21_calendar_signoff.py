"""Signed mock fixtures exercise the signoff validator, NOT true official site verification."""
import copy
import unittest

from tools.kb21_calendar_signoff import validate
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
                      validate(q, i)["days"]["2026-10-18"]["errors"][0] if False else
                      " ".join(validate(q, i)["errors"]))
        q, i = sample()
        i["days"]["2026-10-18"]["eng.1"]["captured_at"] = "2026-10-18T19:00:00+02:00"
        self.assertEqual(validate(q, i)["status"], "BLOCKED")

    def test_esports_source_failure_and_unnamed_reviewer_block(self):
        q, i = sample()
        q["source_status"]["2026-10-18"][0]["status"] = "ERROR"
        i["days"]["2026-10-18"]["ita.1"]["reviewer"] = ""
        self.assertEqual(validate(q, i)["status"], "BLOCKED")

    def test_date_mismatch_fails(self):
        q, i = sample()
        i["days"]["2026-10-19"] = copy.deepcopy(i["days"]["2026-10-18"])
        self.assertEqual(validate(q, i)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
