"""Regression cases for Google-first KB21 forensic restoration, without API tokens."""
import unittest
import json
from pathlib import Path

from tools.kb21_google_original_restore import rebuild, parse_revision_content

HEAD = ["", "ID", "Data analizy", "Data wydarzenia", "Sport", "Liga",
        "Wydarzenie", "Rynek", "Typ", "Kurs", "P(model)", "Fair odds",
        "Implied prob.", "Edge [pp]", "EV", "Forma", "ELO/siła", "xG",
        "Dom/wyjazd", "Absencje", "Motywacja", "H2H", "Ruch kursów",
        "Value factor", "Ryzyko/dane", "KB Score", "Confidence",
        "Ryzyko", "Decyzja", "Closing odds", "CLV", "Wynik meczu",
        "Wynik zakładu", "Zysk [u]", "Brier", "Uwagi", "Źródła"]


def item(ident="24", p=".48", score="79", note=None, eventdate="2026-08-23",
         decision="KB PLAY"):
    fields = ["23", ident, "2026-08-22", eventdate, "Piłka nożna",
              "Premier League", "Everton – Crystal Palace", "1X2",
              "Everton wygra", "2.25", p] + [""] * 14 + [
              score, "7", "Średnie", decision] + [""] * 6 + [
              note if note is not None else
              "KB2.1 | STR 27/35 | QUAL 25/35 | MATCH 27/30 | SCORE 79/100",
              "https://example.org/fixture"]
    assert len(fields) == len(HEAD), (len(fields), len(HEAD))
    return fields


def csv_row(row):
    import csv
    from io import StringIO
    s = StringIO()
    writer = csv.writer(s, lineterminator="\n")
    writer.writerow(row)
    return s.getvalue()


def capture(*records):
    return "Dashboard\n" + csv_row(["\f"] + HEAD[1:]) + "".join(
        csv_row(x) for x in records) + "\f,Other,Some column\n"


def revision(num, instant, *records):
    return {"revision_id":str(num), "modified_at":instant,
            "content":capture(*records)}


