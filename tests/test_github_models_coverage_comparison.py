import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from github_models.coverage_comparison import baseline_audit, compare


# A deliberately old external audit contract lacks identity_ready. Keeping it
# outside the test process detects accidental imports of the repaired module.
OLD_AUDIT = '''
def audit(queue, history, *, as_of_utc):
    rows = []
    for fixture in queue["fixtures"]:
        known = fixture.get("league_id") == "l_4WFCIZ" and bool(history)
        row = dict(fixture_id=fixture["fixture_id"], league=fixture["league"],
                   elo_ready=known and len(history) >= 5,
                   dixon_coles_history_ready=known and len(history) >= 30,
                   reason="ready_for_model_attempt" if known else "old_mapping_blocked")
        if known:
            row.update(mapped_home=fixture["home"], mapped_away=fixture["away"])
        rows.append(row)
    return dict(fixtures=rows, implementation_path=__file__, history_received=len(history))
'''


class CoverageComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        package = self.root / "github_models"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "coverage_audit.py").write_text(OLD_AUDIT)
        self.cutoff = "2026-11-06T08:00:00Z"
        common = dict(league="Premier League", home="A", away="B",
                      kickoff_utc="2026-11-06T20:00:00Z")
        self.queue = dict(fixtures=[
            dict(common, fixture_id="eng", league_id="l_4WFCIZ"),
            dict(common, fixture_id="rus", league_id="l_2Mh0jT"),
        ])
        self.history = [dict(fixture_id="old:" + str(i), league="Premier League",
                             country_code="ENG", home="A", away="B", home_goals=1,
                             away_goals=0, completed_at_utc="2026-11-01T20:00:00Z",
                             published_at_utc="2026-11-02T08:00:00Z") for i in range(30)]

    def tearDown(self):
        self.temporary.cleanup()

    def run_comparison(self, **options):
        return compare(self.queue, self.history, [], baseline_root=self.root,
                       as_of_utc=self.cutoff, **options)

    def test_external_import_isolated_and_foreign_leagues_remain_separate(self):
        result, reports = self.run_comparison()
        self.assertTrue(reports["before_same_history"]["implementation_path"].startswith(str(self.root)))
        groups = {row["league_id"]: row for row in result["leagues"]}
        self.assertEqual(set(groups), {"l_4WFCIZ", "l_2Mh0jT"})
        self.assertEqual(groups["l_4WFCIZ"]["countries"], ["ENG"])
        self.assertEqual(groups["l_2Mh0jT"]["countries"], ["RUS"])
        self.assertEqual(groups["l_2Mh0jT"]["after"]["identity_ready"], 0)
        self.assertEqual(result["summary"]["after"]["elo_ready"], 1)
        self.assertEqual(sum(row["total"] for row in result["leagues"]), 2)
        for name in reports:
            self.assertEqual(sum(result["summary"][name]["reasons"].values()), 2)

    def test_both_versions_receive_same_unique_as_of_available_history(self):
        self.history = self.history[:5]
        self.history.append(dict(self.history[0], home_goals=99))
        self.history.append(dict(self.history[1], fixture_id="future-publication",
                                 published_at_utc="2026-11-07T08:00:00Z"))
        self.history.append(dict(self.history[2], fixture_id="unfinished",
                                 completed_at_utc="2026-11-07T08:00:00Z",
                                 published_at_utc="2026-11-07T09:00:00Z"))
        result, reports = self.run_comparison()
        self.assertEqual(result["eligible_history_rows"], 4)
        self.assertEqual(reports["before_same_history"]["history_received"], 4)
        self.assertEqual(result["summary"]["before_same_history"]["elo_ready"], 0)
        self.assertEqual(result["summary"]["after"]["elo_ready"], 0)

    def test_original_ingestion_scope_reported_separately_and_inputs_unchanged(self):
        original = copy.deepcopy((self.queue, self.history))
        result, reports = self.run_comparison(before_history=[])
        self.assertEqual(result["summary"]["before_same_history"]["identity_ready"], 1)
        self.assertEqual(result["summary"]["before_original_history"]["identity_ready"], 0)
        self.assertEqual(reports["before_original_history"]["history_received"], 0)
        self.assertEqual((self.queue, self.history), original)

    def test_started_fixture_has_same_entry_gate_but_original_audit_is_preserved(self):
        self.queue["fixtures"][0]["kickoff_utc"] = self.cutoff
        result, reports = self.run_comparison()
        self.assertTrue(reports["before_same_history"]["fixtures"][0]["elo_ready"])
        self.assertEqual(result["started_fixtures"], 1)
        for name in ("before_same_history", "after"):
            self.assertEqual(result["summary"][name]["elo_ready"], 0)
            self.assertEqual(result["summary"][name]["reasons"]["prediction_not_prematch"], 1)

    def test_event_sample_diagnostic_excludes_foreign_country_namesake(self):
        event = dict(league="Premier League", home="A", away="B", country_code="ENG",
                     completed_at_utc="2026-11-01T20:00:00Z",
                     published_at_utc="2026-11-02T08:00:00Z",
                     events={"corners": [3, 4], "cards": [1, 2], "fouls": [7, 8]})
        foreign = dict(event, country_code="RUS", home="C", away="D")
        result, _ = compare(self.queue, self.history, [event, foreign], baseline_root=self.root,
                            as_of_utc=self.cutoff)
        self.assertEqual(result["event_samples_available"]["Premier League"],
                         {"corners": 1, "cards": 1, "fouls": 1})

    def test_duplicate_fixture_and_missing_old_source_fail_closed(self):
        self.queue["fixtures"].append(copy.deepcopy(self.queue["fixtures"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_queue_fixture"):
            self.run_comparison()
        with self.assertRaisesRegex(ValueError, "baseline_coverage_module_missing"):
            baseline_audit({}, [], baseline_root=self.root / "missing", as_of_utc=self.cutoff)

    def test_cli_writes_audits_and_input_hashes(self):
        for name, value in (("queue", self.queue), ("history", self.history), ("events", [])):
            (self.root / (name + ".json")).write_text(json.dumps(value))
        output = self.root / "output" / "comparison.json"
        command = [sys.executable, "-B", "-m", "github_models.coverage_comparison",
                   "--queue", str(self.root / "queue.json"), "--history", str(self.root / "history.json"),
                   "--events", str(self.root / "events.json"), "--baseline-root", str(self.root),
                   "--as-of", self.cutoff, "--output", str(output)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(output.read_text())
        self.assertEqual(set(result["input_sha256"]), {"queue", "history", "events"})
        for name in result["audit_files"].values():
            self.assertTrue((output.parent / name).is_file())
        self.assertIn("not evidence", result["interpretation"]["dixon_coles_history_ready"])


if __name__ == "__main__":
    unittest.main()
