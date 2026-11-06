"""Conservative research settlement; no guessed match identities."""
import json
import math
from datetime import datetime, timedelta
from github_models.team_mapping import resolve

def settle(predictions, queue, history, as_of_utc):
    now = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    fixtures = {x["fixture_id"]: x for x in queue["fixtures"]}
    out = []
    for p in predictions["predictions"]:
        f = fixtures[p["fixture_id"]]
        kick = datetime.fromisoformat(f["kickoff_utc"].replace("Z", "+00:00"))
        frozen = datetime.fromisoformat(p["frozen_at_utc"].replace("Z", "+00:00"))
        if frozen >= kick:
            raise ValueError("not_prematch")
        row = {"fixture_id": p["fixture_id"], "model_id": p["model_id"], "status": "pending"}
        if kick < now:
            try:
                mapped = resolve(f, history)
                matches = [h for h in history if h["league"] == mapped["league"]
                    and h["home"] == mapped["home"] and h["away"] == mapped["away"]
                    and abs(((datetime.fromisoformat(h["completed_at_utc"].replace("Z", "+00:00")) - timedelta(days=2)).date() - kick.date()).days) <= 1
                    and datetime.fromisoformat(h["published_at_utc"].replace("Z", "+00:00")) <= now]
                if len(matches) == 1:
                    h = matches[0]
                    actual = 0 if h["home_goals"] > h["away_goals"] else 1 if h["home_goals"] == h["away_goals"] else 2
                    prob = [p["p_home"], p["p_draw"], p["p_away"]]
                    if abs(sum(prob) - 1) > 0.001:
                        raise ValueError("invalid_probabilities")
                    row.update(status="settled", actual=("1", "X", "2")[actual],
                        source_fixture_id=h["fixture_id"],
                        brier=sum((v - (i == actual))**2 for i, v in enumerate(prob)),
                        log_loss=-math.log(max(prob[actual], 1e-15)))
                elif len(matches) > 1:
                    row["status"] = "ambiguous"
            except (ValueError, KeyError, TypeError):
                pass
        out.append(row)
    return {"schema": "github-models-settlement-v1", "as_of_utc": as_of_utc, "settlements": out}
