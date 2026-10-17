"""UEFA diagnostic article tests: never promote dates into confirmed kickoffs."""
import copy
from io import BytesIO
import unittest

from tools.kb21_official_uefa_articles import SOURCES, parse, collect
from tools.kb21_uefa_article_compare import compare

HTML = """<html><main>
<h1>2026/27 Europa League: League phase fixtures by date</h1>
<h2>Matchday 2</h2><p>Thursday 15 October 2026</p>
<p>Other Club 2-1 Past Rival</p>
<h2>Matchday 3</h2><p>Thursday 22 October 2026</p>
<p>Ararat-Armenia vs AZ Alkmaar (18:45)</p>
<p>Juventus vs Rennes</p>
<p>Europa League highlights: Juventus</p>
<h2>Matchday 4</h2><p>Thursday 5 November 2026</p>
<p>Rennes vs Juventus (18:45)</p>
</main></html>"""

DAYS = ["2026-10-21", "2026-10-22", "2026-10-23"]
LEAGUE = "uefa.europa"


def record():
    return {
        "schema": "kb21-official-uefa-league-phase-v1", "league_id": LEAGUE,
        "official_url": SOURCES[LEAGUE], "days": DAYS, "errors": [],
        "calendar_gate": "BLOCKED", "kickoff_timezone_verified": False,
        "full_calendar_verified": False, "reviewer_signed": False,
        "by_day": {DAYS[0]: [], DAYS[1]: [
            {"home": "Ararat-Armenia", "away": "AZ Alkmaar", "date_printed": DAYS[1]},
            {"home": "Juventus", "away": "Rennes", "date_printed": DAYS[1]},
        ], DAYS[2]: []},
    }


def queue():
    return {"days": DAYS, "fixtures": [{
        "date_warsaw": DAYS[1], "fixture_id": LEAGUE + ":100",
        "fixture": "Ararat-Armenia - AZ Alkmaar",
        "kickoff": "2026-10-22T18:45:00+02:00",
    }]}


class OfficialUefaArticleTests(unittest.TestCase):
    def test_extract_explicit_dates_and_clubs_but_not_past_scores(self):
        rows, issues = parse(LEAGUE, HTML)
        self.assertEqual(issues, [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["date_printed"], "2026-10-22")
        self.assertEqual(rows[0]["printed_kickoff"], "18:45")
        self.assertFalse(rows[0]["kickoff_timezone_verified"])
        self.assertEqual(rows[1]["printed_kickoff"], "21:00 (UEFA default)")

    def test_all_three_club_league_phase_articles_supported(self):
        for league in ("uefa.champions", "uefa.europa", "uefa.europa.conf"):
            rows, issues = parse(league, HTML)
            self.assertEqual(len(rows), 3)
            self.assertEqual(issues, [])

    def test_uefa_nations_scoped_article_future_fixtures_no_scores_or_kickoff_approval(self):
        nations_html = """<html><main>
<h1>2026/27 UEFA Nations League: All the league phase fixtures and results</h1>
<h2>Matchday 4</h2><p>Monday 5 October</p>
<p>A1 Italy 2-0 Belgium</p>
<h2>Matchday 5</h2><p>Thursday 12 November</p>
<p>A1 Türkiye vs Belgium (18:00)</p><p>C2 Armenia vs Cyprus (18:00)</p>
<p>A1 Italy vs France</p>
<h2>Matchday 6</h2><p>Monday 16 November</p>
<p>B4 Poland vs Sweden</p>
</main></html>"""
        rows, errors = parse("uefa.nations", nations_html)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["date_printed"], "2026-11-12")
        self.assertEqual(rows[0]["printed_kickoff"], "18:00")
        self.assertEqual(rows[2]["printed_kickoff"], "20:45 (UEFA default)")
        self.assertEqual(rows[3]["home"], "Poland")
        self.assertFalse(all(row["kickoff_timezone_verified"] for row in rows))

    def test_uefa_nations_invalid_page_cannot_certify_zero(self):
        rows, errors = parse("uefa.nations", "<html><h1>Nations League</h1></html>")
        self.assertEqual(rows, [])
        self.assertIn("OFFICIAL_LEAGUE_PHASE_HEADING_NOT_FOUND", errors)

    def test_unrecognized_article_does_not_certify_empty_dates(self):
        rows, issues = parse(LEAGUE, "<p>Site changed</p>")
        self.assertEqual(rows, [])
        self.assertIn("OFFICIAL_LEAGUE_PHASE_HEADING_NOT_FOUND", issues)

    def test_snapshot_zero_in_window_is_not_verified_zero(self):
        data = HTML.encode("utf-8")
        snapshot = collect(LEAGUE, DAYS, opener=lambda request, timeout: BytesIO(data))
        self.assertEqual(snapshot["status"], "OFFICIAL_LEAGUE_PHASE_ARTICLE_PARTIAL_FOR_REVIEW")
        self.assertEqual(snapshot["article_future_fixture_count"], 3)
        self.assertEqual(len(snapshot["by_day"][DAYS[0]]), 0)
        self.assertFalse(snapshot["full_calendar_verified"])
        self.assertFalse(snapshot["kickoff_timezone_verified"])
        self.assertEqual(snapshot["calendar_gate"], "BLOCKED")

    def test_date_team_match_cannot_claim_approved_time(self):
        result = compare(queue(), record())
        row = result["days"][DAYS[1]]
        self.assertEqual(row["date_team_matched"], 1)
        self.assertEqual(row["time_approved_matches"], 0)
        self.assertEqual(row["statuses"]["DATE_TEAMS_ONLY_KICKOFF_UNVERIFIED"], 1)
        self.assertEqual(len(row["organizer_only"]), 1)
        self.assertFalse(row["no_games_certified"])
        self.assertEqual(result["calendar_gate"], "BLOCKED")

    def test_refuse_spoofed_calendar_approval_or_foreign_date(self):
        data = record()
        data["calendar_gate"] = "PASS_MANUAL"
        with self.assertRaises(ValueError):
            compare(queue(), data)
        data = record()
        data["by_day"][DAYS[1]][0]["date_printed"] = DAYS[0]
        with self.assertRaisesRegex(ValueError, "outside requested day"):
            compare(queue(), data)

    def test_no_espsn_candidates_is_not_zero_proof(self):
        q = {"days": DAYS, "fixtures": []}
        rows = compare(q, record())["days"]
        self.assertEqual(rows[DAYS[0]]["espn_count"], 0)
        self.assertFalse(rows[DAYS[0]]["no_games_certified"])


if __name__ == "__main__":
    unittest.main()
