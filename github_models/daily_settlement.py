"""Daily settlement of archived forecasts against verified results."""
import argparse
import json
from pathlib import Path
from github_models.settlement import settle

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive-dir", required=True)
    p.add_argument("--history", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    root = Path(a.archive_dir)
    history = json.loads(Path(a.history).read_text())
    reports = []
    for forecast in sorted(root.glob("frozen/*/*.json")):
        relative = forecast.relative_to(root)
        queue_file = root / "queues" / relative.parts[1] / relative.name
        if not queue_file.exists():
            continue
        predictions = json.loads(forecast.read_text())
        queue = json.loads(queue_file.read_text())
        result = settle(predictions, queue, history, a.as_of)
        reports.append({"archive": str(relative), "result": result})
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"schema": "github-models-daily-settlement-v1",
        "as_of_utc": a.as_of, "archives_processed": len(reports),
        "reports": reports}, ensure_ascii=False, indent=2) + "\n")
    print("Settlement archives processed:", len(reports))
    print("Settled:", sum(sum(x["status"] == "settled" for x in r["result"]["settlements"]) for r in reports))

if __name__ == "__main__":
    main()
