"""Conservative post-match settlement for independently frozen event totals."""
import math
from datetime import datetime, timedelta
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize

def settle_markets(markets, queue, history, event_history, as_of_utc):
    now = datetime.fromisoformat(as_of_utc.replace("Z","+00:00"))
    fixtures = {str(f["fixture_id"]):f for f in queue["fixtures"]}
    results = []
    for p in markets.get("markets",[]):
        fixture = fixtures[str(p["fixture_id"])]
        kickoff = datetime.fromisoformat(fixture["kickoff_utc"].replace("Z","+00:00"))
        frozen = datetime.fromisoformat(p["frozen_at_utc"].replace("Z","+00:00"))
        if frozen >= kickoff:
            raise ValueError("not_prematch")
        probability = float(p["probability"])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("invalid_probability")
        row = {"fixture_id":p["fixture_id"],"market":p["market"],"line":p["line"],
            "selection":p["selection"],"status":"pending"}
        if kickoff >= now:
            results.append(row)
            continue
        try:
            mapped = resolve(canonicalize(fixture),history)
        except (ValueError,KeyError,TypeError):
            row["status"] = "unmapped"
            results.append(row)
            continue
        candidates = []
        pool = history if p["market"] == "goals" else event_history
        for h in pool:
            try:
                date = datetime.fromisoformat(h["completed_at_utc"].replace("Z","+00:00"))-timedelta(days=2)
                published = datetime.fromisoformat(h["published_at_utc"].replace("Z","+00:00"))
                if h["league"] != mapped["league"] or h["home"] != mapped["home"] or h["away"] != mapped["away"]:
                    continue
                if abs((date.date()-kickoff.date()).days) > 1 or published > now:
                    continue
                if p["market"] == "goals":
                    value = int(h["home_goals"])+int(h["away_goals"])
                else:
                    value = sum(h["events"][p["market"]])
                candidates.append(value)
            except (KeyError,TypeError,ValueError):
                continue
        if len(candidates) == 1:
            value = candidates[0]
            hit = value > p["line"] if p["selection"] == "over" else value < p["line"]
            row.update(status="settled",actual_total=value,hit=bool(hit),
                brier=(probability-float(hit))**2,
                log_loss=-math.log(max(probability if hit else 1-probability,1e-15)))
        elif len(candidates)>1:
            row["status"]="ambiguous"
        results.append(row)
    return {"schema":"github-models-event-settlement-v1","as_of_utc":as_of_utc,"settlements":results}
