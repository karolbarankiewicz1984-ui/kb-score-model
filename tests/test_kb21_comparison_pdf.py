"""Compact real research PDFs with Polish characters and no market claims."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_xg_pair_shadow import inputs
from tools.kb21_single_source_form import shadow_snapshot
from tools.kb21_xg_pair_shadow import freeze_pair
from tools.kb21_comparison_pdf import paired_pdf, audit_pdf
from tests.test_kb21_single_source_form import NOW


class PDFReportsTests(unittest.TestCase):
    def test_paired_pdf_contains_real_pre_kickoff_two_model_probs(self):
        form, fm, xg, xm = inputs()
        day = form["days"][0]
        freeze = freeze_pair(day["day"], fm, day, shadow_snapshot(form, day),
                             xm, xg["days"][0], now=NOW+timedelta(seconds=3))
        self.assertEqual(freeze["paired_count"],1)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"paired.pdf"
            paired_pdf(freeze,target)
            self.assertTrue(target.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(target.stat().st_size,3000)

    def test_zero_paired_predictions_still_has_transparent_pdf(self):
        form,fm,xg,xm=inputs()
        day=form["days"][0]
        freeze=freeze_pair(day["day"],fm,day,shadow_snapshot(form,day),
                           xm,xg["days"][0],now=NOW+timedelta(seconds=3))
        freeze["pairs"]=[]
        freeze["paired_count"]=0
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"zero.pdf"
            paired_pdf(freeze,target)
            self.assertTrue(target.read_bytes().startswith(b"%PDF-"))

    def test_market_or_unsafe_data_cannot_be_published(self):
        form,fm,xg,xm=inputs()
        day=form["days"][0]
        freeze=freeze_pair(day["day"],fm,day,shadow_snapshot(form,day),
                           xm,xg["days"][0],now=NOW+timedelta(seconds=3))
        with tempfile.TemporaryDirectory() as tmp:
            contaminated=deepcopy(freeze)
            contaminated["pairs"][0]["odds"]=1.9
            with self.assertRaisesRegex(ValueError,"contaminated"):
                paired_pdf(contaminated,Path(tmp)/"bad.pdf")
            unsafe=deepcopy(freeze)
            unsafe["safe_to_publish_play"]=True
            with self.assertRaisesRegex(ValueError,"Unverified"):
                paired_pdf(unsafe,Path(tmp)/"bad.pdf")

    def test_audit_pdf_contains_valid_results_and_missing_data(self):
        report={
            "schema":"kb21-xg-vs-goals-prospective-comparison-v1",
            "date":"2026-10-18",
            "register_writes":False,"original_kb21_n_effect":0,
            "safe_to_publish_play":False,
            "paired_pregame_forecasts":2,"distinct_settled_FT_matches":1,
            "unresolved":1,
            "summary":{
                "mean_1x2_brier_goals":.612,"mean_1x2_brier_xg":.598,
                "brier_1x2_xg_minus_goals":-.014,
                "mean_over25_brier_goals":.25,"mean_over25_brier_xg":.23,
                "brier_over25_xg_minus_goals":-.02,
            },
            "rows":[
                {"fixture":"ŁKS Łódź – Górnik Zabrze",
                 "full_time_goals":[2,1],"goals_baseline_brier_1x2":.612,
                 "xg_shadow_brier_1x2":.598,"status":"SETTLED_FT"},
                {"fixture":"Zagłębie Lubin – Legia Warszawa",
                 "full_time_goals":None,"goals_baseline_brier_1x2":None,
                 "xg_shadow_brier_1x2":None,"status":"NOT_STANDARD_FULL_TIME"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"audit.pdf"
            audit_pdf(report,p)
            self.assertTrue(p.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(p.stat().st_size,3000)
            report["register_writes"]=True
            with self.assertRaisesRegex(ValueError,"Unverified"):
                audit_pdf(report,p)


if __name__=="__main__":
    unittest.main()
