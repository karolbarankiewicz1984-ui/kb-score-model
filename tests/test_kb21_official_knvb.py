import io
import unittest
from tools.kb21_official_knvb import parse_html, collect

HTML = """<html><head><title>Programma Eredivisie</title></head>
<body><nav>Programma Eredivisie wedstrijden</nav><main>
<h1>Programma Eredivisie</h1>
<h2>zaterdag 17 oktober 2026</h2>
<div>ADO Den Haag</div><img src="x"/><span>16:30</span><div>PSV</div>
<div>Telstar</div><span>20:00</span><div>Feyenoord</div>
<div>Sparta Rotterdam</div><span>21:00</span><div>Willem II</div>
<h2>zondag 18 oktober 2026</h2>
<div>PEC Zwolle</div><span>12:15</span><div>Go Ahead Eagles</div>
<div>SC Cambuur</div><span>14:30</span><div>AZ</div>
<div>FC Groningen</div><span>16:45</span><div>Ajax</div>
<div>N.E.C.</div><span>20:00</span><div>Fortuna Sittard</div>
<div>FC Twente</div><span>20:00</span><div>FC Utrecht</div>
<h2>vrijdag 23 oktober 2026</h2><p>Go Ahead Eagles</p><p>20:00</p><p>Telstar</p>
</main><footer>More clubs PSV Ajax</footer></body></html>"""


class Fake(io.BytesIO):
    pass


class KNVBTests(unittest.TestCase):
    def test_eight_weekend_pairs_and_local_kickoff(self):
        parsed = parse_html(HTML)
        self.assertTrue(parsed["heading_found"])
        self.assertEqual(len(parsed["fixtures"]), 9)
        self.assertEqual([f["home"] for f in parsed["fixtures"][:3]],
                         ["ADO Den Haag", "Telstar", "Sparta Rotterdam"])
        self.assertEqual(parsed["fixtures"][0]["kickoff_warsaw"],
                         "2026-10-17T16:30:00+02:00")

    def test_missing_monday_is_not_certified_zero(self):
        result = collect(["2026-10-17", "2026-10-18", "2026-10-19"],
                         opener=lambda req, timeout: Fake(HTML.encode()))
        self.assertEqual([len(result["by_day"][d]) for d in result["days"]], [3, 5, 0])
        self.assertEqual(result["unconfirmed_zero_dates"], ["2026-10-19"])
        self.assertEqual(result["status"], "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW")
        self.assertEqual(result["calendar_gate"], "BLOCKED")
        self.assertFalse(result["reviewer_signed"])

    def test_missing_program_heading_fails_closed(self):
        result = collect(["2026-10-17"], opener=lambda req, timeout:
                         Fake(b"<p>ADO Den Haag</p><p>16:30</p><p>PSV</p>"))
        self.assertEqual(result["status"], "OFFICIAL_KNVB_UNAVAILABLE_OR_UNREADABLE")
        self.assertTrue(result["errors"])
        self.assertEqual(result["by_day"]["2026-10-17"], [])

    def test_clubs_without_kickoff_never_match(self):
        html = ("<h1>Programma Eredivisie</h1>"
                "<h2>zaterdag 17 oktober 2026</h2><p>Ajax</p><p>PSV</p>")
        self.assertEqual(parse_html(html)["fixtures"], [])

    def test_split_date_and_split_club_text(self):
        html = ("<h1>Programma Eredivisie</h1>"
                "<p>zaterdag <b>17</b> oktober 2026</p>"
                "<div>FC <b>Twente</b></div><span>20:00</span><p>Ajax</p>")
        self.assertEqual(parse_html(html)["fixtures"][0]["home"], "FC Twente")

    def test_http_failure_stays_diagnostic(self):
        def fail(req, timeout):
            raise OSError("unreachable")
        result = collect(["2026-10-17"], opener=fail)
        self.assertEqual(result["status"], "OFFICIAL_KNVB_UNAVAILABLE_OR_UNREADABLE")
        self.assertEqual(result["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
