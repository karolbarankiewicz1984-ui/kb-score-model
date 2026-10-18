"""PDF regression: meaningful pages for both frozen forecasts and FT audit."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_xg_pair_audit import write_archive
from tests.test_kb21_shadow_audit import result_feed
from tools.kb21_xg_pair_audit import compare, load_pairs
from tools.kb21_pdf_reports import forecast_pdf, audit_pdf


class CompactPdfTests(unittest.TestCase):
    def test_forecast_pdf_is_valid_compact_pregame_document(self):
        with tempfile.TemporaryDirectory() as root:
            docs=write_archive(Path(root)/"run42")
            src=docs["KB21_XG_V_GOALS_SHADOW_2026-10-18.json"]
            output=forecast_pdf(src,Path(root)/"today.pdf")
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(output.stat().st_size,1500)
            self.assertEqual(src["paired_count"],1)
            self.assertFalse(src["safe_to_publish_play"])

    def test_audit_pdf_is_valid_and_not_false_profitable_bet(self):
        with tempfile.TemporaryDirectory() as root:
            write_archive(Path(root)/"run42")
            pair,_=load_pairs(root,"2026-10-18")
            audit=compare("2026-10-18",pair,result_feed(),
                          now=datetime(2026,10,19,3,tzinfo=timezone.utc))
            output=audit_pdf(audit,Path(root)/"audit.pdf")
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(output.stat().st_size,1500)
            self.assertEqual(audit["distinct_settled_FT_matches"],1)
            self.assertFalse(audit["safe_to_publish_play"])

    def test_no_forecast_pair_still_explicitly_empty_not_fake_zero(self):
        with tempfile.TemporaryDirectory() as root:
            docs=write_archive(Path(root)/"run42")
            f=deepcopy(docs["KB21_XG_V_GOALS_SHADOW_2026-10-18.json"])
            f["pairs"]=[]
            f["paired_count"]=0
            out=forecast_pdf(f,Path(root)/"empty.pdf")
            self.assertGreater(out.stat().st_size,1500)

    def test_reject_markets_and_false_original_model(self):
        with tempfile.TemporaryDirectory() as root:
            docs=write_archive(Path(root)/"run42")
            f=deepcopy(docs["KB21_XG_V_GOALS_SHADOW_2026-10-18.json"])
            f["pairs"][0]["odds"]=1.5
            with self.assertRaisesRegex(ValueError,"Invalid"):
                forecast_pdf(f,Path(root)/"tainted.pdf")
            f=deepcopy(docs["KB21_XG_V_GOALS_SHADOW_2026-10-18.json"])
            f["original_kb21_p_model"]=.77
            with self.assertRaisesRegex(ValueError,"Only frozen"):
                forecast_pdf(f,Path(root)/"fake.pdf")

    def test_reject_inconsistent_audit(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"audit.pdf"
            with self.assertRaisesRegex(ValueError,"Only genuine"):
                audit_pdf({
                    "schema":"kb21-xg-vs-goals-prospective-comparison-v1",
                    "publication":"RESEARCH_ONLY_NOT_PLAY",
                    "safe_to_publish_play":True,
                    "register_writes":False,
                    "original_kb21_n_effect":0,
                    "paired_pregame_forecasts":0,
                    "summary":{},"rows":[]},out)

if __name__=="__main__":
    unittest.main()
