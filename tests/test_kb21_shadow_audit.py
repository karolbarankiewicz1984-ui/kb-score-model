"""Forward-only KB21 shadow settlement. None of these are original KB predictions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_single_source_calendar import TODAY, TOMORROW, NOW, fixture, wrapper
from tests.test_kb21_single_source_form import base_calendar, TeamsClient
from tools.kb21_single_source_form import build_source_pack, shadow_snapshot
from tools.kb21_shadow_audit import (
    load_archives, settle, previous_warsaw_day, render,
)


def archive(folder):
    manifest, docs = base_calendar()
    pack = build_source_pack(manifest, docs, TeamsClient(), "test", now=NOW)
    day = pack["days"][0]
    snap = shadow_snapshot(pack, day)
    directory = Path(folder)
    directory.mkdir(parents=True, exist_ok=True)
    content = {
        "SINGLE_SOURCE_MANIFEST.json": manifest,
        "KB21_API_CALENDAR_" + TODAY + ".json": docs[TODAY],
        "KB21_FORM_MANIFEST.json": {k:v for k,v in pack.items() if k != "days"},
        "KB21_SHADOW_" + TODAY + ".json": snap,
    }
    for name, value in content.items():
        (directory / name).write_text(json.dumps(value), encoding="utf-8")
    return content


def result_feed(status="FT", goals=(2, 1), date=None):
    game = fixture(11)
    game["fixture"]["status"] = {"short":status, "long":status}
    if date:
        game["fixture"]["date"] = date
    game["goals"] = {"home":goals[0], "away":goals[1]}
    game["score"] = {"fulltime":{"home":goals[0], "away":goals[1]}}
    return wrapper(TODAY, 1, 1, [game])


class ShadowAuditTests(unittest.TestCase):
    def test_yesterday_calendar_timezone(self):
        self.assertEqual(previous_warsaw_day(datetime(
            2026, 10, 19, 1, tzinfo=timezone.utc)), TODAY)
        self.assertEqual(previous_warsaw_day(datetime(
            2026, 10, 18, 22, 30, tzinfo=timezone.utc)), TODAY)

    def test_real_saved_snapshot_settles_correct_outcome(self):
        with tempfile.TemporaryDirectory() as root:
            archive(Path(root)/"run123")
            forecasts, count = load_archives(root, TODAY)
            self.assertEqual(count, 1)
            self.assertEqual(len(forecasts), 1)
            report = settle(TODAY, forecasts, result_feed(),
                            now=datetime(2026,10,19,3,tzinfo=timezone.utc),
                            source_snapshots=count)
            self.assertEqual(report["distinct_settled_matches"], 1)
            self.assertEqual(report["unique_pregame_predictions"], 1)
            self.assertEqual(report["unresolved_matches"], 0)
            self.assertEqual(report["results"][0]["realized_1x2"], "home")
            self.assertEqual(report["results"][0]["realized_over_2_5"], 1)
            self.assertEqual(report["results"][0]["status"], "SETTLED_FT")
            self.assertIsNotNone(report["mean_multiclass_brier_1x2"])
            self.assertIsNotNone(report["mean_brier_over_2_5"])
            self.assertFalse(report["safe_to_publish_play"])
            self.assertFalse(report["register_writes"])
            self.assertEqual(report["old_kb21_n_effect"], 0)
            self.assertIn("NO PLAY", render(report))

    def test_same_forecast_from_twice_downloaded_run_counts_once(self):
        with tempfile.TemporaryDirectory() as root:
            archive(Path(root)/"run123")
            archive(Path(root)/"run456")
            forecasts, count = load_archives(root, TODAY)
            self.assertEqual(count, 2)
            self.assertEqual(len(forecasts), 1)

    def test_an_altered_snapshot_cannot_manufacture_premarket_forecast(self):
        with tempfile.TemporaryDirectory() as root:
            data = archive(Path(root)/"run123")
            dest = Path(root)/"run123"/("KB21_SHADOW_" + TODAY + ".json")
            doc = deepcopy(data["KB21_SHADOW_" + TODAY + ".json"])
            doc["created_from_source_run_utc"] = (NOW + timedelta(days=2)).isoformat()
            dest.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "timestamps|kickoff|Invalid"):
                load_archives(root, TODAY)

    def test_rejects_injected_odds_or_fake_calibration(self):
        with tempfile.TemporaryDirectory() as root:
            data = archive(Path(root)/"run123")
            dest = Path(root)/"run123"/("KB21_SHADOW_" + TODAY + ".json")
            doc = deepcopy(data["KB21_SHADOW_" + TODAY + ".json"])
            doc["predictions"][0]["odds"] = 1.8
            dest.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "polluted"):
                load_archives(root, TODAY)
            doc["predictions"][0]["odds"] = None
            doc["predictions"][0]["original_kb21_p_model"] = 0.96
            dest.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "polluted"):
                load_archives(root, TODAY)

    def test_result_changed_kickoff_never_scores(self):
        with tempfile.TemporaryDirectory() as root:
            archive(Path(root)/"run123")
            forecasts, _ = load_archives(root, TODAY)
            shifted = result_feed(date=TODAY + "T16:00:00+02:00")
            report = settle(TODAY, forecasts, shifted,
                            now=datetime(2026,10,19,4,tzinfo=timezone.utc))
            self.assertEqual(report["distinct_settled_matches"], 0)
            self.assertEqual(report["results"][0]["status"],
                             "KICKOFF_CHANGED_NOT_SETTLED")

    def test_non_ft_and_conflicting_goals_are_not_counted(self):
        with tempfile.TemporaryDirectory() as root:
            archive(Path(root)/"run123")
            forecasts, _ = load_archives(root, TODAY)
            late = datetime(2026,10,19,4,tzinfo=timezone.utc)
            self.assertEqual(settle(TODAY, forecasts, result_feed(status="AET"),
                                    now=late)["distinct_settled_matches"], 0)
            bad = result_feed()
            bad["response"][0]["score"]["fulltime"]["home"] = 1
            report = settle(TODAY, forecasts, bad, now=late)
            self.assertEqual(report["results"][0]["status"],
                             "INCOMPLETE_OR_CONFLICTING_SCORE")

    def test_no_predictions_never_fakes_results(self):
        report = settle(TODAY, [], result_feed(),
                        now=datetime(2026,10,19,4,tzinfo=timezone.utc))
        self.assertEqual(report["distinct_settled_matches"], 0)
        self.assertIsNone(report["top_1x2_accuracy"])
        self.assertIn("Brak zachowanych prognoz", render(report))

    def test_result_wrong_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            archive(Path(root)/"run123")
            forecasts, _ = load_archives(root, TODAY)
            bad = wrapper(TOMORROW, 1, 1, [])
            with self.assertRaisesRegex(ValueError, "wrong date"):
                settle(TODAY, forecasts, bad,
                       now=datetime(2026,10,19,4,tzinfo=timezone.utc))

    def test_cannot_audit_during_the_target_day(self):
        with self.assertRaisesRegex(ValueError, "still running"):
            settle(TODAY, [], result_feed(), now=NOW)


if __name__ == "__main__":
    unittest.main()
