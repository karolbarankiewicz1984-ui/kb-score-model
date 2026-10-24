"""Prospective/manual KB Score scoring cannot become historical PLAY."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_single_source_worklist import inputs
from tools.kb21_single_source_worklist import build as worklist
from tools.kb21_premarket_intake import build, render, write


def source():
    m, c, fm, forms = inputs()
    x = worklist(m, c, fm, forms)
    return {k: v for k, v in x.items() if k != "days"}, {
        row["date"]: row for row in x["days"]
    }


def assessment(record):
    source_note = {
        "url": "https://example.org/fixtures/123",
        "observed_at": "2026-10-18T07:55:00+00:00",
        "note": "Before market capture, independently observed factual team profile",
    }
    return {
        "fixture_id": record["fixture_id"],
        "fixture": record["fixture"],
        "date_warsaw": record["date_warsaw"],
        "source_snapshot_utc": record["source_snapshot_utc"],
        "kickoff": record["kickoff_utc"],
        "market": "Under 2.5 goals", "analyst": "Named human analyst",
        "reasoning": "Manual sport judgement with uncertainty and opposing case",
        "str": 25, "qual": 24, "match": 19,
        "str_evidence": [source_note],
        "qual_evidence": [source_note],
        "match_evidence": [source_note],
        "p_model": 0.57,
        "p_model_method": "Separate subjective manual calibration with factual evidence and opponent consideration",
        "confidence": 6,
        "freeze_at": "2026-10-18T08:00:00+00:00",
        "submitted_at": "2026-10-18T08:01:00+00:00",
    }


NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


class PremarketIntakeTests(unittest.TestCase):
    def test_no_submission_never_generates_probabilities(self):
        manifest, dates = source()
        result = build(manifest, dates, now=NOW)
        self.assertEqual(result["total_fixtures"], 2)
        self.assertEqual(result["submitted_assessments"], 0)
        self.assertEqual(result["format_validated_pending_review"], 0)
        self.assertEqual(result["automatic_p_model_count"], 0)
        self.assertEqual(result["kb21_n_effect"], 0)
        self.assertFalse(result["register_writes"])
        self.assertFalse(result["safe_to_publish_play"])
        self.assertFalse(result["original_p_model_formula_recovered"])
        self.assertIn("NO PLAY", render(result["days"][0]))
        with tempfile.TemporaryDirectory() as d:
            write(result, d)
            self.assertTrue((Path(d) / "KB21_PREMARKET_REVIEW_MANIFEST.json").is_file())
            self.assertEqual(len(list(Path(d).glob("*"))), 5)

    def test_manual_evidence_is_counted_but_never_published(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        result = build(m, d, [a], now=NOW)
        self.assertEqual(result["format_validated_pending_review"], 1)
        self.assertEqual(result["days"][0]["rows"][0]["sport_score"], 68)
        self.assertEqual(result["days"][0]["rows"][0]["p_model"], .57)
        self.assertEqual(result["days"][0]["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["days"][0]["rows"][0]["safe_to_publish_play"])

    def test_odds_and_outcomes_in_assessment_are_contamination(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        a["odds"] = 1.81
        a["result"] = "WIN"
        result = build(m, d, [a], now=NOW)
        self.assertEqual(result["invalid_assessments"], 1)
        self.assertIsNone(result["days"][0]["rows"][0]["p_model"])

    def test_broken_identity_and_foreign_fixture_refused(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        a["fixture_id"] = 999999
        with self.assertRaisesRegex(ValueError, "foreign"):
            build(m, d, [a], now=NOW)
        a = assessment(d[m["dates"][0]]["records"][0])
        a["kickoff"] = "2026-10-25T16:00:00+01:00"
        x = build(m, d, [a], now=NOW)
        self.assertEqual(x["invalid_assessments"], 1)
        self.assertTrue(any("not identical" in e for e in x["days"][0]["rows"][0]["errors"]))

    def test_no_retroactive_or_fabricated_freeze(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        a["freeze_at"] = "2026-10-18T03:00:00+00:00"
        self.assertEqual(build(m, d, [a], now=NOW)["invalid_assessments"], 1)
        a = assessment(d[m["dates"][0]]["records"][0])
        a["submitted_at"] = "2026-10-18T15:00:00+00:00"
        self.assertEqual(build(m, d, [a], now=NOW)["invalid_assessments"], 1)
        a = assessment(d[m["dates"][0]]["records"][0])
        a["freeze_at"] = "2026-10-18T10:00:00+00:00"
        self.assertEqual(build(m, d, [a], now=NOW)["invalid_assessments"], 1)

    def test_missing_evidence_rejected(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        a["str_evidence"] = []
        self.assertEqual(build(m, d, [a], now=NOW)["invalid_assessments"], 1)

    def test_refuses_broken_worklist_manifest_or_forged_auto_score(self):
        m, d = source()
        x = deepcopy(m)
        x["register_writes"] = True
        with self.assertRaisesRegex(ValueError, "strict two-day"):
            build(x, d, now=NOW)
        d[m["dates"][0]]["records"][0]["original_kb21_p_model"] = .7
        with self.assertRaisesRegex(ValueError, "contaminated"):
            build(m, d, now=NOW)

    def test_duplicate_assessment_refused(self):
        m, d = source()
        a = assessment(d[m["dates"][0]]["records"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build(m, d, [a, deepcopy(a)], now=NOW)


if __name__ == "__main__":
    unittest.main()
