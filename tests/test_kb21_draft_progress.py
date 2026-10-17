"""Regression: source prefill must visibly reduce REAL data gaps, never approval."""
import copy
import unittest

from tests.test_kb21_calendar_signoff import sample
from tools.kb21_draft_progress import analyze, render


def fixtures():
    queue, manually_signed = sample()
    template = copy.deepcopy(manually_signed)
    template["approval"] = None
    template["daily_approvals"] = {day: None for day in template["days"]}
    for daily in template["days"].values():
        for record in daily.values():
            record.update({"fixtures": [], "captured_at": None,
                           "reviewer": None, "full_day_checked": False,
                           "confirmed_zero_matches": None})
    prepared = copy.deepcopy(template)
    prepared["days"]["2026-10-18"]["eng.1"]["fixtures"] = [{
        "home": "Home FC", "away": "Away FC",
        "kickoff": "2026-10-18T18:00:00+02:00"
    }]
    prepared["days"]["2026-10-18"]["eng.1"].update({
        "organizer_facts_source": "https://fantasy.premierleague.com/api/fixtures/",
        "organizer_facts_capture_utc": "2026-10-17T08:00:00Z",
        "organizer_source_catalogue_kind": "FULL_SEASON_380_FPL",
    })
    return queue, template, prepared


class HonestEvidenceProgressTests(unittest.TestCase):
    def test_reconciled_game_reduces_data_errors_not_human_errors(self):
        queue, template, prepared = fixtures()
        report = analyze(queue, template, prepared)
        self.assertEqual(report["competition_day_cells"], 14)
        self.assertEqual(report["human_reviewed_cells"], 0)
        self.assertEqual(report["human_approval_days"], 0)
        self.assertEqual(report["gate"], "BLOCKED")
        self.assertFalse(report["safe_to_publish_play"])
        self.assertEqual(report["net_reduction_in_formal_errors"], 3)
        self.assertEqual(report["actual_blockers_resolved_vs_template"][
            "ZERO_MATCHES_NOT_CONFIRMED_BY_ORGANIZER"], 1)
        self.assertEqual(report["actual_blockers_resolved_vs_template"][
            "OFFICIAL_VS_INDEPENDENT_FIXTURE_COUNT_DIFFERENCE"], 1)
        self.assertEqual(report["actual_blockers_resolved_vs_template"][
            "INDEPENDENT_MATCHES_UNEXPLAINED"], 1)
        for required in (
                "MISSING_INDEPENDENT_REVIEWER",
                "OFFICIAL_DAY_NOT_VERIFIED_COMPLETE",
                "MISSING_TIMESTAMPED_ORGANIZER_CAPTURE"):
            self.assertEqual(report["prepared"]["errors_by_code"][required], 14)
        self.assertIn("0/14", render(report))
        self.assertEqual(report["prepared"]["cells_with_machine_capture_metadata"], 1)

    def test_empty_sourcing_is_never_called_progress(self):
        queue, empty, _ = fixtures()
        report = analyze(queue, empty, copy.deepcopy(empty))
        self.assertEqual(report["net_reduction_in_formal_errors"], 0)
        self.assertEqual(report["prepared"]["fixture_rows_ready_for_human_inspection"], 0)
        self.assertEqual(report["prepared"]["missing_evidence_occurrences"],
                         report["baseline"]["missing_evidence_occurrences"])

    def test_reject_signed_approval_and_human_flags(self):
        queue, template, prepared = fixtures()
        prepared["approval"] = {"reviewer": "fake"}
        with self.assertRaisesRegex(ValueError, "signed global"):
            analyze(queue, template, prepared)
        _, template, prepared = fixtures()
        prepared["days"]["2026-10-18"]["eng.1"]["reviewer"] = "fake"
        with self.assertRaisesRegex(ValueError, "human signoffs"):
            analyze(queue, template, prepared)
        _, template, prepared = fixtures()
        prepared["days"]["2026-10-18"]["eng.1"]["captured_at"] = "2026-10-17T08:00:00Z"
        with self.assertRaisesRegex(ValueError, "human signoffs"):
            analyze(queue, template, prepared)
        _, template, prepared = fixtures()
        prepared["days"]["2026-10-18"]["eng.1"]["confirmed_zero_matches"] = True
        with self.assertRaisesRegex(ValueError, "human signoffs"):
            analyze(queue, template, prepared)

    def test_reject_missing_league_or_mismatched_dates(self):
        queue, template, prepared = fixtures()
        prepared["days"]["2026-10-18"].pop("bel.1")
        with self.assertRaisesRegex(ValueError, "14 competitions"):
            analyze(queue, template, prepared)
        _, template, prepared = fixtures()
        prepared["days"]["2026-10-18"]["eng.1"]["fixtures"] = None
        with self.assertRaisesRegex(ValueError, "fixture lists"):
            analyze(queue, template, prepared)
        _, template, prepared = fixtures()
        template["days"]["2026-10-19"] = template["days"].pop("2026-10-18")
        with self.assertRaisesRegex(ValueError, "window mismatch"):
            analyze(queue, template, prepared)


if __name__ == "__main__":
    unittest.main()
