import json
import tempfile
import unittest
from pathlib import Path
from github_models.daily_queue import build_queue

class QueueTests(unittest.TestCase):
    def test_three_days_and_no_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = "2026-11-05"
            data = dict(schema="pitchapi-prematch-context-v1", source="PitchAPI",
                        target_date=day, snapshot_utc="2026-11-05T07:00:00Z",
                        fixtures=[dict(pitch_match_id="m1", league="Test League", league_id=987, country_code="ENG",
                                       home="A", away="B", kickoff_utc="2026-11-05T17:00:00Z",
                                       both_sides_sufficient=True)])
            Path(tmp, day + ".json").write_text(json.dumps(data))
            q = build_queue(tmp, start_date=day, as_of_utc="2026-11-05T08:00:00Z")
            self.assertEqual(len(q["fixtures"]), 1)
            self.assertEqual(q["missing_dates"], ["2026-11-06", "2026-11-07"])
            self.assertEqual(q["fixtures"][0]["models_requested"],
                             ["dixon-coles", "elo", "xgboost"])
            self.assertNotIn("p_home", q["fixtures"][0])
            self.assertEqual(q["fixtures"][0]["league_id"], 987)
            self.assertEqual(q["fixtures"][0]["country_code"], "ENG")


    def test_seven_day_queue_contains_next_saturday_only_when_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = "2026-11-15"
            for day in range(15, 22):
                date = f"2026-11-{day:02d}"
                fixtures = ([dict(pitch_match_id="sat", league="LaLiga2",
                                  league_id="l_3kyHLd", country_code="ESP",
                                  home="Eibar", away="Cadiz",
                                  kickoff_utc="2026-11-21T17:30:00Z")]
                            if day == 21 else [])
                data = dict(schema="pitchapi-research-fixtures-v1",
                            source="PitchAPI", source_status="ok", target_date=date,
                            snapshot_utc="2026-11-15T08:05:00Z", fixtures=fixtures)
                Path(tmp, date + ".json").write_text(json.dumps(data))
            q = build_queue(tmp, start_date=base, as_of_utc="2026-11-15T08:10:00Z", days=7)
            self.assertEqual(len(q["dates"]), 7)
            self.assertEqual(q["dates"][-1], "2026-11-21")
            self.assertEqual((q["missing_dates"], q["invalid_dates"]), ([], []))
            self.assertEqual([f["fixture_id"] for f in q["fixtures"]], ["sat"])
            self.assertNotIn("p_home", q["fixtures"][0])

    def test_seven_day_missing_and_invalid_dates_are_never_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            Saturday = "2026-11-21"
            Path(tmp, Saturday + ".json").write_text(json.dumps(
                dict(schema="pitchapi-research-fixtures-v1", source="PitchAPI",
                     source_status="source_error", target_date=Saturday,
                     snapshot_utc="2026-11-15T08:05:00Z", fixtures=[])))
            q = build_queue(tmp, start_date="2026-11-15",
                            as_of_utc="2026-11-15T08:10:00Z", days=7)
            self.assertEqual(q["missing_dates"], [f"2026-11-{d:02d}" for d in range(15, 21)])
            self.assertEqual(q["invalid_dates"], ["2026-11-21"])
            self.assertEqual(q["fixtures"], [])

    def test_invalid_horizon_fails_before_snapshot_read(self):
        for horizon in (-1, 0, 8, 2.5, True):
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                build_queue("/not/a/real/path", start_date="2026-11-15",
                            as_of_utc="2026-11-15T08:10:00Z", days=horizon)

    def test_future_snapshot_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = dict(schema="pitchapi-prematch-context-v1", source="PitchAPI",
                        target_date="2026-11-05", snapshot_utc="2026-11-05T12:00:00Z",
                        fixtures=[])
            Path(tmp, "2026-11-05.json").write_text(json.dumps(data))
            q = build_queue(tmp, start_date="2026-11-05", as_of_utc="2026-11-05T08:00:00Z")
            self.assertEqual(q["invalid_dates"], ["2026-11-05"])

    def test_cross_midnight_fixture_does_not_invalidate_entire_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = '2026-11-06'
            base = dict(league='Bundesliga', league_id='verified-test-id', home='A', away='B', both_sides_sufficient=True)
            data = dict(schema='pitchapi-prematch-context-v1', source='PitchAPI', target_date=day,
                        snapshot_utc='2026-11-05T22:00:00Z', fixtures=[
                            dict(base, pitch_match_id='wrong-day', kickoff_utc='2026-11-06T23:30:00Z'),
                            dict(base, pitch_match_id='right-day', kickoff_utc='2026-11-06T18:00:00Z')])
            Path(tmp, day + '.json').write_text(json.dumps(data))
            q = build_queue(tmp, start_date='2026-11-05', as_of_utc='2026-11-05T22:30:00Z')
            self.assertEqual(q['invalid_dates'], [])
            self.assertEqual([f['fixture_id'] for f in q['fixtures']], ['right-day'])
