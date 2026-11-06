"""Read-only settlement of independently frozen GitHub Models forecasts."""
from collections import defaultdict
from math import log
from datetime import datetime, timezone
from github_models.settlement import probability_vector
from github_models.elo_engine import utc

def settle(predictions, verified_outcomes, *, as_of_utc=None):
    """Use exact fixture ID and verified final goals; never rewrite forecasts."""
    cutoff = utc(as_of_utc) if as_of_utc is not None else datetime.now(timezone.utc)
    outcomes = defaultdict(list)
    for row in verified_outcomes:
        try:
            if row["status"] != "FINISHED" or not row["published_at_utc"]:
                continue
            published = utc(row["published_at_utc"])
            if published > cutoff:
                continue
            if row.get("completed_at_utc") and utc(row["completed_at_utc"]) > published:
                continue
            goals = row["home_goals"], row["away_goals"]
            if any(type(g) is not int or g < 0 for g in goals):
                continue
            outcomes[str(row["fixture_id"])].append((goals, row))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    by_model = defaultdict(list)
    for pred in predictions:
        matches = outcomes.get(str(pred["fixture_id"]), [])
        if len(matches) != 1:
            continue
        (hg, ag), source = matches[0]
        outcome = 0 if hg > ag else (1 if hg == ag else 2)
        try:
            probs = probability_vector(pred)
            frozen, kickoff = utc(pred["frozen_at_utc"]), utc(pred["kickoff_utc"])
            if not frozen < kickoff < cutoff:
                continue
            if source.get("completed_at_utc") and utc(source["completed_at_utc"]) <= kickoff:
                continue
            if (pred.get("source_provider") and source.get("source_provider")
                    and pred["source_provider"] != source["source_provider"]):
                continue
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        brier = sum((p - int(i == outcome)) ** 2 for i, p in enumerate(probs))
        loss = -log(max(probs[outcome], 1e-15))
        hit = int(max(range(3), key=lambda i: probs[i]) == outcome)
        by_model[pred["model_id"]].append((brier, loss, hit))
    return {model: dict(n=len(values),
                        brier=sum(v[0] for v in values) / len(values),
                        log_loss=sum(v[1] for v in values) / len(values),
                        hit_rate=sum(v[2] for v in values) / len(values))
            for model, values in sorted(by_model.items())}
