import io
import unittest
from tools.kb21_official_press_fixtures import collect, parse

ITALY = """<main><h1>The referees for the 7th round</h1>
<p>The referees of Serie A 2026/2027</p>
<p>FROSINONE – SASSUOLO&nbsp;&nbsp;16/10 h. 20.45</p>
<p>MARCHETTI (TRINCHIERI – LAUDATO) VAR: DI PAOLO</p>
<p>VENEZIA – NAPOLI 17/10 h. 15.00</p>
<p>BOLOGNA – INTER 17/10 h. 18.00</p>
<p>ROMA – GENOA 17/10 h. 20.45</p>
<p>UDINESE – LECCE 18/10 h. 12.30</p>
<p>FIORENTINA – COMO 18/10 h. 15.00</p>
<p>MILAN – ATALANTA 18/10 h. 18.00</p>
<p>JUVENTUS – LAZIO 18/10 h. 20.45</p>
<p>MONZA – CAGLIARI 19/10 h. 18.30</p>
<p>PARMA – TORINO 19/10 h. 20.45</p></main>"""

FRANCE = """<main><h1>Programmations TV : J7 et J8</h1>
<h3>7e journée de Ligue 1 McDonald's</h3>
<p>Vendredi 16 octobre 2026 à 20h45 sur Ligue 1+</p><p>Le Mans FC – Toulouse FC</p>
<p>Samedi 17 octobre 2026 à 17h15 sur Ligue 1+</p>
<p>RC Strasbourg Alsace – Paris Saint-Germain</p>
<p>Samedi 17 octobre 2026 à 20h45 sur Ligue 1+</p>
<p>LOSC – Stade Brestois 29<br>ESTAC Troyes – RC Lens</p>
<p>Dimanche 18 octobre 2026 à 15h00 sur Ligue 1+</p>
<p>Angers SCO – Olympique de Marseille</p>
<p>Dimanche 18 octobre 2026 à 17h15 sur Ligue 1+</p>
<p>Paris FC – Stade Rennais FC<br>FC Lorient – AS Monaco<br>Havre AC – AJ Auxerre</p>
<p>Dimanche 18 octobre 2026 à 20h45 sur Ligue 1+</p><p>Olympique Lyonnais – OGC Nice</p>
<h3>8e journée de Ligue 1 McDonald's</h3>
<p>Vendredi 23 octobre 2026 à 20h45 sur Ligue 1+</p>
<p>Stade Brestois 29 – OGC Nice</p>
<p>Samedi 24 octobre 2026 à 17h15 sur Ligue 1+</p>
<p>Toulouse FC – ESTAC Troyes</p>
<p>Langue du site</p><p>RC Lens – Paris FC</p></main>"""


class Fake(io.BytesIO):
    pass


class PressTests(unittest.TestCase):
    def test_serie_a_complete_7th_round_dated_announcement(self):
        fixtures = parse("ita.1", ITALY)
        self.assertEqual(len(fixtures), 10)
        self.assertEqual(fixtures[1]["home"], "Venezia")
        self.assertEqual(fixtures[1]["away"], "Napoli")
        self.assertEqual(fixtures[1]["kickoff_warsaw"],
                         "2026-10-17T15:00:00+02:00")
        self.assertEqual(fixtures[1]["kickoff_utc"],
                         "2026-10-17T13:00:00+00:00")
        self.assertEqual({f["source_kind"] for f in fixtures},
                         {"DATED_ORGANIZER_PRESS_RELEASE"})

    def test_ligue1_multiple_matches_at_same_time_and_round_boundary(self):
        fixtures = parse("fra.1", FRANCE)
        self.assertEqual(len(fixtures), 11)
        self.assertEqual(len([f for f in fixtures
                              if f["date_warsaw"] == "2026-10-17"]), 3)
        self.assertEqual(len([f for f in fixtures
                              if f["date_warsaw"] == "2026-10-18"]), 5)
        self.assertTrue(any(f["home"] == "FC Lorient"
                            and f["away"] == "AS Monaco" for f in fixtures))
        self.assertTrue(any(f["date_warsaw"] == "2026-10-23" for f in fixtures))

    def test_source_does_not_authorize_empty_new_week(self):
        report = collect("ita.1", ["2026-10-23"], opener=lambda req, timeout:
                         Fake(ITALY.encode("utf-8")))
        self.assertEqual(report["by_day"]["2026-10-23"], [])
        self.assertIn("2026-10-23", report["days_outside_article_range"])
        self.assertEqual(report["status"], "OFFICIAL_DATED_ARTICLE_PARTIAL_FOR_REVIEW")
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertFalse(report["reviewer_signed"])

    def test_france_source_http_failure_never_signs_off(self):
        def fail(req, timeout):
            raise OSError("temporary outage")
        report = collect("fra.1", ["2026-10-17"], opener=fail)
        self.assertEqual(report["status"], "UNVERIFIED_SOURCE_OR_PARSER_ERROR")
        self.assertTrue(report["errors"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")

    def test_incomplete_announcement_is_explicitly_flagged(self):
        # A partially parsed HTML page can look convincing; it must not
        # be accepted as the original organizer's full announcement.
        fragment = ITALY.replace("<p>PARMA – TORINO 19/10 h. 20.45</p>", "")
        result = collect("ita.1", ["2026-10-17"], opener=lambda req, timeout:
                         Fake(fragment.encode("utf-8")))
        self.assertEqual(result["parsed_article_fixture_count"], 9)
        self.assertEqual(result["expected_article_fixture_count"], 10)
        self.assertTrue(any("Incomplete organizer article" in e
                            for e in result["errors"]))
        self.assertEqual(result["status"], "UNVERIFIED_SOURCE_OR_PARSER_ERROR")
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_day_inside_french_article_window_without_fixtures_is_not_zero(self):
        result = collect("fra.1", ["2026-10-18", "2026-10-19", "2026-10-23"],
                         opener=lambda req, timeout: Fake(FRANCE.encode("utf-8")))
        self.assertEqual(result["by_day"]["2026-10-19"], [])
        self.assertIn("2026-10-19",
                      result["days_without_article_fixture_evidence"])
        self.assertNotIn("2026-10-19", result["days_outside_article_range"])
        self.assertNotIn("2026-10-18",
                         result["days_without_article_fixture_evidence"])
        self.assertEqual(result["expected_article_fixture_count"], 18)
        self.assertEqual(result["status"], "UNVERIFIED_SOURCE_OR_PARSER_ERROR")
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_wrong_content_or_unknown_league_fails_closed(self):
        self.assertEqual(parse("ita.1", "<p>ROMA – GENOA 17/10 h. 20.45</p>"), [])
        self.assertEqual(parse("fra.1", "<p>Olympique Lyonnais – OGC Nice</p>"), [])
        with self.assertRaises(ValueError):
            collect("eng.1", ["2026-10-17"])

    def test_italy_filters_dates_without_proving_zero_day(self):
        report = collect("ita.1", ["2026-10-17", "2026-10-18"],
                         opener=lambda req, timeout: Fake(ITALY.encode("utf-8")))
        self.assertEqual(len(report["by_day"]["2026-10-17"]), 3)
        self.assertEqual(len(report["by_day"]["2026-10-18"]), 4)
        self.assertEqual(report["parsed_article_fixture_count"], 10)
        self.assertFalse(report["full_calendar_verified"])


if __name__ == "__main__":
    unittest.main()
