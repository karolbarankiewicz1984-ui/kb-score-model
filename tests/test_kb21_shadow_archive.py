"""Audit archives are additive and never touch historical KB21 registers."""
import base64
from copy import deepcopy
from unittest.mock import patch, MagicMock
import json
import unittest

from tools.kb21_shadow_archive import PREFIX, archive, prepare


def sample():
    return {
        "schema": "kb21-shadow-forward-settlement-v1",
        "date": "2026-10-18", "audited_at_utc": "2026-10-19T07:00:00Z",
        "source": "API-Football result fixtures (same provider IDs)",
        "model": "kb21-api-last10-goals-shadow-v1",
        "publication": "RESEARCH_ONLY_NOT_PLAY",
        "old_kb21_n_effect": 0, "register_writes": False,
        "safe_to_publish_play": False,
        "unique_pregame_predictions": 1, "distinct_settled_matches": 1,
        "results": [{
            "fixture_id": 111, "event": "A – B",
            "kickoff_utc": "2026-10-18T12:00:00Z",
            "freeze_utc": "2026-10-18T08:00:00Z",
            "snapshot_sha256": "a"*64,
            "status": "SETTLED_FT",
            "probabilities": {"home": .5, "draw": .2,
                              "away": .3, "over_2_5": .6},
        }],
    }


class ShadowArchiveTests(unittest.TestCase):
    def test_genuine_snapshot_path_only_isolated_namespace(self):
        path, raw = prepare(sample(), 12345, 1)
        self.assertEqual(path, f"{PREFIX}/2026-10-18/12345-attempt1.json")
        self.assertEqual(json.loads(raw)["results"][0]["fixture_id"], 111)
        self.assertNotIn("data/kb21_calendar_reviews", path)
        self.assertNotIn("rejestr", path.lower())

    def test_no_forecasts_means_no_permanent_file(self):
        report = sample()
        report["results"] = []
        report["unique_pregame_predictions"] = 0
        self.assertIsNone(prepare(report, 12345, 1))

    def test_explicitly_rejects_original_kbscore_n_mutations(self):
        report = sample()
        report["old_kb21_n_effect"] = 1
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            prepare(report, 12345, 1)

    def test_rejects_late_source_forecast(self):
        report = sample()
        report["results"][0]["freeze_utc"] = "2026-10-18T13:00:00Z"
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            prepare(report, 12345, 1)

    def test_rejects_duplicate_ids(self):
        report = sample()
        report["results"].append(deepcopy(report["results"][0]))
        report["unique_pregame_predictions"] = 2
        with self.assertRaisesRegex(ValueError, "duplicated"):
            prepare(report, 12345, 1)

    def test_invalid_repo_and_attempt_fail(self):
        with self.assertRaisesRegex(ValueError, "owner/name"):
            archive(sample(), "invalid", 12, 1)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            prepare(sample(), 12, False)

    def test_identical_run_retry_skips_write(self):
        report = sample()
        _, content = prepare(report, 111, 2)
        existing = json.dumps({"content":base64.b64encode(content).decode()})
        with patch.dict("os.environ", {"GH_TOKEN":"dummy"}):
            with patch("tools.kb21_shadow_archive.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0,stdout=existing,stderr="")
                result = archive(report, "owner/repo", 111, 2)
                self.assertEqual(result["status"], "ALREADY_ARCHIVED_IDENTICAL")
                self.assertEqual(run.call_count, 1)

    def test_conflict_never_overwrites_original_archived_bytes(self):
        existing = json.dumps({"content":base64.b64encode(b'old-file').decode()})
        with patch.dict("os.environ", {"GH_TOKEN":"dummy"}):
            with patch("tools.kb21_shadow_archive.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0,stdout=existing,stderr="")
                with self.assertRaisesRegex(ValueError, "Conflicting"):
                    archive(sample(), "owner/repo", 111, 1)
                self.assertEqual(run.call_count, 1)

    def test_new_archive_uses_create_only_gitHub_api(self):
        with patch.dict("os.environ", {"GH_TOKEN":"dummy"}):
            with patch("tools.kb21_shadow_archive.subprocess.run") as run:
                run.side_effect = [
                    MagicMock(returncode=1,stdout="",stderr="HTTP 404"),
                    MagicMock(returncode=0,stdout="{}",stderr=""),
                ]
                result = archive(sample(), "owner/repo", 111, 1)
                self.assertEqual(result["status"], "ARCHIVED_NEW_APPEND_ONLY")
                self.assertEqual(run.call_count, 2)
                args = run.call_args_list[1].args[0]
                self.assertIn("PUT", args)
                self.assertIn("data/kb21_shadow_audits", " ".join(args))

if __name__ == "__main__":
    unittest.main()
