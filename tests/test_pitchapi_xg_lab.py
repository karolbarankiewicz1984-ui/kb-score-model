"""Regression tests for isolated PitchAPI / API-Football post-match data lab."""
import unittest
from tools.pitchapi_xg_lab import collect_match, compare, competition, norm

class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class FakeClient:
    def __init__(self, shots):
        self.matches = Obj(shots=lambda mid: Obj(periods=[Obj(shots=shots)]))

def pitch(**patch):
    obj = {
        "pitch_match_id": "m_123456", "league": "Champions League",
        "home": "Roma", "away": "Real Madrid", "kickoff_utc": "2026-10-14T19:00:00Z",
        "goals_home": 3, "goals_away": 4,
        "xg_home": {"xg": 0.65, "xg_complete": True, "shot_count": 2},
        "xg_away": {"xg": 0.35, "xg_complete": True, "shot_count": 1},
    }
    obj.update(patch)
    return obj

def api(**patch):
    obj = {"fixture_id": 1635614, "date": "2026-10-14T21:00:00+02:00",
           "league": "UEFA Champions League", "home": "AS Roma", "away": "Real Madrid",
           "goals": {"home": 3, "away": 4}, "home_id": 11, "away_id": 22,
           "teams": [{"team_id": 11, "shots": 12}, {"team_id": 22, "shots": 8}]}
    obj.update(patch)
    return obj

class MatchTests(unittest.TestCase):
    def test_joins_same_fixture(self):
        result = compare([pitch()], [api()])
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["usable_for_historical_calibration"], 1)
        self.assertEqual(result["matched_rows"][0]["xg_home"], 0.65)

    def test_competition_is_required(self):
        self.assertEqual(compare([pitch(league="Europa League")], [api()])["matched"], 0)

    def test_kickoff_mismatch_excluded(self):
        self.assertEqual(compare([pitch(kickoff_utc="2026-10-14T02:00:00Z")], [api()])["matched"], 0)

    def test_wrong_result_is_quarantined(self):
        result = compare([pitch(goals_home=0)], [api()])
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["usable_for_historical_calibration"], 0)
        self.assertIsNone(result["matched_rows"][0]["xg_home"])

    def test_missing_xg_does_not_become_zero(self):
        result = compare([pitch(xg_home={"xg": None, "xg_complete": False, "shot_count": 2})], [api()])
        self.assertEqual(result["usable_for_historical_calibration"], 0)

    def test_ambiguous_matches_are_not_assigned(self):
        result = compare([pitch(), pitch(pitch_match_id="m_654321")], [api()])
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["unresolved"][0]["reason"], "ambiguous_match")

    def test_unicode_team_and_europe_aliases(self):
        self.assertEqual(norm("Bodø/Glimt"), "bodo glimt")
        self.assertEqual(norm("Fenerbahçe"), "fenerbahce")
        self.assertEqual(norm("Lask Linz"), norm("LASK"))
        self.assertEqual(norm("AEK Athens FC"), norm("AEK Athens"))
        self.assertEqual(norm("Coventry City"), norm("Coventry"))
        self.assertEqual(norm("Newcastle United"), norm("Newcastle"))
        self.assertEqual(norm("Club Brugge KV"), norm("Club Brugge"))
        self.assertEqual(norm("Sabah FA"), norm("Sabah FK"))
        self.assertEqual(norm("Slavia Praha"), norm("Slavia Prague"))
        self.assertEqual(competition("LaLiga"), competition("La Liga"))
        self.assertEqual(competition("Liga Portugal"), competition("Primeira Liga"))
        self.assertEqual(competition("UEFA Europa Conference League"), competition("Conference League"))

class ShotTests(unittest.TestCase):
    def row(self, shots):
        match = Obj(id="m_123456", home_team=Obj(id="t_home", name="Roma"),
                    away_team=Obj(id="t_away", name="Real Madrid"),
                    league=Obj(id="l_1", name="Champions League"),
                    date="2026-10-14", time_utc="2026-10-14T19:00:00Z",
                    score_home=3, score_away=4, status="finished")
        return collect_match(match, FakeClient(shots))

    def test_sum_belongs_to_correct_team(self):
        p = self.row([Obj(id="s1", team_id="t_home", expected_goals=0.3),
                      Obj(id="s2", team_id="t_home", expected_goals=0.25),
                      Obj(id="s3", team_id="t_away", expected_goals=0.5)])
        self.assertEqual(p["xg_home"]["xg"], 0.55)
        self.assertEqual(p["xg_away"]["xg"], 0.5)

    def test_incomplete_shots_cannot_set_xg(self):
        p = self.row([Obj(id="s1", team_id="t_home", expected_goals=0.3),
                      Obj(id="s2", team_id="t_home", expected_goals=None),
                      Obj(id="s3", team_id="t_away", expected_goals=0.4)])
        self.assertIsNone(p["xg_home"]["xg"])
        self.assertEqual(p["xg_away"]["xg"], 0.4)

    def test_unknown_team_rejected(self):
        p = self.row([Obj(id="s1", team_id="other", expected_goals=0.3)])
        self.assertEqual(p["shots_error"], "unrecognized_shot_team")

    def test_duplicate_shot_id_deduplicated(self):
        p = self.row([Obj(id="s1", team_id="t_home", expected_goals=0.3),
                      Obj(id="s1", team_id="t_home", expected_goals=0.3),
                      Obj(id="s2", team_id="t_away", expected_goals=0.4)])
        self.assertEqual(p["xg_home"]["shot_count"], 1)

if __name__ == "__main__":
    unittest.main()
