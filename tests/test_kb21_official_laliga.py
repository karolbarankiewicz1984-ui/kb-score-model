import io
import unittest
from tools.kb21_official_laliga import parse_html, collect

HTML = """<table><thead><tr><th>FECHA</th><th>HORARIO</th><th>PARTIDO</th></tr></thead>
<tbody><tr><td>SAB 17.10.2026</td><td>14:00</td><td><a>RCD Espanyol de Barcelona</a> VS <a>Atlético de Madrid</a></td></tr>
<tr><td>SAB 17.10.2026</td><td>18:30</td><td>Real Betis VS FC Barcelona</td></tr>
<tr><td>DOM 18.10.2026</td><td>21:00</td><td>Real Madrid VS Sevilla FC</td></tr>
<tr><td>VIE 16.10.2026</td><td>21:00</td><td>RC Deportivo 1 - 1 Levante UD</td></tr></tbody></table>"""


class FakeResponse(io.BytesIO):
    pass


class OfficialLaLigaTests(unittest.TestCase):
    def test_matchday_and_mainland_spain_timezone(self):
        report = parse_html(HTML, 9, days=["2026-10-17", "2026-10-18"])
        self.assertTrue(report["table_recognized"])
        self.assertEqual(report["parsed_rows"], 4)
        self.assertEqual(len(report["fixtures"]), 3)
        self.assertEqual(report["fixtures"][1]["home"], "Real Betis")
        self.assertEqual(report["fixtures"][1]["kickoff_warsaw"], "2026-10-17T18:30:00+02:00")

    def test_no_table_never_means_confirmed_zero(self):
        def opener(req, timeout):
            return FakeResponse(b"<div>No data available</div>")
        report = collect(["2026-10-17"], rounds=[9], opener=opener)
        self.assertEqual(report["status"], "NO_USABLE_OFFICIAL_MATCHES")
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertEqual(len(report["errors"]), 1)

    def test_has_fixture_but_no_auto_signoff(self):
        def opener(req, timeout):
            return FakeResponse(HTML.encode("utf-8"))
        report = collect(["2026-10-17", "2026-10-18"], rounds=[9], opener=opener)
        self.assertEqual(len(report["by_day"]["2026-10-17"]), 2)
        self.assertFalse(report["full_calendar_verified"])
        self.assertFalse(report["reviewer_signed"])
        self.assertEqual(report["publication"], "DIAGNOSTIC / NO PLAY")

    def test_wrong_html_and_bad_scope_are_rejected(self):
        self.assertFalse(parse_html("<div>Real Betis VS Barcelona</div>", 9)["table_recognized"])
        with self.assertRaises(ValueError):
            collect(["2026-10-17"], rounds=[0], opener=lambda *a: None)
