"""Each real signed date survives three-day rollovers; no auto-approval."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_calendar_signoff import sample
from tools.kb21_calendar_coverage import SCOPE
from tools.kb21_calendar_signoff import validate
from tools.kb21_persistent_day_reviews import prepare, apply, SCHEMA


def case():
    q, signed = sample()
    today = "2026-10-18"
    tomorrow = "2026-10-19"
    q["days"] = [today, tomorrow]
    q["source_status"][tomorrow] = copy.deepcopy(q["source_status"][today])
    unsigned = {
        "schema": "kb21-human-calendar-inventory-v1",
        "days": {
            today: copy.deepcopy(signed["days"][today]),
            tomorrow: copy.deepcopy(signed["days"][today]),
        },
        "daily_approvals": {today: None, tomorrow: None},
        "approval": None,
    }
    unsigned["days"][tomorrow]["eng.1"]["fixtures"] = []
    for day in unsigned["days"]:
        for record in unsigned["days"][day].values():
            record["reviewer"] = None
            record["captured_at"] = None
            record["full_day_checked"] = False
            record["confirmed_zero_matches"] = None
    return q, signed, unsigned


def sign(form, day, same_date_capture=None, approved_at=None):
    obj = copy.deepcopy(form)
    obj["approval"] = {
        "reviewer": "Independent human reviewer",
        "approved_at": approved_at or (
            "2026-10-17T15:00:00+02:00" if day == "2026-10-18"
            else "2026-10-18T15:00:00+02:00"),
        "attests_independent_official_review": True,
    }
    for code, row in obj["competitions"].items():
        row["reviewer"] = "Independent human reviewer"
        row["captured_at"] = (same_date_capture or (
            "2026-10-17T13:00:00+02:00" if day == "2026-10-18"
            else "2026-10-18T13:00:00+02:00"))
        row["full_day_checked"] = True
        row["confirmed_zero_matches"] = not bool(row["fixtures"])
    return obj


def save(folder, date, obj):
    Path(folder, date + ".json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class PersistentDailyReviewTests(unittest.TestCase):
    def test_working_forms_remain_unsafe_and_no_signoffs_ever_generated(self):
        q, signed, draft = case()
        forms = prepare(q, draft, now=datetime(2026, 10, 17, 19, tzinfo=timezone.utc))
        self.assertEqual(set(forms), set(q["days"]))
        self.assertEqual(len(forms["2026-10-18"]["competitions"]), len(SCOPE))
        self.assertFalse(forms["2026-10-18"]["human_signoff_provided"])
        self.assertIsNone(forms["2026-10-18"]["approval"])
        self.assertFalse(forms["2026-10-18"]["safe_to_publish_play"])
        self.assertEqual(forms["2026-10-19"]["cutoff_kind"],
                         "ZERO_CANDIDATES_DATE_START")
        self.assertTrue(forms["2026-10-19"]["signoff_window_open_at_generation"])

    def test_one_signed_day_and_future_day_remain_distinct(self):
        q, signed, draft = case()
        forms = prepare(q, draft, now=datetime(2026, 10, 17, 12, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", sign(forms["2026-10-19"], "2026-10-19"))
            combined, status = apply(q, draft, folder,
                                     now=datetime(2026, 10, 18, 15, tzinfo=timezone.utc))
        self.assertEqual(status["manual_days_reused"], ["2026-10-19"])
        self.assertEqual(status["pending_days"], ["2026-10-18"])
        self.assertEqual(status["automated_signoffs_created"], 0)
        self.assertIsNone(combined["daily_approvals"]["2026-10-18"])
        self.assertEqual(validate(q, combined)["days"]["2026-10-19"]["calendar_gate"],
                         "PASS_MANUAL")
        self.assertEqual(validate(q, combined)["calendar_gate"], "BLOCKED")

    def test_same_signed_day_reused_when_rolling_window_moves(self):
        q, signed, draft = case()
        forms = prepare(q, draft)
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", sign(forms["2026-10-19"], "2026-10-19"))
            combined1, summary1 = apply(q, draft, folder,
                                        now=datetime(2026, 10, 18, 17, tzinfo=timezone.utc))
            # The next diagnostic window no longer contains 2026-10-18.
            shifted = copy.deepcopy(q)
            shifted["days"] = ["2026-10-19", "2026-10-20"]
            shifted["fixtures"] = []
            shifted["source_status"]["2026-10-20"] = copy.deepcopy(
                q["source_status"]["2026-10-19"])
            rolled = copy.deepcopy(draft)
            rolled["days"] = {
                "2026-10-19": rolled["days"]["2026-10-19"],
                "2026-10-20": copy.deepcopy(rolled["days"]["2026-10-19"]),
            }
            rolled["daily_approvals"] = {
                "2026-10-19": None, "2026-10-20": None}
            combined2, summary2 = apply(
                shifted, rolled, folder,
                now=datetime(2026, 10, 18, 17, tzinfo=timezone.utc))
        self.assertEqual(summary1["manual_days_reused"], ["2026-10-19"])
        self.assertEqual(summary2["manual_days_reused"], ["2026-10-19"])
        self.assertEqual(summary2["pending_days"], ["2026-10-20"])
        self.assertEqual(validate(shifted, combined2)["days"]["2026-10-19"]
                         ["calendar_gate"], "PASS_MANUAL")
        self.assertFalse(combined2.get("approval"))

    def test_change_in_independent_fixture_rejects_stale_date_review(self):
        q, signed, draft = case()
        form = sign(prepare(q, draft)["2026-10-19"], "2026-10-19")
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", form)
            changed = copy.deepcopy(q)
            changed["fixtures"].append({
                "fixture_id": "eng.1:202", "date_warsaw": "2026-10-19",
                "fixture": "Team A - Team B",
                "kickoff": "2026-10-19T19:00:00+02:00",
            })
            with self.assertRaisesRegex(ValueError, "conflicts with current"):
                apply(changed, draft, folder, now=datetime(2026, 10, 18, 17,
                                                           tzinfo=timezone.utc))

    def test_after_midnight_zero_day_approval_fails_closed(self):
        q, _, draft = case()
        form = sign(prepare(q, draft)["2026-10-19"], "2026-10-19",
                    approved_at="2026-10-19T08:00:00+02:00")
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", form)
            with self.assertRaisesRegex(ValueError, "ZERO_CANDIDATES_DATE_START"):
                apply(q, draft, folder, now=datetime(2026, 10, 20,
                                                      tzinfo=timezone.utc))

    def test_source_after_earliest_day_kickoff_rejected(self):
        q, _, draft = case()
        form = sign(prepare(q, draft)["2026-10-18"], "2026-10-18",
                    same_date_capture="2026-10-18T19:00:00+02:00",
                    approved_at="2026-10-18T20:00:00+02:00")
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-18", form)
            with self.assertRaisesRegex(ValueError, "FIRST_KICKOFF"):
                apply(q, draft, folder, now=datetime(2026, 10, 20,
                                                      tzinfo=timezone.utc))

    def test_future_fake_signoff_rejected_even_if_kickoff_not_reached(self):
        q, _, draft = case()
        form = sign(prepare(q, draft)["2026-10-19"], "2026-10-19")
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", form)
            with self.assertRaisesRegex(ValueError, "future or invalid"):
                apply(q, draft, folder, now=datetime(2026, 10, 17, 12,
                                                     tzinfo=timezone.utc))

    def test_missing_approval_fake_organizer_and_invalid_scope_rejected(self):
        q, _, draft = case()
        raw = prepare(q, draft)["2026-10-19"]
        with tempfile.TemporaryDirectory() as folder:
            save(folder, "2026-10-19", raw)
            with self.assertRaisesRegex(ValueError, "Invalid dated manual"):
                apply(q, draft, folder)
            signed = sign(raw, "2026-10-19")
            signed["competitions"].pop("bel.1")
            save(folder, "2026-10-19", signed)
            with self.assertRaisesRegex(ValueError, "Invalid dated manual"):
                apply(q, draft, folder)

    def test_absent_files_does_not_require_any_signature(self):
        q, _, draft = case()
        before = copy.deepcopy(draft)
        with tempfile.TemporaryDirectory() as folder:
            combined, status = apply(q, draft, folder)
        self.assertEqual(combined, before)
        self.assertEqual(status["manual_days_reused"], [])
        self.assertEqual(status["automated_signoffs_created"], 0)
        self.assertEqual(status["pending_days"], q["days"])


if __name__ == "__main__":
    unittest.main()
