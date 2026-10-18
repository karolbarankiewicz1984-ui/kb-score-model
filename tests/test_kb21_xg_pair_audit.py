"""End-to-end: saved earlier paired snapshots vs canonical real FT results."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from tests.test_kb21_single_source_form import base_calendar, TeamsClient, NOW
from tests.test_kb21_pitchapi_prematch_bridge import pitch_doc
from tests.test_kb21_shadow_audit import result_feed
from tools.kb21_single_source_form import build_source_pack, shadow_snapshot
from tools.kb21_pitchapi_prematch_bridge import build as build_xg
from tools.kb21_xg_pair_shadow import freeze_pair
from tools.kb21_xg_pair_audit import load_pairs, compare, render


def write_archive(root):
    m, cal = base_calendar()
    form=build_source_pack(m,cal,TeamsClient(),"key",now=NOW)
    xg=build_xg(m,cal,{d:pitch_doc(d,"p-"+d) for d in m["dates"]},now=NOW)
    fm={k:v for k,v in form.items() if k!="days"}
    xm={k:v for k,v in xg.items() if k!="days"}
    day=form["days"][0]
    old=shadow_snapshot(form,day)
    xgday=xg["days"][0]
    pair=freeze_pair(day["day"],fm,day,old,xm,xgday,now=NOW+timedelta(seconds=4))
    docs={
        "SINGLE_SOURCE_MANIFEST.json":m,
        "KB21_API_CALENDAR_"+day["day"]+".json":cal[day["day"]],
        "KB21_FORM_MANIFEST.json":fm,
        "KB21_SHADOW_"+day["day"]+".json":old,
        "KB21_PREODDS_XG_MANIFEST.json":xm,
        "KB21_PREODDS_XG_"+day["day"]+".json":xgday,
        "KB21_XG_V_GOALS_SHADOW_"+day["day"]+".json":pair,
    }
    root.mkdir(parents=True,exist_ok=True)
    for name, obj in docs.items():
        (root/name).write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
    return docs


class XgAuditTests(unittest.TestCase):
    def test_paired_results_share_exact_ft_fixture_and_no_model_updates(self):
        with tempfile.TemporaryDirectory() as base:
            docs=write_archive(Path(base)/"run1")
            day=docs["KB21_XG_V_GOALS_SHADOW_2026-10-18.json"]["date"]
            pairs,count=load_pairs(base,day)
            self.assertEqual((len(pairs),count),(1,1))
            report=compare(day,pairs,result_feed(),
                now=datetime(2026,10,19,3,tzinfo=timezone.utc))
            self.assertEqual(report["distinct_settled_FT_matches"],1)
            self.assertIsNotNone(report["summary"]["mean_1x2_brier_xg"])
            self.assertIsNotNone(report["summary"]["mean_1x2_brier_goals"])
            self.assertEqual(report["original_kb21_n_effect"],0)
            self.assertFalse(report["register_writes"])
            self.assertFalse(report["safe_to_publish_play"])
            self.assertIn("BADANIE, NIE TYP",render(report))

    def test_second_identical_archive_not_second_independent_game(self):
        with tempfile.TemporaryDirectory() as base:
            write_archive(Path(base)/"123")
            write_archive(Path(base)/"456")
            pairs,count=load_pairs(base,"2026-10-18")
            self.assertEqual(count,2)
            self.assertEqual(len(pairs),1)

    def test_after_kickoff_freeze_cannot_be_rewritten_as_pregame(self):
        with tempfile.TemporaryDirectory() as base:
            docs=write_archive(Path(base)/"run1")
            name="KB21_XG_V_GOALS_SHADOW_2026-10-18.json"
            pair=deepcopy(docs[name])
            pair["created_at_utc"]="2026-10-19T04:00:00Z"
            pair["pairs"][0]["pair_freeze_utc"]=pair["created_at_utc"]
            (Path(base)/"run1"/name).write_text(json.dumps(pair),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Rejected"):
                load_pairs(base,"2026-10-18")

    def test_tampered_baseline_and_swapped_fixture_refused(self):
        with tempfile.TemporaryDirectory() as base:
            docs=write_archive(Path(base)/"run1")
            name="KB21_XG_V_GOALS_SHADOW_2026-10-18.json"
            pair=deepcopy(docs[name])
            pair["pairs"][0]["goals_baseline_probabilities"]["home"]=.99
            (Path(base)/"run1"/name).write_text(json.dumps(pair),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Rejected"):
                load_pairs(base,"2026-10-18")
            pair=deepcopy(docs[name])
            pair["pairs"][0]["odds"]=1.8
            (Path(base)/"run1"/name).write_text(json.dumps(pair),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Rejected"):
                load_pairs(base,"2026-10-18")

    def test_missing_finished_result_is_not_bad_prediction(self):
        with tempfile.TemporaryDirectory() as base:
            write_archive(Path(base)/"run1")
            pairs,_=load_pairs(base,"2026-10-18")
            feed=result_feed(status="PST")
            report=compare("2026-10-18",pairs,feed,
                now=datetime(2026,10,19,3,tzinfo=timezone.utc))
            self.assertEqual(report["distinct_settled_FT_matches"],0)
            self.assertIsNone(report["summary"]["mean_1x2_brier_xg"])
            self.assertEqual(report["unresolved"],1)

    def test_no_pairs_means_no_winner_claim(self):
        report=compare("2026-10-18",[],result_feed(),
                now=datetime(2026,10,19,3,tzinfo=timezone.utc))
        self.assertEqual(report["distinct_settled_FT_matches"],0)
        self.assertIsNone(report["summary"]["brier_1x2_xg_minus_goals"])
        self.assertIn("Brak par prognoz",render(report))


if __name__=="__main__":
    unittest.main()
