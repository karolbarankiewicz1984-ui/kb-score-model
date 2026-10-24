"""Offline checks for safe closing-snapshot commit retry behavior."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from tools.api_market_closing_publish import TARGET, publish


def response(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class PublishSnapshotTests(unittest.TestCase):
    def test_no_change_does_not_commit_or_push(self):
        commands = []
        def fake_git(*args, check=True):
            commands.append(args)
            return response()
        with patch("tools.api_market_closing_publish.git", side_effect=fake_git):
            self.assertEqual(publish(sleep=lambda _: None), "NO_CHANGE")
        self.assertEqual(commands, [("status", "--porcelain", "--", TARGET)])

    def test_push_race_retries_after_new_fetch_and_rebase_without_force(self):
        calls, slept = [], []
        def fake_git(*args, check=True):
            calls.append((args, check))
            if args[0] == "status":
                return response(stdout="?? data/api_football/closing_snapshots/2026-10-24/x.json\n")
            if args[0] == "push":
                return response(returncode=1, stderr="rejected: fetch first") if (
                    sum(x[0][0] == "push" for x in calls) == 1
                ) else response()
            return response()
        with patch("tools.api_market_closing_publish.git", side_effect=fake_git):
            self.assertEqual(publish(sleep=slept.append, attempts=3), "PUBLISHED")
        cmds = [x[0] for x in calls]
        self.assertEqual([x[0] for x in cmds].count("push"), 2)
        self.assertEqual([x[0] for x in cmds].count("fetch"), 2)
        self.assertEqual([x[0] for x in cmds].count("commit"), 1)
        self.assertEqual([x[0] for x in cmds].count("-c"), 2)
        self.assertEqual(slept, [2])
        self.assertFalse(any("--force" in str(x) or "force-with-lease" in str(x)
                             for x in cmds))
        self.assertTrue(all(x == ("push", "origin", "HEAD:refs/heads/main")
                            for x in cmds if x[0] == "push"))

    def test_failed_all_pushes_does_not_claim_published(self):
        counts = {"push": 0}
        def fake_git(*args, check=True):
            if args[0] == "status":
                return response(stdout=" M data/api_football/closing_snapshots/x.json")
            if args[0] == "push":
                counts["push"] += 1
                return response(returncode=1, stderr="remote branch moved")
            return response()
        with patch("tools.api_market_closing_publish.git", side_effect=fake_git):
            with self.assertRaisesRegex(RuntimeError, "cannot publish snapshot"):
                publish(attempts=3, sleep=lambda _: None)
        self.assertEqual(counts["push"], 3)

    def test_true_rebase_conflict_stops_before_push(self):
        counts = {"push": 0}
        def fake_git(*args, check=True):
            if args[0] == "status":
                return response(stdout="?? data/api_football/closing_snapshots/new.json")
            if args[0] == "-c":
                raise RuntimeError("Rebase conflict: snapshot path touched")
            if args[0] == "push":
                counts["push"] += 1
            return response()
        with patch("tools.api_market_closing_publish.git", side_effect=fake_git):
            with self.assertRaisesRegex(RuntimeError, "Rebase conflict"):
                publish(sleep=lambda _: None)
        self.assertEqual(counts["push"], 0)

    def test_invalid_attempt_count_is_rejected(self):
        with self.assertRaises(ValueError):
            publish(attempts=0)


if __name__ == "__main__":
    unittest.main()
