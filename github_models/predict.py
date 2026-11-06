"""Generate independent GitHub Models predictions or explicit data blockers."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from github_models.elo_engine import predict_elo, eligible_history, utc
from github_models.dixon_coles_engine import predict_dixon_coles
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize
from github_models.settlement import fixture_index, probability_vector

def run(queue, history, *, as_of_utc):
    cutoff = utc(as_of_utc)
    # Names introduced only by future/unobserved results are not valid evidence.
    eligible = eligible_history(history, frozen_at_utc=as_of_utc)
    fixture_index(queue)
    results, blockers = [], []
    # Fitted state belongs only to this invocation and this observed history.
    # Different fixtures of one league can share a fit, never a prediction.
    fitted_cache = {}
    for fixture in queue["fixtures"]:
        try:
            if utc(fixture["kickoff_utc"]) <= cutoff:
                continue
            mapped = resolve(canonicalize(fixture), eligible)
            mapping_error = None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            mapping_error = str(exc)
        for model in ("elo", "dixon-coles", "xgboost"):
            if model == "xgboost":
                blockers.append(dict(fixture_id=fixture["fixture_id"], model=model,
                                     reason="model_not_trained_or_adapter_not_ready"))
                continue
            try:
                if mapping_error is not None:
                    raise ValueError(mapping_error)
                if model == "elo":
                    forecast = predict_elo(eligible, mapped, frozen_at_utc=as_of_utc)
                else:
                    forecast = predict_dixon_coles(eligible, mapped, frozen_at_utc=as_of_utc,
                                                  fitted_cache=fitted_cache)
                probability_vector(forecast)
                forecast = dict(forecast, resolved_identity={k: mapped[k]
                    for k in ("league", "country_code", "league_id", "home", "away",
                              "home_id", "away_id", "home_team_id", "away_team_id",
                              "source_provider") if k in mapped})
                results.append(forecast)
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                blockers.append(dict(fixture_id=fixture["fixture_id"], model=model,
                                     reason=str(exc)))
    return dict(schema="github-models-independent-predictions-v1",
                generated_at_utc=as_of_utc, production_multimodel_unchanged=True,
                predictions=results, blockers=blockers,
                blocker_summary=dict(Counter(x['model'] + ': ' + x['reason'] for x in blockers)))

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
