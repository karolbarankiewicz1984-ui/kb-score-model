"""Publish API Market closing snapshots with bounded non-force Git race recovery.

A closing run may compete with other repository writers between rebase and
push. GitHub Actions concurrency groups cover only jobs sharing that group.
Never force-push or drop a closing snapshot to silence notifications.
"""
from __future__ import annotations

import argparse
import subprocess
import time

TARGET = "data/api_football/closing_snapshots"
MAX_ATTEMPTS = 6


def git(*args, check=True):
    cp = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "unknown git error").strip()
        raise RuntimeError(f"Git {args[0]} failed: {detail[-1800:]}")
    return cp


def publish(sleep=time.sleep, attempts=MAX_ATTEMPTS):
    """Commit only closing-snapshot data and retry fetch/rebase/push races.

    This runs only in the GitHub Actions checkout. No merging, force-push or
    migration of other workflows is attempted. Rebase conflicts fail closed.
    """
    if not isinstance(attempts, int) or not 1 <= attempts <= 10:
        raise ValueError("Invalid bounded retry count")
    changed = git("status", "--porcelain", "--", TARGET).stdout.strip()
    if not changed:
        print("API closing: no new snapshot files to publish.")
        return "NO_CHANGE"

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", TARGET)
    git("commit", "-m", "data: closing market snapshot")

    for number in range(1, attempts + 1):
        git("fetch", "origin", "main")
        # If a true path conflict occurs, abort instead of overwriting anything.
        git("-c", "rebase.autoStash=false", "rebase", "origin/main")
        pushed = git("push", "origin", "HEAD:refs/heads/main", check=False)
        if pushed.returncode == 0:
            print(f"API closing: published snapshot on attempt {number}/{attempts}.")
            return "PUBLISHED"
        if number == attempts:
            detail = (pushed.stderr or pushed.stdout or "push rejected").strip()
            raise RuntimeError("API closing: cannot publish snapshot after "
                               f"{attempts} attempts; local snapshot not claimed published: "
                               + detail[-1400:])
        print(f"::warning::Closing snapshot push collision; safe retry "
              f"{number}/{attempts} without force.")
        sleep(min(number * 2, 12))
    raise AssertionError("unreachable")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    args = p.parse_args()
    publish(attempts=args.attempts)


if __name__ == "__main__":
    main()
