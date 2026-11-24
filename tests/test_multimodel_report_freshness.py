"""Regression: current PDFs must never contain yesterday's or started fixtures."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from github_models.report_freshness import (
    MIN_LEAD, StaleReportError, current_window, still_publishable,
)

NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)


def sample():
    queue = {
        "schema": "github-models-fixture-queue-v1",
        "generated_at_utc": "2026-11-24T08:00:00Z",
        "fixtures": [
            {"fixture_id": "started", "kickoff_utc": "2026-11-24T09:00:00Z"},
            {"fixture_id": "near", "kickoff_utc": "2026-11-24T10:04:00Z"},
            {"fixture_id": "future", "kickoff_utc": "2026-11-24T17:00:00Z"},
            {"fixture_id": "tomorrow", "kickoff_utc": "2026-11-25T17:00:00Z"},
        ],
    }
    market = {"as_of_utc": "2026-11-24T08:30:00Z"}
    return queue, market


class FreshDailyPdf(unittest.TestCase):
    def test_current_window_drops_started_and_too_close_without_rewriting_history(self):
        q, m = sample()
        state = current_window(q, m, now_utc=NOW)
        self.assertEqual(state["day"], "2026-11-24")
        self.assertEqual(state["eligible_fixture_ids"], ["future"])
        self.assertEqual(state["eligible_fixtures"], 1)
        self.assertEqual(state["started_or_too_close"], 2)
        self.assertEqual(len(q["fixtures"]), 4)
        self.assertTrue(still_publishable(state, now_utc=NOW))

    def test_yesterday_successful_archive_cannot_be_current(self):
        q, m = sample()
        q["generated_at_utc"] = "2026-11-22T08:00:00Z"
        m["as_of_utc"] = "2026-11-22T08:30:00Z"
        with self.assertRaisesRegex(StaleReportError, "queue_not_today_warsaw"):
            current_window(q, m, now_utc=NOW)

    def test_current_queue_with_yesterday_market_is_rejected(self):
        q, m = sample()
        m["as_of_utc"] = "2026-11-23T22:00:00Z"
        with self.assertRaisesRegex(StaleReportError, "market_not_today_warsaw"):
            current_window(q, m, now_utc=NOW)

    def test_todays_queue_older_than_six_hours_is_rejected(self):
        q, m = sample()
        q["generated_at_utc"] = "2026-11-24T03:59:59Z"
        m["as_of_utc"] = "2026-11-24T04:00:00Z"
        with self.assertRaisesRegex(StaleReportError, "queue_too_old"):
            current_window(q, m, now_utc=NOW)

    def test_future_snapshot_rejected(self):
        q, m = sample()
        m["as_of_utc"] = "2026-11-24T11:00:00Z"
        with self.assertRaisesRegex(StaleReportError, "market_from_future"):
            current_window(q, m, now_utc=NOW)

    def test_naive_timestamp_rejected(self):
        q, m = sample()
        q["generated_at_utc"] = "2026-11-24T08:00:00"
        with self.assertRaisesRegex(StaleReportError, "missing_timezone"):
            current_window(q, m, now_utc=NOW)

    def test_duplicate_fixture_id_rejected(self):
        q, m = sample()
        q["fixtures"].append(dict(q["fixtures"][0]))
        with self.assertRaisesRegex(StaleReportError, "duplicate_fixture_id"):
            current_window(q, m, now_utc=NOW)

    def test_no_more_upcoming_matches_cannot_publish_stale_picks(self):
        q, m = sample()
        q["fixtures"] = [q["fixtures"][0]]
        with self.assertRaisesRegex(StaleReportError, "no_upcoming_fixtures_today"):
            current_window(q, m, now_utc=NOW)

    def test_queue_timestamp_never_after_odds_snapshot(self):
        q, m = sample()
        m["as_of_utc"] = "2026-11-24T07:59:59Z"
        with self.assertRaisesRegex(StaleReportError, "odds_snapshot_before_queue"):
            current_window(q, m, now_utc=NOW)

    def test_recheck_rejects_if_match_starts_during_render(self):
        q, m = sample()
        state = current_window(q, m, now_utc=NOW)
        with self.assertRaisesRegex(StaleReportError, "kickoff_too_close_for_publication"):
            still_publishable(state, now_utc=NOW + timedelta(hours=6, minutes=57))

    def test_recheck_rejects_midnight_in_warsaw(self):
        q, m = sample()
        state = current_window(q, m, now_utc=NOW)
        with self.assertRaisesRegex(StaleReportError, "day_changed_during_pdf_generation"):
            still_publishable(state, now_utc=datetime(2026,11,24,23,5,tzinfo=timezone.utc))

    def test_next_local_day_not_equal_utc_day(self):
        q, m = sample()
        now = datetime(2026, 11, 24, 23, 30, tzinfo=timezone.utc)  # 25 Nov in Warsaw
        with self.assertRaisesRegex(StaleReportError, "queue_not_today_warsaw"):
            current_window(q, m, now_utc=now)

    def test_fulltime_and_oddspapi_replay_workflow_is_explicit(self):
        root = Path(__file__).resolve().parents[1]
        production = (root / ".github/workflows/multimodel-two-pdfs.yml").read_text(encoding="utf-8")
        ci = (root / ".github/workflows/multimodel-shots-ci.yml").read_text(encoding="utf-8")
        composer = (root / "github_models/unified_output.py").read_text(encoding="utf-8")
        self.assertIn("Validate fresh Warsaw-day queue and market snapshot", production)
        self.assertIn("Recheck report at publication time", production)
        self.assertIn("CURRENT_PDF_PUBLICATION_GUARD=PASS", production)
        self.assertIn("--historical-replay", ci)
        self.assertIn("ODTWORZENIE HISTORYCZNE", composer)
        self.assertIn('parser.add_argument("--historical-replay"', composer)
        self.assertIn("if moment(f[\"kickoff_utc\"]).date().isoformat()==day", composer)


if __name__ == "__main__":
    unittest.main()
