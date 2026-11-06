"""Conservative post-match settlement for independently frozen event totals."""
import math
from github_models.elo_engine import utc
from github_models.settlement import fixture_index, matching_outcomes, source_match_date


def settle_markets(markets, queue, history, event_history, as_of_utc):
    now = utc(as_of_utc)
    fixtures = fixture_index(queue)
    results = []
    for p in markets.get("markets", []):
        fixture = fixtures[str(p["fixture_id"])]
        kickoff, frozen = utc(fixture["kickoff_utc"]), utc(p["frozen_at_utc"])
        if frozen >= kickoff:
            raise ValueError("not_prematch")
        if frozen > now:
            raise ValueError("forecast_not_yet_frozen")
        probability = p["probability"]
        if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("invalid_probability")
        line = p["line"]
        if (p["market"] not in ("goals", "corners", "cards", "fouls")
                or p["selection"] not in ("over", "under")
                or type(line) not in (int, float) or not math.isfinite(line)
                or line < 0 or line % 1 != .5):
            raise ValueError("unsupported_market_identity")
        row = {"fixture_id": p["fixture_id"], "market": p["market"], "line": line,
               "selection": p["selection"], "status": "pending"}
        if kickoff >= now:
            results.append(row)
            continue
        pool = history if p["market"] == "goals" else event_history
        try:
            candidates = matching_outcomes(fixture, pool, as_of_utc=as_of_utc,
                                            resolved_identity=p.get("resolved_identity"))
            if len(candidates) == 1:
                outcome = candidates[0]
                values = ([outcome["home_goals"], outcome["away_goals"]] if p["market"] == "goals"
                          else outcome["events"][p["market"]])
                if len(values) != 2 or any(type(v) is not int or v < 0 for v in values):
                    raise ValueError("invalid_final_statistics")
                value = sum(values)
                hit = value > line if p["selection"] == "over" else value < line
                row.update(status="settled", actual_total=value, hit=bool(hit),
                    source_fixture_id=outcome.get("fixture_id"), source_match_date=source_match_date(outcome).isoformat(),
                    brier=(probability-float(hit))**2,
                    log_loss=-math.log(max(probability if hit else 1-probability, 1e-15)))
            elif len(candidates) > 1:
                row.update(status="ambiguous", reason="multiple_verified_outcomes")
            else:
                row["reason"] = "no_exact_verified_outcome"
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            row.update(status="unmapped", reason=str(exc))
        results.append(row)
    return {"schema": "github-models-event-settlement-v1", "as_of_utc": as_of_utc, "settlements": results}
