"""Result-page cards may retain KNVB fixtures after they leave 'programma'."""
import io
import unittest

from tools.kb21_official_knvb_results import parse_html, collect

HTML = """<html><head><title>Uitslagen Eredivisie</title></head><body>
<h1>Uitslagen Eredivisie</h1>
<div>31 januari 2027</div><div>FC Groningen</div><span>-</span><div>N.E.C.</div>
<h2>17 oktober 2026</h2>
<div>Sparta Rotterdam</div><span>-</span><div>Willem II</div>
<div>Telstar</div><span>-</span><div>Feyenoord</div>
<div>ADO Den Haag</div><span>-</span><div>PSV</div>
<h2>16 oktober 2026</h2><div>sc Heerenveen</div><span>4-0</span><div>Excelsior</div>
</body></html>"""
DAYS = ["2026-10-17", "2026-10-18", "2026-10-19"]


class ResultPageTests(unittest.TestCase):
    def test_knvb_results_retains_ado_psv_without_signed_clock(self):
        p = parse_html(HTML)
        self.assertTrue(p["heading_found"])
        self.assertEqual(p["issues"], [])
        matches = [x for x in p["pairs"]
                   if x["date_printed"] == "2026-10-17"
                   and x["home"] == "ADO Den Haag"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["away"], "PSV")
        self.assertIsNone(matches[0]["kickoff_utc"])
        self.assertFalse(matches[0]["kickoff_time_verified"])
        self.assertFalse(matches[0]["match_result_verified"])

    def test_capture_three_day_buckets_but_never_prove_no_games(self):
        snapshot = collect(DAYS, opener=lambda request, timeout: io.BytesIO(HTML.encode()))
        self.assertEqual(snapshot["status"], "KNVB_RESULTS_DATE_PAIRS_PARTIAL")
        self.assertEqual(len(snapshot["by_day"]["2026-10-17"]), 3)
        self.assertEqual(snapshot["by_day"]["2026-10-18"], [])
        self.assertFalse(snapshot["confirmed_zero_matches"])
        self.assertFalse(snapshot["prematch_calendar_verified"])
        self.assertEqual(snapshot["calendar_gate"], "BLOCKED")

    def test_bad_page_is_unverified_not_official_zero(self):
        p = parse_html("<html><h1>Results</h1><p>ADO Den Haag PSV</p></html>")
        self.assertEqual(p["pairs"], [])
        self.assertIn("MISSING_RESULTS_HEADING", p["issues"])

    def test_no_score_separator_does_not_merge_unrelated_clubs(self):
        p = parse_html(
            "<h1>Uitslagen Eredivisie</h1><h2>17 oktober 2026</h2>"
            "<p>ADO Den Haag</p><p>PSV</p>")
        self.assertEqual(p["pairs"], [])

    def test_result_date_can_have_weekday(self):
        p = parse_html(
            "<h1>Uitslagen Eredivisie</h1><h2>zaterdag 17 oktober 2026</h2>"
            "<div>ADO Den Haag</div><span>2 - 0</span><div>PSV</div>")
        self.assertEqual(p["pairs"][0]["date_printed"], "2026-10-17")

    def test_unreachable_results_stays_no_play(self):
        def fail(request, timeout):
            raise ConnectionError("offline")
        snapshot = collect(DAYS, opener=fail)
        self.assertEqual(snapshot["status"], "KNVB_RESULTS_UNVERIFIED")
        self.assertEqual(len(snapshot["by_day"]["2026-10-17"]), 0)
        self.assertFalse(snapshot["prematch_calendar_verified"])
        self.assertEqual(snapshot["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
