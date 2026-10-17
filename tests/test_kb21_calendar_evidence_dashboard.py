import json
from pathlib import Path
import tempfile
import unittest

from tools.kb21_calendar_evidence_dashboard import summarize, render

DAYS = ["2026-10-17", "2026-10-18"]


def queue():
    return {
        "days": DAYS,
        "fixtures": [
            {"date_warsaw": DAYS[0], "fixture_id": "eng.1:1"},
            {"date_warsaw": DAYS[0], "fixture_id": "por.1:2"},
            {"date_warsaw": DAYS[1], "fixture_id": "eng.1:3"},
        ],
    }


def gate():
    return {
        "calendar_gate": "BLOCKED",
        "days": {
            DAYS[0]: {"calendar_gate": "BLOCKED", "errors": ["missing human review"]},
            DAYS[1]: {"calendar_gate": "BLOCKED", "errors": ["no independent comparison",
                                                             "unsigned day"]},
        },
    }


def write(folder, filename, data):
    (Path(folder) / filename).write_text(json.dumps(data), encoding="utf-8")


def fake_fpl(folder, conflicting=False):
    write(folder, "official-fpl-premier-league.json", {
        "schema": "kb21-official-premier-league-fpl-v1",
        "league_id": "eng.1", "calendar_gate": "BLOCKED",
        "days": DAYS, "by_day": {
            DAYS[0]: [{"home": "Everton", "away": "Chelsea"}],
            DAYS[1]: [{"home": "Leeds", "away": "Arsenal"}],
        }, "errors": [],
    })
    write(folder, "official-fpl-vs-espn.json", {
        "days": {
            DAYS[0]: {"statuses": {"MATCHED_FOR_REVIEW": 0 if conflicting else 1}},
            DAYS[1]: {"statuses": {"MATCHED_FOR_REVIEW": 1}},
        }, "calendar_gate": "BLOCKED",
    })


def fake_portugal(folder):
    write(folder, "official-portugal-postponement.json", {
        "league_id": "por.1", "calendar_gate": "BLOCKED",
        "days": DAYS, "status": "CLUB_ARTICLE_PARTIAL_FOR_REVIEW",
        "by_day": {DAYS[0]: [{"home": "SC Braga", "away": "Gil Vicente"}], DAYS[1]: []},
        "errors": ["BRAGA_DISPLAY_UNAVAILABLE"],
    })
    write(folder, "official-portugal-vs-espn.json", {
        "days": {
            DAYS[0]: {"statuses": {"MATCHED_FOR_REVIEW": 1}},
            DAYS[1]: {"statuses": {"CLUB_ARTICLE_ONLY": 0}},
        }, "calendar_gate": "BLOCKED",
    })


class CalendarEvidenceDashboardTests(unittest.TestCase):
    def test_14_leagues_two_days_and_diagnostic_matching(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            fake_portugal(folder)
            report = summarize(queue(), gate(), folder)
        self.assertEqual(report["totals"]["league_day_cells"], 28)
        self.assertEqual(report["totals"]["candidate_fixtures"], 3)
        self.assertEqual(report["totals"]["paired_for_review"], 3)
        self.assertEqual(report["totals"]["manual_gate_errors"], 3)
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertFalse(report["safe_to_publish_play"])
        self.assertEqual(report["totals"]["days_passed_manual_gate"], 0)
        self.assertIn("NIE PLAY", render(report))

    def test_club_evidence_stays_partial_with_unresolved_second_clock(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            fake_portugal(folder)
            report = summarize(queue(), gate(), folder)
        portugal = next(x for x in report["rows"]
                        if x["day"] == DAYS[0] and x["league_id"] == "por.1")
        self.assertEqual(portugal["paired_for_review"], 1)
        self.assertEqual(portugal["evidence_status"], "SOURCE_ISSUES_REQUIRING_REVIEW")
        self.assertFalse(portugal["full_day_signed"])
        blank = next(x for x in report["rows"]
                     if x["day"] == DAYS[1] and x["league_id"] == "por.1")
        self.assertEqual(blank["evidence_status"],
                         "SOURCE_ISSUES_REQUIRING_REVIEW")
        self.assertFalse(blank["full_day_signed"])

    def test_organizer_candidate_conflict_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder, conflicting=True)
            report = summarize(queue(), gate(), folder)
        premier = next(x for x in report["rows"]
                       if x["day"] == DAYS[0] and x["league_id"] == "eng.1")
        self.assertEqual(premier["evidence_status"],
                         "MISSING_OR_CONFLICTING_CANDIDATES")
        self.assertEqual(report["totals"]["unpaired_candidates"], 2)
        self.assertIn("MISSING_OR_CONFLICTING_CANDIDATES", render(report))

    def test_empty_belgian_day_does_not_count_as_verified_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            report = summarize({"days": DAYS, "fixtures": []}, gate(), folder)
        belgium = next(x for x in report["rows"]
                       if x["day"] == DAYS[0] and x["league_id"] == "bel.1")
        self.assertEqual(belgium["espn_candidates"], 0)
        self.assertEqual(belgium["evidence_status"], "NO_DIRECT_ORGANIZER_ADAPTER")
        self.assertFalse(belgium["full_day_signed"])
        self.assertEqual(report["totals"]["without_direct_adapters"], 6)

    def test_refuse_mismatched_or_approved_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            wrong = gate()
            wrong["days"].pop(DAYS[1])
            with self.assertRaises(ValueError):
                summarize(queue(), wrong, folder)
            write(folder, "official-fpl-vs-espn.json", {
                "calendar_gate": "PASS_MANUAL", "days": {d: {} for d in DAYS},
            })
            with self.assertRaises(ValueError):
                summarize(queue(), gate(), folder)

    def test_refuse_impossible_higher_matched_count(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            write(folder, "official-fpl-vs-espn.json", {
                "calendar_gate": "BLOCKED",
                "days": {DAYS[0]: {"statuses": {"MATCHED_FOR_REVIEW": 5}},
                         DAYS[1]: {"statuses": {"MATCHED_FOR_REVIEW": 1}}},
            })
            with self.assertRaises(ValueError):
                summarize(queue(), gate(), folder)


if __name__ == "__main__":
    unittest.main()
