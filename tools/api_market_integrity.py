"""Reject pipeline writes outside API-owned data/report directories before push."""
from pathlib import Path
import subprocess

ALLOWED = (
    "data/api_football/market_work/", "data/api_football/market_scan/",
    "data/api_football/market_snapshots/", "data/api_football/predictions/",
    "data/api_football/national_dynamic/", "data/api_football/international_5m/national/",
    "data/api_football/calibration/", "data/api_football/closing_snapshots/",
    "reports/api_market_scan/",
)


def assert_api_paths(paths):
    for path in paths:
        if not path.startswith(ALLOWED) or ".." in Path(path).parts:
            raise RuntimeError(f"API pipeline attempted a write outside its data: {path}")
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(Path.cwd().resolve()):
            raise RuntimeError(f"API path escapes repository: {path}")


def main():
    changed = set()
    for args in (["git", "diff", "--name-only", "HEAD", "-z"],
                 ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(x for x in subprocess.check_output(args).decode().split("\0") if x)
    assert_api_paths(changed)
    print(f"API isolation check passed: {len(changed)} data/report paths; no CORE writes")


if __name__ == "__main__":
    main()
