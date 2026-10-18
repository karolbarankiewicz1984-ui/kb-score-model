"""Forward-only premarket xG bridge; no fabricated scores or extra API requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from tests.test_kb21_single_source_calendar import TODAY, TOMORROW, NOW
from tests.test_kb21_single_source_form import base_calendar
from tools.kb21_pitchapi_prematch_bridge import build, render_day, _validate_recent

CAPTURE = datetime(2026, 10, 17, 17, 30, tzinfo=timezone.utc)


def sample(team, mid, capture=CAPTURE):
    records = []
    for ix in range(5):
        records.append({
            "match_id": team + "-" + str(ix),
            "kickoff_utc": (capture-timedelta(days=ix+1)).isoformat(),
            "xg_for": 1.1 + ix/10,
            "xg_against": .5 + ix/10,
        })
    return {
        "complete_samples": 5, "requested_samples": 5,
        "data_quality": "sufficient",
        "mean_xg_for": 1.3, "mean_xg_against": .7,
        "source_match_ids": [x["match_id"] for x in records],
        "samples": records,
    }


def pitch_doc(date, mid="m_123", captured=CAPTURE):
    kickoff = date + "T14:00:00+02:00"
    return {
        "schema": "pitchapi-prematch-context-v1",
        "target_date": date, "snapshot_utc": captured.isoformat(),
        "source": "PitchAPI", "model_effect": "NONE", "kb_n_effect": 0,
        "fixtures_collected": 1,
        "fixtures": [{
            "pitch_match_id": mid, "home": "Arsenal", "away": "Chelsea",
            "league": "Premier League", "kickoff_utc": kickoff,
            "both_sides_sufficient": True,
            "home_recent": sample("h", mid, captured),
            "away_recent": sample("a", mid, captured),
        }],
    }


class PitchBridgeTests(unittest.TestCase):
    def test_no_added_games_and_confirmed_two_day_xg(self):
        m, calendars = base_calendar()
        result = build(m, calendars, {
            TODAY: pitch_doc(TODAY),
            TOMORROW: pitch_doc(TOMORROW, "m_456"),
        }, now=NOW)
        self.assertEqual(result["calendar_candidates"], 2)
        self.assertEqual(result["matches_with_verified_prematch_xg"], 2)
        self.assertEqual(result["external_api_calls"], 0)
        self.assertEqual(result["automatic_p_model_count"], 0)
        self.assertEqual(result["automatic_str_qual_match_count"], 0)
        self.assertFalse(result["safe_to_publish_play"])
        self.assertFalse(result["register_writes"])
        for day in result["days"]:
            row = day["records"][0]
            self.assertEqual(row["status"], "VERIFIED_PREMATCH_HISTORICAL_XG")
            self.assertEqual(row["home_xg"]["mean_xg_for"], 1.3)
            self.assertEqual(row["home_xg"]["mean_xg_against"], .7)
            self.assertEqual(row["home_xg"]["sample_size"], 5)
            self.assertIsNone(row["original_kb21_p_model"])
            self.assertIsNone(row["str_35"])
            self.assertIsNone(row["odds"])
            self.assertIn("NIE P(model)",render_day(day))

    def test_missing_tomorrow_snapshot_does_not_invent_xg(self):
        m,c = base_calendar()
        x=build(m,c,{TODAY:pitch_doc(TODAY)},now=NOW)
        self.assertEqual(x["calendar_candidates"],2)
        self.assertEqual(x["matches_with_verified_prematch_xg"],1)
        self.assertEqual(x["days"][1]["records"][0]["status"],
                         "NO_SAVED_PITCHAPI_PREMATCH_ARCHIVE")
        self.assertIsNone(x["days"][1]["records"][0]["home_xg"])

    def test_cannot_join_after_kickoff(self):
        m,c=base_calendar()
        now=datetime(2026,10,19,18,0,tzinfo=timezone.utc)
        x=build(m,c,{TODAY:pitch_doc(TODAY)},now=now)
        self.assertEqual(x["matches_with_verified_prematch_xg"],0)
        self.assertEqual(x["days"][0]["records"][0]["status"],
                         "NOT_VERIFIABLY_PREMATCH_AT_BRIDGE")

    def test_snapshot_captured_after_kickoff_never_works(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY, captured=datetime(
            2026,10,18,13,0,tzinfo=timezone.utc))
        now=datetime(2026,10,18,14,0,tzinfo=timezone.utc)
        x=build(m,c,{TODAY:snap},now=now)
        self.assertEqual(x["matches_with_verified_prematch_xg"],0)
        self.assertEqual(x["days"][0]["records"][0]["status"],
                         "NOT_VERIFIABLY_PREMATCH_AT_BRIDGE")

    def test_future_snapshot_does_not_join_as_past(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY,captured=NOW+timedelta(hours=1))
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)
        self.assertEqual(r["days"][0]["records"][0]["status"],
                         "INVALID_PREMATCH_SNAPSHOT")

    def test_snapshot_later_than_sample_does_not_legalize_future_sample(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["home_recent"]["samples"][0]["kickoff_utc"] = (
            CAPTURE+timedelta(hours=1)).isoformat()
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)
        self.assertEqual(r["days"][0]["records"][0]["status"],
                         "INSUFFICIENT_OR_UNVERIFIED_HISTORICAL_XG")

    def test_samples_under_two_hours_before_snapshot_refused(self):
        p=sample("h","m123")
        p["samples"][0]["kickoff_utc"]=(CAPTURE-timedelta(minutes=10)).isoformat()
        self.assertIsNone(_validate_recent(p,CAPTURE,"m123"))

    def test_do_not_auto_correct_wrong_mean_xg(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["home_recent"]["mean_xg_for"]=4.5
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)

    def test_no_reverse_or_vague_team_joins(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["home"]="Chelsea"
        snap["fixtures"][0]["away"]="Arsenal"
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["days"][0]["records"][0]["status"],
                         "NOT_MATCHED_IN_PITCHAPI_SNAPSHOT")
        snap["fixtures"][0]["home"]="Arsenal FC"
        snap["fixtures"][0]["away"]="Chelsea"
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)

    def test_mismatched_league_or_kickoff_denied(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["league"]="Champions League"
        self.assertEqual(build(m,c,{TODAY:snap},now=NOW)
                         ["matches_with_verified_prematch_xg"],0)
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["kickoff_utc"]=TODAY+"T17:00:00+02:00"
        self.assertEqual(build(m,c,{TODAY:snap},now=NOW)
                         ["matches_with_verified_prematch_xg"],0)

    def test_ambiguous_source_duplicates_are_not_used(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        copy=deepcopy(snap["fixtures"][0])
        copy["pitch_match_id"]="m_duplicate"
        snap["fixtures"].append(copy)
        snap["fixtures_collected"]=2
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)
        self.assertEqual(r["days"][0]["records"][0]["status"],
                         "AMBIGUOUS_PITCHAPI_FIXTURE_MATCH")

    def test_pitch_snapshot_duplicate_id_invalidates_whole_source(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"].append(deepcopy(snap["fixtures"][0]))
        snap["fixtures_collected"]=2
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["days"][0]["source_status"],
                         "INVALID_PREMATCH_SNAPSHOT")

    def test_wrong_canonical_candidate_cannot_be_added(self):
        m,c=base_calendar()
        wrong=deepcopy(c)
        wrong[TODAY]["candidates"][0]["home"]="NotArsenal"
        with self.assertRaisesRegex(ValueError,"Noncanonical"):
            build(m,wrong,{TODAY:pitch_doc(TODAY)},now=NOW)
        with self.assertRaisesRegex(ValueError,"two canonical"):
            build({**m,"provider_count":2},c,{},now=NOW)

    def test_tainted_non_numeric_xg_refused(self):
        m,c=base_calendar()
        snap=pitch_doc(TODAY)
        snap["fixtures"][0]["away_recent"]["samples"][2]["xg_for"]=True
        r=build(m,c,{TODAY:snap},now=NOW)
        self.assertEqual(r["matches_with_verified_prematch_xg"],0)


if __name__=="__main__":
    unittest.main()
