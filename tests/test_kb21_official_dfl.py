import io
import unittest
from datetime import datetime, timezone

from tools.kb21_official_dfl import SOURCE, convert, fetch, parse_table, render


HEADER = "<tr><th>Matchday</th><th>Day</th><th>Date</th><th>Kick-off (CET)</th>" \
         "<th>Kick-off (UTC)</th><th>Home Team</th><th>Away Team</th>" \
         "<th>Match Type</th><th>Features</th></tr>"


def tr(day, date, local, utc, home, away, round=6):
    columns = [str(round), day, date, local, utc, home, away, "Gold", ""]
    return "<tr>" + "".join("<td>" + value + "</td>" for value in columns) + "</tr>"


def html():
    return "<html><table>" + HEADER + (
        tr("Sat", "17-Oct-2026", "15:30", "13:30", "Hamburger SV", "VfB Stuttgart")
        + tr("Sat", "17-Oct-2026", "18:30", "16:30", "FC Bayern München", "RB Leipzig")
        + tr("Sun", "18-Oct-2026", "15:30", "13:30", "Bayer 04 Leverkusen",
             "Sport-Club Freiburg")
        + tr("Fri", "16-Oct-2026", "20:30", "18:30",
             "Eintracht Frankfurt", "1. FC Köln")) + "</table></html>"


class FakeResponse(io.BytesIO):
    pass


class OfficialDflTests(unittest.TestCase):
    def test_extract_public_fixture_table_with_utc_time_and_polish_dst(self):
        data = convert(html(), ["2026-10-17", "2026-10-18", "2026-10-19"],
                       captured_at=datetime(2026, 10, 17, 9, tzinfo=timezone.utc))
        self.assertTrue(data["table_headers_detected"])
        self.assertEqual(data["page_fixture_rows"], 4)
        self.assertEqual(len(data["by_day"]["2026-10-17"]), 2)
        self.assertEqual(len(data["by_day"]["2026-10-18"]), 1)
        self.assertEqual(data["by_day"]["2026-10-19"], [])
        fixture = data["by_day"]["2026-10-17"][0]
        self.assertEqual(fixture["home"], "Hamburger SV")
        self.assertEqual(fixture["kickoff_utc"], "2026-10-17T13:30:00+00:00")
        self.assertEqual(fixture["kickoff_warsaw"], "2026-10-17T15:30:00+02:00")
        self.assertFalse(data["full_day_coverage_verified"])
        self.assertEqual(data["calendar_gate"], "BLOCKED")
        self.assertIn("NO PLAY", render(data))

    def test_suspect_invalid_fixture_row_blocks_interpretation(self):
        broken = "<table>" + HEADER + tr(
            "Sat", "invalid-date", "15:30", "13:30", "A", "B") + "</table>"
        data = convert(broken, ["2026-10-17"])
        self.assertEqual(data["status"], "OFFICIAL_TABLE_UNUSABLE_OR_INCOMPLETE")
        self.assertEqual(data["page_invalid_row_count"], 1)
        self.assertEqual(data["by_day"]["2026-10-17"], [])

    def test_empty_page_does_not_approve_any_empty_day(self):
        data = convert("<html>Welcome</html>", ["2026-10-17"])
        self.assertFalse(data["table_headers_detected"])
        self.assertFalse(data["full_day_coverage_verified"])
        self.assertEqual(data["status"], "OFFICIAL_TABLE_UNUSABLE_OR_INCOMPLETE")

    def test_duplicate_rows_never_count_as_two_official_fixtures(self):
        base = tr("Sat", "17-Oct-2026", "15:30", "13:30", "A", "B")
        result = parse_table("<table>" + HEADER + base + base + "</table>")
        self.assertEqual(result["extracted_match_count"], 1)
        self.assertEqual(result["invalid_rows"][0]["reason"], "DUPLICATE_FIXTURE")

    def test_official_fetch_uses_bounded_public_url(self):
        def opener(request, timeout):
            self.assertEqual(request.full_url, SOURCE)
            return FakeResponse(html().encode("utf-8"))
        result = fetch(["2026-10-17"], opener=opener,
                       captured_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
        self.assertEqual(result["page_fixture_rows"], 4)
        self.assertEqual(result["status"], "OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW")


if __name__ == "__main__":
    unittest.main()
