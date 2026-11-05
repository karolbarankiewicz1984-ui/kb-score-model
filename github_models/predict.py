"""Generate independent GitHub Models predictions or explicit data blockers."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from github_models.elo_engine import predict_elo
from github_models.team_mapping import resolve

def run(queue, history, *, as_of_utc):
    results, blockers = [], []
    for fixture in queue["fixtures"]:
        if datetime.fromisoformat(fixture["kickoff_utc"].replace("Z", "+00:00")) <= datetime.fromisoformat(as_of_utc.replace("Z", "+00:00")):
            continue
        for model in ("elo", "dixon-coles", "xgboost"):
            if model != "elo":
                blockers.append(dict(fixture_id=fixture["fixture_id"], model=model,
                                     reason="model_not_trained_or_adapter_not_ready"))
                continue
            try:
                mapped = resolve(fixture, history)
                forecast = predict_elo(history, mapped, frozen_at_utc=as_of_utc)
                results.append(forecast)
            except (ValueError, KeyError, TypeError) as exc:
                blockers.append(dict(fixture_id=fixture["fixture_id"], model=model,
                                     reason=str(exc)))
    return dict(schema="github-models-independent-predictions-v1",
                generated_at_utc=as_of_utc, production_multimodel_unchanged=True,
                predictions=results, blockers=blockers)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--history", default="data/github_models/verified_results.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    history_path = Path(args.history)
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
    if not isinstance(history, list):
        raise ValueError("history_must_be_list")
    result = run(queue, history, as_of_utc=args.as_of)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GitHub Models: {len(result['predictions'])} real forecasts; {len(result['blockers'])} blockers")

if __name__ == "__main__":
    main()
