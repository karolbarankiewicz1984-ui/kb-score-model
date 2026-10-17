import io
import unittest
from tools.kb21_official_tff import parse_html, collect

HTML = """<html><body><h2>Trendyol Süper Lig 2026-2027 Sezonu Fikstürü</h2>
<span>8.Hafta</span>
<div>16.10.2026</div><span>20:00</span><a>ARCA ÇORUM FK</a><a>2 - 1</a><a>ÇAYKUR RİZESPOR A.Ş.</a>
<div>17.10.2026 13:30</div><a>ERZURUMSPOR FK</a><a>2 - 0</a><a>EYÜPSPOR</a>
<div>17.10.2026</div><span>16:00</span><a>AMED SPORTİF FAALİYETLER</a><a>-</a><a>TÜMOSAN KONYASPOR</a>
<div>17.10.2026</div><span>16:00</span><a>GENÇLERBİRLİĞİ</a><a>-</a><a>GALATASARAY A.Ş.</a>
<div>17.10.2026</div><span>19:00</span><a>FENERBAHÇE A.Ş.</a><a>-</a><a>CORENDON ALANYASPOR</a>
<div>18.10.2026</div><span>13:30</span><a>KASIMPAŞA A.Ş.</a><a>-</a><a>SAMSUNSPOR A.Ş.</a>
<div>18.10.2026</div><span>16:00</span><a>KOCAELİSPOR</a><a>-</a><a>GÖZTEPE A.Ş.</a>
<div>18.10.2026</div><span>19:00</span><a>İSTANBUL BAŞAKŞEHİR FK</a><a>-</a><a>GAZİANTEP FUTBOL KULÜBÜ A.Ş.</a>
<div>19.10.2026</div><span>20:00</span><a>TRABZONSPOR A.Ş.</a><a>-</a><a>BEŞİKTAŞ A.Ş.</a>
<h2>Trendyol Süper Lig 2026-2027 Sezonu Puan Cetveli</h2>
<tr><td>17.10.2026</td><td>16:00</td><td>GALATASARAY A.Ş.</td><td>-</td><td>FENERBAHÇE A.Ş.</td></tr>
</body></html>"""


class Fake(io.BytesIO):
    pass


class TFFTests(unittest.TestCase):
    def test_nine_official_fixtures_and_turkey_time_zone(self):
        data = parse_html(HTML)
        self.assertEqual(len(data["fixtures"]), 9)
        self.assertEqual(data["issues"], [])
        self.assertEqual(data["fixtures"][1]["home"], "ERZURUMSPOR FK")
        self.assertEqual(data["fixtures"][1]["kickoff_warsaw"],
                         "2026-10-17T12:30:00+02:00")

    def test_eight_scoped_events_never_sign_daily_calendar(self):
        data = collect(["2026-10-17", "2026-10-18", "2026-10-19"],
                       opener=lambda req, timeout: Fake(HTML.encode()))
        self.assertEqual([len(data["by_day"][day]) for day in data["days"]],
                         [4, 3, 1])
        self.assertEqual(data["status"], "OFFICIAL_TFF_MATCHWEEK_PARTIAL_FOR_REVIEW")
        self.assertEqual(data["calendar_gate"], "BLOCKED")
        self.assertFalse(data["reviewer_signed"])

    def test_truncated_organizer_round_rejected(self):
        fragment = HTML.replace(
            '<div>19.10.2026</div><span>20:00</span><a>TRABZONSPOR A.Ş.</a>'
            '<a>-</a><a>BEŞİKTAŞ A.Ş.</a>', "")
        result = collect(["2026-10-19"],
                         opener=lambda req, timeout: Fake(fragment.encode()))
        self.assertEqual(result["status"], "OFFICIAL_TFF_UNAVAILABLE_OR_INCOMPLETE")
        self.assertTrue(any("INCOMPLETE_VISIBLE_MATCHWEEK" in e
                            for e in result["errors"]))

    def test_no_heading_never_extracts_standings_as_matches(self):
        data = parse_html(
            "<h2>Trendyol Süper Lig Puan Cetveli</h2>"
            "<div>17.10.2026 16:00 GALATASARAY A.Ş.</div>")
        self.assertEqual(data["fixtures"], [])

    def test_unknown_http_source_stays_blocked(self):
        def fail(req, timeout):
            raise OSError("No official page")
        data = collect(["2026-10-17"], opener=fail)
        self.assertEqual(data["status"], "OFFICIAL_TFF_UNAVAILABLE_OR_INCOMPLETE")
        self.assertEqual(data["calendar_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
