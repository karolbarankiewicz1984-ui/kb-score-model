"""CLI for additional prospective SHADOW probabilities; independent of A/B/C."""
import argparse
import json
from pathlib import Path
from github_models.shadow_markets import run


def main():
    p = argparse.ArgumentParser()
    for name in ("queue", "history", "as-of", "output"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    read = lambda file: json.loads(Path(file).read_text(encoding="utf-8"))
    result = run(read(args.queue), read(args.history), args.as_of)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False,
                                 indent=2) + "\n", encoding="utf-8")
    print("SHADOW_ROWS=" + str(len(result["candidates"])))
    print("SHADOW_BLOCKED_FIXTURES=" + str(len(result["blockers"])))
    print("SHADOW_UNSUPPORTED=" + ",".join(result["unsupported_markets"]))


if __name__ == "__main__":
    main()
