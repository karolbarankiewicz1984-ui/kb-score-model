import unittest
from pathlib import Path

from github_models.shots_archive import load_history
from github_models.shots_research import poisson_probability
from github_models.shots_settlement import audit
from github_models.shots_research import observation, research_probability, archived_quote_eligible, combined_match_history

CUTOFF="2026-11-24T12:00:00Z"
KICKOFF="2026-11-25T18:00:00Z"
def row(i, team="h", total=12, target=5):
    return {"fixture_id":str(i),"team_id":team,"scope":"team","source":"independent_historical",
            "kickoff_utc":"2026-11-10T18:00:00Z","published_at_utc":"2026-11-12T09:00:00Z",
            "period":"fulltime","stat_definition_verified":True,"shots_total":total,"shots_on_target":target}

class ShotsResearchTests(unittest.TestCase):
    def test_research_probability(self):
        r=research_probability([row(i) for i in range(5)],family="shots_total",
            selection="over",line=11.5,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertEqual(r["status"],"research_only_uncalibrated")
        self.assertTrue(0 < r["probability"] < 1)
    def test_insufficient_history(self):
        r=research_probability([row(1)],family="shots_on_target",selection="under",line=4.5,
            forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertIsNone(r["probability"])
    def test_no_future_leakage(self):
        r=row(1);r["published_at_utc"]="2026-11-24T13:00:00Z"
        with self.assertRaises(ValueError): observation(r,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_no_unverified_definition(self):
        r=row(1);r["stat_definition_verified"]=False
        with self.assertRaises(ValueError): observation(r,forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_no_duplicate_history(self):
        with self.assertRaises(ValueError):
            research_probability([row(1)]*5,family="shots_total",selection="over",line=10.5,
                forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
    def test_pre_match_quote(self):
        q={"bookmaker":"superbet.pl","family":"shots_total","scope":"match",
           "period":"fulltime","selection":"over","market_identity_verified":True,
           "line":22.5,"odds":1.2,"captured_at_utc":CUTOFF,"changed_at_utc":CUTOFF,
           "source":"oddspapi-v4","fixture_id":"fixture","odds_fixture_id":"odds-fixture",
           "market_id":"id","outcome_id":"outcome"}
        options = dict(fixture_kickoff_utc=KICKOFF, forecast_cutoff_utc=CUTOFF, fixture_id="fixture")
        self.assertTrue(archived_quote_eligible(q, **options))
        q["market_identity_verified"]=False
        self.assertFalse(archived_quote_eligible(q, **options))
        q["market_identity_verified"] = True
        q["changed_at_utc"] = None
        self.assertFalse(archived_quote_eligible(q, **options))
        q["changed_at_utc"] = CUTOFF
        q["captured_at_utc"] = "2026-11-24T13:00:00Z"
        self.assertFalse(archived_quote_eligible(q, **options))
    def test_pairing(self):
        r=combined_match_history([row(1,"h")],[row(1,"a",9,3)],
            forecast_cutoff_utc=CUTOFF,fixture_kickoff_utc=KICKOFF)
        self.assertEqual(r[0]["shots_total"],21)
        self.assertEqual(r[0]["shots_on_target"],8)

    def test_same_fixture_and_impossible_publication_time(self):
        r = row(1)
        args = {"forecast_cutoff_utc": CUTOFF, "fixture_kickoff_utc": KICKOFF}
        with self.assertRaisesRegex(ValueError, "target_fixture_in_history"):
            observation(r, fixture_id=1, **args)
        r["published_at_utc"] = r["kickoff_utc"]
        with self.assertRaisesRegex(ValueError, "historical_data_not_available"):
            observation(r, **args)

    def test_poisson_small_tail_and_complement(self):
        for mean, line in ((.1, 20.5), (8., 6.5), (0., 3.5), (800., 150.5)):
            with self.subTest(mean=mean):
                under = poisson_probability(mean, line, "under")
                over = poisson_probability(mean, line, "over")
                self.assertAlmostEqual(under + over, 1.)
                if 0 < mean < 1:
                    self.assertGreater(over, 0.)

    def test_real_source_coverage_and_cutoff(self):
        root = Path(__file__).resolve().parents[1]
        cutoff = "2026-11-22T15:45:00Z"
        histories, teams, _, coverage = load_history(root, cutoff)
        self.assertGreater(coverage["pitchapi_daily_files"], 30)
        self.assertGreater(coverage["pitchapi_exact_legacy_both_totals_agree"], 0)
        self.assertLess(coverage["pitchapi_exact_legacy_both_totals_agree"],
                        coverage["pitchapi_exact_legacy_both_totals_compared"])
        self.assertGreater(len(teams), 100)
        for history in histories.values():
            for item in history:
                observation(item, forecast_cutoff_utc=cutoff, fixture_kickoff_utc=KICKOFF)

    def test_empty_or_replayed_audit_never_reports_zero_loss(self):
        result = audit([({"mode": "historical_replay"}, CUTOFF)], {}, as_of_utc=CUTOFF)
        self.assertFalse(result["rows"])
        self.assertFalse(result["calibration_authorized"])
        self.assertTrue(all(row["brier"] is None and row["log_loss"] is None
                            for row in result["summary"]))



    def test_real_queue_zero_forecasts_diagnostic_without_guessing_identity(self):
        from collections import defaultdict
        from unittest.mock import patch
        from github_models.shots_shadow import freeze
        queue = {"schema": "github-models-fixture-queue-v1",
                 "generated_at_utc": "2026-11-24T09:30:00Z",
                 "fixtures": [
                     {"fixture_id": "p-100", "home": "Team Alpha", "away": "Team Beta",
                      "league": "Example league", "league_id": 5,
                      "country_code": "GB", "home_team_id": "h-1",
                      "away_team_id": "a-2", "source_provider": "PitchAPI",
                      "identity_blockers": [], "snapshot_utc": "2026-11-24T09:00:00Z",
                      "kickoff_utc": "2026-11-24T18:00:00Z"},
                     {"fixture_id": "p-101", "home": "Team C", "away": "Team D",
                      "league": "Example league", "league_id": 5, "country_code": "GB",
                      "home_team_id": "h-3", "away_team_id": "a-4",
                      "source_provider": "PitchAPI", "identity_blockers": ["ambiguous"],
                      "snapshot_utc": "2026-11-24T09:00:00Z",
                      "kickoff_utc": "2026-11-24T18:00:00Z"},
                 ]}
        with patch("github_models.shots_shadow.load_history",
                   return_value=(defaultdict(list), {}, {}, {})), patch(
                   "github_models.shots_shadow.archived_quotes",
                   return_value=({}, {"status": "exact_quotes_unavailable"})):
            result = freeze(queue, {}, ".", day="2026-11-24",
                            cutoff="2026-11-24T10:00:00Z")
        diag = result["coverage"]["queue_diagnostics"]
        self.assertEqual(result["summary"]["forecast_rows"], 0)
        self.assertEqual(diag["fixtures_checked"], 2)
        self.assertEqual(diag["reason_counts"],
                         {"unverified_prematch_fixture": 1,
                          "unverified_team_crosswalk": 1})
        self.assertEqual(diag["unmapped_pitch_team_ids"], ["a-2", "h-1"])
        self.assertEqual(diag["warning"], "no_eligible_forecasts_check_identity_and_history")
        self.assertFalse(result["calibration_authorized"])

    def test_two_pdf_workflow_surfaces_optional_shots_failures(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/multimodel-two-pdfs.yml").read_text(encoding="utf-8")
        self.assertIn("id: shots_audit", workflow)
        self.assertIn("Record independent shots health and source blockers", workflow)
        self.assertIn("MULTIMODEL_SHOTS_STATUS=", workflow)
        self.assertIn("SOURCE_BLOCKED_ZERO_FORECASTS", workflow)
        self.assertIn("name: multimodel-shots-health", workflow)
        self.assertIn("::warning::MultiModel shots:", workflow)
        self.assertIn("continue-on-error: true", workflow)

if __name__=="__main__": unittest.main()
