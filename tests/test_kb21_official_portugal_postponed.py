import io
import unittest
from tools.kb21_official_portugal_postponed import (
    GIL_NEWS, BRAGA_PROGRAM, parse_gil_article,
    parse_braga_display, collect,
)

GIL = """<html><main><h2>DATA E HORA DO JOGO EM ATRASO COM O SC BRAGA</h2>
<p>Outubro 1, 2026</p><p>O jogo em atraso da jornada dois na Liga Portugal,
entre o Gil Vicente FC e o SC Braga, vai jogar-se a 19 de outubro no Estádio
Municipal de Braga. O apito inicial está marcado para as 20h15.</p>
<h2>Mais notícias</h2><p>Uma notícia diferente.</p></main></html>"""
BRAGA = """<html><main><h2>FIXTURES</h2>
<p>SC Braga vs Sporting</p><p>Oct 9, 2026, 19:15</p>
<p>SC Braga vs Gil Vicente FC</p><p>Oct 19, 2026, 19:15</p>
<p>BRAGA MUNICIPAL STADIUM</p></main></html>"""


class Fake(io.BytesIO):
    pass


def opener(request, timeout):
    url = request.full_url
    if url == GIL_NEWS:
        return Fake(GIL.encode("utf-8"))
    if url == BRAGA_PROGRAM:
        return Fake(BRAGA.encode("utf-8"))
    raise AssertionError("Unexpected URL")


class PortugalClubsTests(unittest.TestCase):
    def test_explicit_gil_local_clock_is_not_website_utc(self):
        fixture = parse_gil_article(GIL)
        self.assertEqual(fixture["home"], "SC Braga")
        self.assertEqual(fixture["away"], "Gil Vicente FC")
        self.assertEqual(fixture["gil_local_clock"], "20:15")
        self.assertEqual(fixture["kickoff_warsaw"], "2026-10-19T21:15:00+02:00")
        self.assertEqual(fixture["kickoff_utc"], "2026-10-19T19:15:00+00:00")

    def test_braga_clock_is_unzoned_and_not_converted(self):
        fixture = parse_braga_display(BRAGA)
        self.assertEqual(fixture["display_clock"], "19:15")
        self.assertIsNone(fixture["display_timezone"])
        self.assertFalse(fixture["timezone_known"])

    def test_two_clubs_have_unresolved_timezone_not_false_conflict(self):
        out = collect(["2026-10-17", "2026-10-18", "2026-10-19"],
                      opener=opener)
        self.assertEqual(out["status"], "CLUB_ARTICLE_PARTIAL_FOR_REVIEW")
        self.assertEqual(out["source_comparison"], "DISPLAY_TIMEZONE_NOT_STATED")
        self.assertEqual(len(out["by_day"]["2026-10-19"]), 1)
        self.assertEqual(out["unconfirmed_zero_dates"],
                         ["2026-10-17", "2026-10-18"])
        self.assertFalse(out["reviewer_signed"])
        self.assertFalse(out["full_calendar_verified"])
        self.assertEqual(out["calendar_gate"], "BLOCKED")

    def test_club_article_cannot_be_used_to_backfill_other_dates(self):
        out = collect(["2026-10-20"], opener=opener)
        self.assertEqual(out["by_day"]["2026-10-20"], [])
        self.assertEqual(out["unconfirmed_zero_dates"], ["2026-10-20"])

    def test_missing_official_news_cannot_claim_a_kickoff(self):
        def source(request, timeout):
            if request.full_url == GIL_NEWS:
                return Fake(b"<p>Jogo Braga Gil Vicente 20h15</p>")
            return Fake(BRAGA.encode())
        out = collect(["2026-10-19"], opener=source)
        self.assertEqual(out["by_day"]["2026-10-19"], [])
        self.assertEqual(out["status"], "NO_AUTHENTICATED_CLUB_FIXTURE")
        self.assertIn("GIL_OFFICIAL_ARTICLE_NO_EXACT_FIXTURE", out["errors"])
        self.assertEqual(out["calendar_gate"], "BLOCKED")

    def test_braga_article_missing_is_diagnostic_not_fatal(self):
        def source(request, timeout):
            if request.full_url == BRAGA_PROGRAM:
                raise OSError("web unavailable")
            return Fake(GIL.encode())
        out = collect(["2026-10-19"], opener=source)
        self.assertEqual(out["source_comparison"], "BRAGA_DISPLAY_UNAVAILABLE")
        self.assertEqual(len(out["by_day"]["2026-10-19"]), 1)
        self.assertTrue(out["errors"])
        self.assertEqual(out["calendar_gate"], "BLOCKED")

    def test_outdated_date_or_headline_not_trusted(self):
        self.assertIsNone(parse_gil_article(GIL.replace("Outubro 1, 2026",
                                                        "Outubro 1, 2025")))
        self.assertIsNone(parse_gil_article("<p>Jogo SC Braga 20h15</p>"))
        self.assertIsNone(parse_braga_display("<p>SC Braga vs Porto Oct 19, 2026, 19:15</p>"))

if __name__ == "__main__":
    unittest.main()
