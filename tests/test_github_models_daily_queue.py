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
            self.assertEqual(q["fixtures"][0]["country_code"], "England")

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
