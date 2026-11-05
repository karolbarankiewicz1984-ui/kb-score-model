"""Read-only settlement of independently frozen GitHub Models forecasts."""
from collections import defaultdict
from math import log

def settle(predictions, verified_outcomes):
    """Use exact fixture ID and verified final goals; never rewrite forecasts."""
    outcomes = {}
    for row in verified_outcomes:
        try:
            if row["status"] != "FINISHED" or not row["published_at_utc"]:
                continue
            goals = row["home_goals"], row["away_goals"]
            if any(type(g) is not int or g < 0 for g in goals):
                continue
            outcomes[row["fixture_id"]] = goals
        except (KeyError, TypeError):
            continue
    by_model = defaultdict(list)
    for pred in predictions:
        if pred["fixture_id"] not in outcomes:
            continue
        hg, ag = outcomes[pred["fixture_id"]]
        outcome = 0 if hg > ag else (1 if hg == ag else 2)
        probs = [float(pred[k]) for k in ("p_home", "p_draw", "p_away")]
        if any(p < 0 or p > 1 for p in probs) or abs(sum(probs) - 1) > 1e-6:
            continue
        brier = sum((p - int(i == outcome)) ** 2 for i, p in enumerate(probs)) / 3
        loss = -log(max(probs[outcome], 1e-15))
        hit = int(max(range(3), key=lambda i: probs[i]) == outcome)
        by_model[pred["model_id"]].append((brier, loss, hit))
    return {model: dict(n=len(values),
                        brier=sum(v[0] for v in values) / len(values),
                        log_loss=sum(v[1] for v in values) / len(values),
                        hit_rate=sum(v[2] for v in values) / len(values))
            for model, values in sorted(by_model.items())}
