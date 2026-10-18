"""Tests for strictly frozen and matched research model probabilities."""
from copy import deepcopy
from datetime import timedelta
import unittest

from tests.test_kb21_single_source_form import base_calendar, TeamsClient, NOW
from tests.test_kb21_pitchapi_prematch_bridge import pitch_doc
from tools.kb21_single_source_form import build_source_pack, shadow_snapshot
from tools.kb21_pitchapi_prematch_bridge import build as bridge
from tools.kb21_xg_pair_shadow import freeze_pair, experimental_xg_probabilities, render


def inputs():
    calendar, dates=base_calendar()
    form=build_source_pack(calendar,dates,TeamsClient(),"key",now=NOW)
    xg=bridge(calendar,dates,{day:pitch_doc(day, "p_"+day)
                            for day in calendar["dates"]},now=NOW)
    fm={k:v for k,v in form.items() if k!="days"}
    xm={k:v for k,v in xg.items() if k!="days"}
    return form,fm,xg,xm


class XgPairTests(unittest.TestCase):
    def test_pair_both_model_forecasts_not_original(self):
        form,fm,xg,xm=inputs()
        for day in form["days"]:
            ref=next(x for x in xg["days"] if x["date"]==day["day"])
            goals=shadow_snapshot(form,day)
            pairs=freeze_pair(day["day"],fm,day,goals,xm,ref,now=NOW+timedelta(seconds=3))
            self.assertEqual(pairs["paired_count"],1)
            self.assertEqual(pairs["register_writes"],False)
            self.assertIsNone(pairs["original_kb21_p_model"])
            self.assertFalse(pairs["safe_to_publish_play"])
            row=pairs["pairs"][0]
            self.assertEqual(row["baseline_model_id"],"kb21-api-last10-goals-shadow-v1")
            self.assertEqual(row["goals_baseline_probabilities"],
                             goals["predictions"][0]["probabilities_1x2_over25"])
            self.assertAlmostEqual(sum(row["xg_shadow_probabilities"][k]
                for k in ("home","draw","away")),1,places=5)
            self.assertIsNone(row["original_kb21_p_model"])
            self.assertIsNone(row["odds"])
            self.assertEqual(row["xg_sample_sizes"],{"home":5,"away":5})
            self.assertIn("NIE SĄ TO TYPY",render(pairs))

    def test_poisson_no_external_information_and_deterministic(self):
        h={"sample_size":5,"mean_xg_for":1.8,"mean_xg_against":.7}
        a={"sample_size":4,"mean_xg_for":1.3,"mean_xg_against":1.4}
        p,rates=experimental_xg_probabilities(h,a)
        self.assertEqual(rates["home"],1.6)
        self.assertEqual(rates["away"],1.0)
        self.assertGreater(p["home"],p["away"])
        self.assertAlmostEqual(sum(p[k] for k in ("home","draw","away")),1,places=5)
        self.assertTrue(0 < p["over_2_5"] < 1)
        self.assertEqual(p,experimental_xg_probabilities(h,a)[0])

    def test_missing_real_pitch_xg_means_no_pair_not_zero(self):
        form,fm,xg,xm=inputs()
        first=form["days"][0]; goals=shadow_snapshot(form,first)
        xg["days"][0]["records"][0]["status"]="NOT_MATCHED_IN_PITCHAPI_SNAPSHOT"
        xg["days"][0]["records"][0]["home_xg"]=None
        pair=freeze_pair(first["day"],fm,first,goals,xm,xg["days"][0],
                         now=NOW+timedelta(seconds=3))
        self.assertEqual(pair["paired_count"],0)

    def test_no_late_first_freeze(self):
        form,fm,xg,xm=inputs()
        first=form["days"][0]; goals=shadow_snapshot(form,first)
        from tools.kb21_single_source_calendar import _iso_datetime
        kickoff=_iso_datetime(first["matches"][0]["kickoff_utc"])
        pair=freeze_pair(first["day"],fm,first,goals,xm,xg["days"][0],now=kickoff+timedelta(seconds=1))
        self.assertEqual(pair["paired_count"],0)

    def test_cross_run_odds_and_id_pollution_rejected(self):
        form,fm,xg,xm=inputs()
        day=form["days"][0]; goals=shadow_snapshot(form,day)
        tampered=deepcopy(goals)
        tampered["predictions"][0]["odds"]=1.62
        with self.assertRaisesRegex(ValueError,"Polluted"):
            freeze_pair(day["day"],fm,day,tampered,xm,xg["days"][0],
                        now=NOW+timedelta(seconds=3))
        broken=deepcopy(xg["days"][0])
        broken["records"][0]["fixture"]="Other - Other"
        with self.assertRaisesRegex(ValueError,"mismatch"):
            freeze_pair(day["day"],fm,day,goals,xm,broken,now=NOW+timedelta(seconds=3))

    def test_no_false_sample_size_or_boolean_xg(self):
        for bad in (True,-1,float("nan"),float("inf"),"1.0"):
            h={"sample_size":5,"mean_xg_for":bad,"mean_xg_against":1.0}
            a={"sample_size":5,"mean_xg_for":1.2,"mean_xg_against":.9}
            with self.assertRaisesRegex(ValueError,"Invalid"):
                experimental_xg_probabilities(h,a)
        with self.assertRaisesRegex(ValueError,"Invalid"):
            experimental_xg_probabilities(
                {"sample_size":2,"mean_xg_for":1.4,"mean_xg_against":1.4},
                {"sample_size":5,"mean_xg_for":1.0,"mean_xg_against":1.0})

    def test_forecast_freeze_before_bridge_fails(self):
        form,fm,xg,xm=inputs()
        day=form["days"][0];goals=shadow_snapshot(form,day)
        with self.assertRaisesRegex(ValueError,"source chain"):
            freeze_pair(day["day"],fm,day,goals,xm,xg["days"][0],
                        now=NOW-timedelta(minutes=2))

if __name__ == "__main__":
    unittest.main()