class RecoverGoogleOriginalTests(unittest.TestCase):
    def test_source_row_recovered_without_retroactive_play(self):
        r = rebuild([revision(60, "2026-08-22T12:00:00Z", item())])
        self.assertEqual(r["records_reconstructed"], 1)
        v = r["records"][0]
        self.assertEqual(v["original_blocks"], [27,25,27])
        self.assertEqual(v["block_status"], "MATCH")
        self.assertEqual(v["original_sport_score"],79)
        self.assertEqual(v["original_p_model"],.48)
        self.assertEqual(v["recalculated_ev"], .08)
        self.assertEqual(v["capture_vs_event_date"], "OBSERVED_BEFORE_EVENT_DATE")
        self.assertEqual(v["historical_label_not_a_new_recommendation"], "KB PLAY")
        self.assertFalse(v["eligible_for_new_live_n"])
        self.assertFalse(r["original_p_model_formula_recovered"])

    def test_captures_on_same_day_do_not_prove_kickoff(self):
        r = rebuild([revision(60,"2026-08-23T08:10:00+00:00",item())])
        self.assertEqual(r["records"][0]["capture_vs_event_date"],
                         "SAME_EVENT_DATE_KICKOFF_UNKNOWN")
        self.assertFalse(r["records"][0]["validated_before_kickoff"])

    def test_late_capture_does_not_count_as_prematch(self):
        r = rebuild([revision(60,"2026-08-25T08:10:00Z",item())])
        self.assertEqual(r["records"][0]["capture_vs_event_date"],
                         "FIRST_OBSERVED_AFTER_EVENT_DATE")

    def test_original_first_snapshot_survives_later_settlement_edits(self):
        r = rebuild([
            revision(60,"2026-08-22T12:10:00Z",item()),
            revision(64,"2026-08-25T12:10:00Z",
                     item(p=".7",decision="KB CONTROL",
                          note="AUDYT later: settled LOSS"))
        ])
        v = r["records"][0]
        self.assertEqual(v["original_p_model"],.48)
        self.assertEqual(v["historical_label_not_a_new_recommendation"],"KB PLAY")
        self.assertEqual(v["first_observed_revision_among_sample"],"60")
        self.assertEqual(len(r["changed_model_fields_in_later_samples"]),1)
        self.assertIn("P(model)",r["changed_model_fields_in_later_samples"][0]["changed_fields"])

    def test_score_mismatch_detected(self):
        r=rebuild([revision(60,"2026-08-22T12:00:00Z",item(score="88"))])
        self.assertEqual(r["records"][0]["block_status"],"SCORE_SUM_MISMATCH")
        self.assertIn("SCORE_SUM_MISMATCH",r["records"][0]["issues"])

    def test_compact_35_35_30_is_recovered(self):
        n="N150 forward; 35/35/30=34/31/23; Pcal 83%"
        r=rebuild([revision(60,"2026-08-22T12:00:00Z",item(score="88",note=n))])
        self.assertEqual(r["records"][0]["original_blocks"],[34,31,23])
        self.assertEqual(r["records"][0]["block_status"],"MATCH")

    def test_snapshot_must_have_unique_id(self):
        with self.assertRaisesRegex(ValueError,"Duplicate Rejestr IDs"):
            rebuild([revision(60,"2026-08-22T12:00:00Z",item(),item())])

    def test_duplicate_revision_refused(self):
        r=revision(60,"2026-08-22T12:00:00Z",item())
        with self.assertRaisesRegex(ValueError,"duplicated"):
            rebuild([r,r])

    def test_after_model_start_only(self):
        a=item()
        a[3]="2026-08-15"
        a[2]="2026-08-14"
        self.assertEqual(parse_revision_content(capture(a)), [])

    def test_real_recovered_google_archive_invariants(self):
        path = (Path(__file__).resolve().parents[1] / "data" /
                "kb21_google_restore" / "original_live_recovered_2026-10-24.json")
        archived = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(archived["original_unchanged"])
        self.assertTrue(archived["n_unchanged"])
        self.assertEqual(archived["rows"], len(archived["records"]))
        self.assertEqual(archived["rows"], 179)
        self.assertEqual(archived["blocks"]["match"], 137)
        self.assertEqual(archived["blocks"]["error"], 0)
        self.assertEqual(archived["ev_anomalies"], [])
        self.assertGreater(len(archived["revisions"]), 0)
        self.assertEqual(
            set(x["archived_label"] for x in archived["records"]),
            {"KB PLAY", "KB LEARN", "KB CONTROL"})
        ids = [r["sheet_id"] for r in archived["records"]]
        self.assertEqual(len(ids), len(set(ids)))
        allowed = {"BEFORE_EVENT_DATE", "ON_EVENT_DATE_TIME_UNVERIFIED",
                   "AFTER_EVENT_DATE"}
        for row in archived["records"]:
            self.assertIn(row["time_class"], allowed)
            self.assertFalse(row["new_N"])
            self.assertFalse(row["new_PLAY"])
            self.assertFalse(row["kickoff_verified"])
            self.assertFalse(row["preprice_freeze_verified"])
            self.assertGreater(row["p_model_original"], 0)
            self.assertLess(row["p_model_original"], 1)
            self.assertLessEqual(row["sport_score_original"], 100)
            if row["components_status"] == "match":
                self.assertEqual(sum(row["components_original"]),
                                 row["sport_score_original"])
            self.assertAlmostEqual(row["ev_original"], row["ev_check"],
                                   delta=.0101)

    def test_boolean_flags_fail_closed(self):
        r=rebuild([revision(60,"2026-08-22T12:00:00Z",item())])
        self.assertFalse(r["historical_n_updated"])
        self.assertTrue(r["no_automatic_play"])


if __name__ == "__main__":
    unittest.main()
