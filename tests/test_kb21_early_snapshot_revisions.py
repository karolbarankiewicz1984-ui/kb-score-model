"""Only TWO real before-whole-day snapshots can support a revision comparison."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from tests.test_kb21_pregame_vault import DAYS, DAY, queue, knvb, fpl, write_snapshots
from tools.kb21_pregame_vault import package
from tools.kb21_early_snapshot_revisions import compare, render


def pack(folder, label, knvb_data, fpl_data, at):
    source_dir = Path(folder, label + "_source")
    source_dir.mkdir()
    files = write_snapshots(source_dir, knvb_data, fpl_data)
    dest = Path(folder, label)
    package(DAYS, files, dest, datetime.fromisoformat(at.replace("Z", "+00:00")))
    return dest


class EarlyOfficialRevisionTests(unittest.TestCase):
    def test_two_pregame_snapshots_detect_removed_and_rescheduled_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            first = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            new_knvb = knvb("2026-10-18T06:00:00Z")
            new_knvb["by_day"][DAY] = []  # vanished before first start
            new_fpl = fpl("2026-10-18T06:00:00Z")
            new_fpl["by_day"][DAY][0]["kickoff_utc"] = "2026-10-18T15:00:00Z"
            second = pack(folder, "second", new_knvb, new_fpl,
                          "2026-10-18T06:05:00Z")
            result = compare(queue(), [second, first])
        rows = {(r["day"], r["league_id"]): r for r in result["rows"]}
        self.assertEqual(len(result["rows"]), 9)
        self.assertEqual(result["summary"]["with_two_eligible_captures"], 2)
        self.assertEqual(result["summary"]["with_organizer_changes"], 2)
        self.assertEqual(len(rows[(DAY, "ned.1")]["removed_pairs"]), 1)
        self.assertEqual(len(rows[(DAY, "eng.1")]["kickoff_changes"]), 1)
        self.assertEqual(rows[(DAY, "eng.1")]["kickoff_changes"][0]["old_kickoff_utc"],
                         "2026-10-18T14:00:00+00:00")
        self.assertFalse(result["safe_to_publish_play"])
        self.assertTrue(all(r["human_signed"] is False for r in result["rows"]))
        self.assertTrue(all(r["full_organizer_day_attested"] is False
                            for r in result["rows"]))
        self.assertIn("WYMAGA KONTROLI", render(result))

    def test_single_snapshot_is_not_evidence_of_stability(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            result = compare(queue(), [archive])
        rows = {(r["day"], r["league_id"]): r for r in result["rows"]}
        self.assertEqual(rows[(DAY, "ned.1")]["status"],
                         "SINGLE_EARLY_SNAPSHOT_NO_DRIFT_COMPARISON")
        self.assertEqual(result["summary"]["with_two_eligible_captures"], 0)
        self.assertEqual(result["summary"]["with_organizer_changes"], 0)

    def test_official_capture_after_first_game_is_rejected_even_for_later_match(self):
        with tempfile.TemporaryDirectory() as folder:
            late = pack(folder, "late",
                        knvb("2026-10-18T11:00:00Z"),
                        fpl("2026-10-18T11:00:00Z"),
                        "2026-10-18T11:05:00Z")
            result = compare(queue(), [late])
        self.assertEqual(result["summary"]["with_two_eligible_captures"], 0)
        self.assertEqual(result["rows"][0]["status"], "NO_EARLY_OFFICIAL_SNAPSHOT")
        self.assertEqual(result["rows"][1]["status"], "NO_EARLY_OFFICIAL_SNAPSHOT")

    def test_unknown_first_start_must_not_claim_early_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            first = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            changed = copy.deepcopy(queue())
            changed["fixtures"][1]["kickoff"] = None
            report = compare(changed, [first])
        self.assertEqual(report["summary"]["with_two_eligible_captures"], 0)
        self.assertEqual(report["rows"][0]["status"],
                         "NO_SAFE_EARLIEST_WHOLE_DAY_KICKOFF")

    def test_two_identical_captures_do_not_certify_whole_day(self):
        with tempfile.TemporaryDirectory() as folder:
            first = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            second = pack(folder, "second",
                          knvb("2026-10-18T06:00:00Z"),
                          fpl("2026-10-18T06:00:00Z"), "2026-10-18T06:05:00Z")
            result = compare(queue(), [first, second])
        row = next(r for r in result["rows"]
                   if r["day"] == DAY and r["league_id"] == "eng.1")
        self.assertEqual(row["status"], "NO_CHANGE_BETWEEN_OBSERVED_EARLY_SNAPSHOTS")
        self.assertFalse(row["full_organizer_day_attested"])

    def test_zero_candidates_is_not_verified_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            first = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            result = compare({"days": DAYS, "fixtures": []}, [first])
        self.assertEqual(result["summary"]["without_safe_earliest_kickoff"], 9)
        self.assertFalse(result["safe_to_publish_play"])

    def test_duplicate_source_pair_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = knvb()
            bad["by_day"][DAY].append(copy.deepcopy(bad["by_day"][DAY][0]))
            first = pack(folder, "first", bad, None, "2026-10-18T04:05:00Z")
            with self.assertRaisesRegex(ValueError, "Duplicate/ambiguous"):
                compare(queue(), [first])


    def test_dfl_added_pregame_fixture_is_review_only(self):
        from tests.test_kb21_pregame_vault import dfl
        with tempfile.TemporaryDirectory() as folder:
            first = pack(folder, "first", knvb(), fpl(), "2026-10-18T04:05:00Z")
            second = pack(folder, "second",
                          knvb("2026-10-18T06:00:00Z"),
                          fpl("2026-10-18T06:00:00Z"),
                          "2026-10-18T06:05:00Z")
            for label, when, item in (
                ("first", "2026-10-18T04:00:00Z", dfl()),
                ("second", "2026-10-18T06:00:00Z", dfl("2026-10-18T06:00:00Z"))):
                doc = json.loads(Path(folder, label, "manifest.json").read_text())
                from tools.kb21_pregame_vault import package
                source_file = Path(folder, label + "_source", "dfl-input.json")
                source_file.write_text(json.dumps(item))
                paths = {name: Path(folder, label + "_source", name + "-input.json")
                         for name in ("knvb", "fpl")}
                paths["dfl"] = source_file
                if label == "second":
                    item["by_day"][DAY].append({
                        "home": "Bayern Munich", "away": "Borussia Dortmund",
                        "kickoff_utc": "2026-10-18T13:00:00Z"})
                    source_file.write_text(json.dumps(item))
                package(DAYS, paths, Path(folder, label),
                        datetime.fromisoformat(
                            ("2026-10-18T04:05:00Z" if label == "first"
                             else "2026-10-18T06:05:00Z").replace("Z", "+00:00")))
            result = compare(queue(), [first, second])
        match = next(row for row in result["rows"]
                     if row["day"] == DAY and row["league_id"] == "ger.1")
        self.assertEqual(match["status"],
                         "OFFICIAL_PREMATCH_SNAPSHOT_CHANGED_NEEDS_REVIEW")
        self.assertEqual(len(match["added_pairs"]), 1)
        self.assertFalse(match["human_signed"])
        self.assertFalse(result["safe_to_publish_play"])

if __name__ == "__main__":
    unittest.main()
