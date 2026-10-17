"""2026 UEFA European Qualifiers edition is a historical source, not a day calendar."""
from io import BytesIO
import unittest

from tools.kb21_official_uefa_qualifiers_cycle import collect, parse
from tools.kb21_uefa_qualifiers_cycle_compare import compare

HTML = """<html><main>
<h1>European Qualifiers for 2026 World Cup: All the results</h1>
<p>The European Qualifiers for the 2026 FIFA World Cup ran from March to November 2025, with the play-offs for the remaining finals places taking place in March 2026.</p>
<h2>Play-off finals</h2><h3>Tuesday 31 March 2026</h3>
<p>Sweden 3-2 Poland</p><p>Bosnia and Herzegovina 1-1 Italy</p>
</main></html>"""
DAYS = ["2026-10-17", "2026-10-18", "2026-10-19"]


def queue():
    return {"days": DAYS, "fixtures": [{
        "date_warsaw": DAYS[1], "fixture_id": "fifa.worldq.uefa:111",
        "fixture": "Ukraine - Poland",
        "kickoff": "2026-10-18T20:45:00+02:00",
    }]}


class QualifiersCycleTests(unittest.TestCase):
    def test_official_historical_article_stops_at_march_2026(self):
        ok, errors = parse(HTML)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_stale_article_or_changed_format_does_not_authorize_zero(self):
        ok, errors = parse("<h1>European Qualifiers</h1>")
        self.assertFalse(ok)
        self.assertIn("HISTORICAL_2026_CYCLE_EVIDENCE_INCOMPLETE", errors)

    def test_live_collect_never_assigns_dates_or_matches(self):
        data = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        self.assertEqual(data["status"], "DOCUMENTED_HISTORICAL_CYCLE_ONLY")
        self.assertEqual(data["documented_last_playoff_day"], "2026-03-31")
        self.assertTrue(all(x == [] for x in data["by_day"].values()))
        self.assertFalse(data["confirmed_zero_matches"])
        self.assertFalse(data["full_calendar_verified"])
        self.assertEqual(data["calendar_gate"], "BLOCKED")

    def test_candidate_in_october_is_edition_conflict_not_a_verified_fixture(self):
        data = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        result = compare(queue(), data)
        sunday = result["days"][DAYS[1]]
        self.assertEqual(sunday["historical_cycle_outside_window_candidates"],
                         ["fifa.worldq.uefa:111"])
        self.assertEqual(sunday["time_approved_matches"], 0)
        self.assertFalse(sunday["no_games_certified"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_missing_source_never_attests_empty_day(self):
        def offline(req, timeout):
            raise RuntimeError("offline")
        data = collect(DAYS, opener=offline)
        self.assertEqual(data["status"], "OFFICIAL_CYCLE_SOURCE_UNVERIFIED")
        self.assertIsNone(data["documented_last_playoff_day"])
        result = compare(queue(), data)
        self.assertEqual(result["days"][DAYS[1]]["historical_cycle_outside_window_candidates"], [])
        self.assertFalse(result["days"][DAYS[1]]["no_games_certified"])

    def test_reject_spoofed_approved_and_inconsistent_cycle(self):
        d = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        d["calendar_gate"] = "PASS_MANUAL"
        with self.assertRaisesRegex(ValueError, "Invalid unsigned"):
            compare(queue(), d)
        d = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        d["day_cycle_status"][DAYS[1]] = "OFFICIAL_ZERO_FIXTURES"
        with self.assertRaisesRegex(ValueError, "contradictory"):
            compare(queue(), d)

    def test_reject_invented_historical_day_fixtures(self):
        d = collect(DAYS, opener=lambda req, timeout: BytesIO(HTML.encode()))
        d["by_day"][DAYS[0]] = [{"home": "Home", "away": "Away"}]
        with self.assertRaisesRegex(ValueError, "cannot declare dated"):
            compare(queue(), d)


if __name__ == "__main__":
    unittest.main()
