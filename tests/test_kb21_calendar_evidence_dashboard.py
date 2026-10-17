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
        self.assertEqual(belgium["evidence_status"], "DIRECT_SOURCE_MISSING")
        self.assertFalse(belgium["full_day_signed"])
        self.assertEqual(report["totals"]["without_direct_adapters"], 1)

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


    def test_outside_competition_scope_is_not_silently_counted_as_matched(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            fake_portugal(folder)
            extra = queue()
            extra["fixtures"].append({
                "date_warsaw": DAYS[0], "fixture_id": "other.tournament:99"
            })
            report = summarize(extra, gate(), folder)
        totals = report["totals"]
        self.assertEqual(totals["candidate_fixtures"], 4)
        self.assertEqual(totals["paired_for_review"], 3)
        self.assertEqual(totals["unpaired_candidates"], 1)
        self.assertEqual(totals["outside_competition_scope"], 1)
        self.assertEqual(totals["outside_competition_scope_ids"],
                         ["other.tournament:99"])
        self.assertIn("other.tournament:99", render(report))
        self.assertFalse(report["safe_to_publish_play"])

    def test_queue_date_outside_review_window_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            extra = queue()
            extra["fixtures"].append({
                "date_warsaw": "2026-10-20", "fixture_id": "eng.1:100"
            })
            with self.assertRaisesRegex(ValueError, "outside reviewed dates"):
                summarize(extra, gate(), folder)

    def test_invalid_fixture_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            extra = queue()
            extra["fixtures"][0]["fixture_id"] = None
            with self.assertRaisesRegex(ValueError, "fixture identifier"):
                summarize(extra, gate(), folder)


    def test_review_plan_prioritizes_source_errors_and_never_approves_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_fpl(folder)
            fake_portugal(folder)
            report = summarize(queue(), gate(), folder)
        rows = {(r["day"], r["league_id"]): r for r in report["rows"]}
        portugal = rows[(DAYS[0], "por.1")]
        premier = rows[(DAYS[0], "eng.1")]
        belgium = rows[(DAYS[0], "bel.1")]
        self.assertEqual(portugal["review_priority"], 1)
        self.assertEqual(portugal["next_action"],
                         "RESOLVE_OFFICIAL_SOURCE_OR_FIXTURE_CONFLICT")
        self.assertEqual(premier["review_priority"], 2)
        self.assertEqual(premier["next_action"],
                         "VERIFY_FULL_ORGANIZER_DAY_AND_SIGN")
        self.assertEqual(belgium["review_priority"], 3)
        self.assertEqual(belgium["next_action"],
                         "VERIFY_OFFICIAL_ZERO_OR_MISSING_FIXTURES")
        self.assertTrue(premier["organizer_review_url"].startswith("https://"))
        markdown = render(report)
        self.assertIn("Praktyczna kolejka kontroli", markdown)
        self.assertIn("P1 Liga Portugal", markdown)
        self.assertIn("P3 Belgian Pro League", markdown)
        self.assertIn("źródło organizatora", markdown)
        self.assertFalse(report["safe_to_publish_play"])


    def test_uefa_official_article_pairs_only_date_and_teams(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "official-uefa-europa.json", {
                "league_id": "uefa.europa", "calendar_gate": "BLOCKED",
                "days": DAYS, "by_day": {
                    DAYS[0]: [{"home": "Lech Poznań", "away": "Sunderland"}],
                    DAYS[1]: [],
                }, "errors": [], "kickoff_timezone_verified": False,
            })
            write(folder, "official-uefa-europa-vs-espn.json", {
                "calendar_gate": "BLOCKED",
                "days": {DAYS[0]: {"statuses": {}, "date_team_matched": 1},
                         DAYS[1]: {"statuses": {}, "date_team_matched": 0}},
            })
            q = {"days": DAYS, "fixtures": [{
                "date_warsaw": DAYS[0], "fixture_id": "uefa.europa:987",
                "fixture": "Lech Poznań - Sunderland",
            }]}
            report = summarize(q, gate(), folder)
        row = next(x for x in report["rows"]
                   if x["league_id"] == "uefa.europa" and x["day"] == DAYS[0])
        self.assertEqual(row["evidence_status"], "DATE_TEAMS_ONLY_TIME_UNVERIFIED")
        self.assertEqual(row["date_team_only_matches"], 1)
        self.assertEqual(row["paired_for_review"], 0)
        self.assertEqual(row["review_priority"], 1)
        self.assertEqual(report["totals"]["unpaired_candidates"], 1)
        self.assertEqual(report["totals"]["date_team_only_not_time_approved"], 1)
        self.assertEqual(report["totals"]["direct_adapters"], 13)
        self.assertFalse(report["safe_to_publish_play"])


    def test_belgium_selected_round_not_dated_not_valid_for_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "official-belgium-selected-round.json", {
                "league_id": "bel.1", "calendar_gate": "BLOCKED", "days": DAYS,
                "date_verified": False, "kickoff_timezone_verified": False,
                "errors": [], "undated_fixtures": [
                    {"home": "KV Kortrijk", "away": "KV Mechelen",
                     "date_warsaw": None, "kickoff_warsaw": None}],
                "by_day": {day: [] for day in DAYS},
            })
            write(folder, "official-belgium-vs-espn.json", {
                "calendar_gate": "BLOCKED",
                "days": {day: {"statuses": {}} for day in DAYS},
            })
            data = {"days": DAYS, "fixtures": [{
                "date_warsaw": DAYS[0], "fixture_id": "bel.1:111"
            }]}
            report = summarize(data, gate(), folder)
        row = next(x for x in report["rows"]
                   if x["day"] == DAYS[0] and x["league_id"] == "bel.1")
        self.assertEqual(row["evidence_status"],
                         "UNDATED_OFFICIAL_ROUND_REQUIRES_REVIEW")
        self.assertEqual(row["paired_for_review"], 0)
        self.assertEqual(row["undated_organizer_round_rows"], 1)
        self.assertEqual(row["review_priority"], 1)
        self.assertEqual(report["totals"]["unpaired_candidates"], 1)
        self.assertEqual(report["totals"]["undated_organizer_round_rows"], 1)
        self.assertFalse(report["safe_to_publish_play"])


if __name__ == "__main__":
    unittest.main()
