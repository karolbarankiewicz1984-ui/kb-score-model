"""Research event-market forecasts from observed prematch historical samples."""
import math
from datetime import datetime
from github_models.team_mapping import resolve

THRESHOLDS = {"goals": (1.5, 2.5, 3.5), "corners": (7.5, 8.5, 9.5),
              "cards": (2.5, 3.5, 4.5), "fouls": (19.5, 22.5, 25.5)}
MIN_LEAGUE = 60
MIN_TEAM = 8

def poisson_over(mean, line):
    if not math.isfinite(mean) or mean <= 0:
        raise ValueError("invalid_rate")
    threshold = int(line)
    term = math.exp(-mean)
    cdf = term
    for k in range(1, threshold+1):
        term *= mean/k
        cdf += term
    return max(0.0, min(1.0, 1.0-cdf))

def run(queue, history, event_history, as_of_utc):
    now = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    out, blockers = [], []
    for fixture in queue["fixtures"]:
        kick = datetime.fromisoformat(fixture["kickoff_utc"].replace("Z", "+00:00"))
        if kick <= now:
            continue
        try:
            mapped = resolve(fixture, history)
        except (ValueError, KeyError, TypeError) as exc:
            for market in THRESHOLDS:
                blockers.append({"fixture_id":fixture["fixture_id"],"market":market,"reason":"team_mapping_unverified"})
            continue
        for market, lines in THRESHOLDS.items():
            pool = []
            if market == "goals":
                for r in history:
                    if "home_goals" not in r or "away_goals" not in r:
                        continue
                    values = [r["home_goals"],r["away_goals"]]
                    pool.append((r,values))
            else:
                for r in event_history:
                    if market in r.get("events", {}):
                        pool.append((r,r["events"][market]))
            valid = []
            for r, values in pool:
                try:
                    published = datetime.fromisoformat(r["published_at_utc"].replace("Z", "+00:00"))
                    completed = datetime.fromisoformat(r["completed_at_utc"].replace("Z", "+00:00"))
                    if r["league"] == mapped["league"] and published <= now and completed < now and completed < kick and len(values) == 2 and min(values) >= 0:
                        valid.append((r,values))
                except (KeyError, ValueError, TypeError):
                    continue
            home_rows = [v for r,v in valid if r["home"] == mapped["home"] or r["away"] == mapped["home"]]
            away_rows = [v for r,v in valid if r["home"] == mapped["away"] or r["away"] == mapped["away"]]
            if len(valid) < MIN_LEAGUE or min(len(home_rows),len(away_rows)) < MIN_TEAM:
                blockers.append({"fixture_id":fixture["fixture_id"],"market":market,
                    "reason":"insufficient_verified_history","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows)})
                continue
            league_mean = sum(sum(v) for _,v in valid)/len(valid)
            hmean = sum(sum(v) for v in home_rows)/len(home_rows)
            amean = sum(sum(v) for v in away_rows)/len(away_rows)
            # Shrink sparse team totals to observed league baseline.
            hrate = (len(home_rows)*hmean+20*league_mean)/(len(home_rows)+20)
            arate = (len(away_rows)*amean+20*league_mean)/(len(away_rows)+20)
            rate = (hrate+arate)/2
            for line in lines:
                p = poisson_over(rate,line)
                out.append({"fixture_id":fixture["fixture_id"],"model_id":"observed-events-poisson-v1",
                    "market":market,"selection":"over","line":line,"probability":round(p,6),
                    "frozen_at_utc":as_of_utc,"probability_status":"uncalibrated_research",
                    "source":"football-data.co.uk","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows),
                    "method":"Poisson with shrinkage of observed team match totals"})
                out.append({"fixture_id":fixture["fixture_id"],"model_id":"observed-events-poisson-v1",
                    "market":market,"selection":"under","line":line,"probability":round(1-p,6),
                    "frozen_at_utc":as_of_utc,"probability_status":"uncalibrated_research",
                    "source":"football-data.co.uk","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows),
                    "method":"Poisson with shrinkage of observed team match totals"})
    return {"schema":"github-models-event-markets-v1","generated_at_utc":as_of_utc,
            "markets":out,"blockers":blockers,"production_multimodel_unchanged":True}
