"""Standalone Elo 1X2 research engine for GitHub Models.

Only verified, published historical final scores may enter ratings.
Never imports or modifies MULTIMODEL production predictions.
"""
from datetime import datetime, timezone
from math import exp, isfinite, log

def utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timezone_required")
    return stamp.astimezone(timezone.utc)

def eligible_history(history, *, frozen_at_utc, league=None):
    """Return unique verified final scores available at the supplied cutoff.

    A repeated source record contributes once. Conflicting records for one
    fixture contribute nothing, so duplication cannot satisfy sample gates.
    """
    cutoff = utc(frozen_at_utc)
    grouped = {}
    for match in history:
        try:
            finished, published = utc(match["completed_at_utc"]), utc(match["published_at_utc"])
            home, away = match["home"], match["away"]
            hg, ag = match["home_goals"], match["away_goals"]
            if not all(isinstance(v, str) and v.strip() for v in
                       (home, away, match["league"], match["fixture_id"])):
                continue
            if league is not None and match["league"] != league:
                continue
            if home == away or any(type(v) is not int or v < 0 for v in (hg, ag)):
                continue
            if finished >= cutoff or published > cutoff or published < finished:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        key = (match["league"], match["fixture_id"])
        facts = (finished, home, away, hg, ag)
        grouped.setdefault(key, []).append((facts, published, match))
    eligible = []
    for rows in grouped.values():
        if len({row[0] for row in rows}) != 1:
            continue
        _, published, match = min(rows, key=lambda row: row[1])
        eligible.append((utc(match["completed_at_utc"]), published, match["fixture_id"], match))
    eligible.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in eligible]


def _decisive_home(advantage):
    """Stable base-ten logistic, including large rating differences."""
    z = log(10) * advantage / 400
    if z >= 0:
        return 1 / (1 + exp(-z))
    weight = exp(z)
    return weight / (1 + weight)


def train_elo(history, *, frozen_at_utc, k=20.0, home_advantage=65.0):
    if (isinstance(k, bool) or isinstance(home_advantage, bool)
            or not isinstance(k, (int, float)) or not isinstance(home_advantage, (int, float))
            or not isfinite(k) or k <= 0 or not isfinite(home_advantage)):
        raise ValueError("invalid_elo_parameters")
    eligible = eligible_history(history, frozen_at_utc=frozen_at_utc)
    ratings = {}
    counts = {}
    for match in eligible:
        league = match["league"]
        h, a = (league, match["home"]), (league, match["away"])
        rh, ra = ratings.get(h, 1500.0), ratings.get(a, 1500.0)
        expected = _decisive_home(rh + home_advantage - ra)
        score = 1.0 if match["home_goals"] > match["away_goals"] else (
            0.5 if match["home_goals"] == match["away_goals"] else 0.0)
        ratings[h] = rh + k * (score - expected)
        ratings[a] = ra - k * (score - expected)
        if not all(isfinite(ratings[team]) for team in (h, a)):
            raise ValueError("nonfinite_elo_rating")
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    return ratings, counts

def predict_elo(history, fixture, *, frozen_at_utc, model_version="elo-v1",
                min_team_matches=5, draw_base=0.26):
    if (isinstance(draw_base, bool) or not isinstance(draw_base, (int, float))
            or not isfinite(draw_base) or not 0 <= draw_base <= 1
            or type(min_team_matches) is not int or min_team_matches < 1):
        raise ValueError("invalid_elo_parameters")
    if (not all(isinstance(fixture.get(key), str) and fixture[key].strip()
                for key in ("fixture_id", "league", "home", "away"))
            or fixture["home"] == fixture["away"]):
        raise ValueError("invalid_fixture_identity")
    cutoff, kickoff = utc(frozen_at_utc), utc(fixture["kickoff_utc"])
    if cutoff >= kickoff:
        raise ValueError("prediction_not_prematch")
    ratings, counts = train_elo(history, frozen_at_utc=frozen_at_utc)
    h = (fixture["league"], fixture["home"])
    a = (fixture["league"], fixture["away"])
    if min(counts.get(h, 0), counts.get(a, 0)) < min_team_matches:
        raise ValueError("insufficient_verified_team_history")
    # A documented baseline heuristic, not calibrated probabilities.
    advantage = ratings[h] + 65.0 - ratings[a]
    decisive_home = _decisive_home(advantage)
    draw = draw_base * exp(-abs(advantage) / 500)
    home = (1 - draw) * decisive_home
    away = (1 - draw) * (1 - decisive_home)
    return dict(fixture_id=fixture["fixture_id"], league=fixture["league"],
                kickoff_utc=fixture["kickoff_utc"], frozen_at_utc=frozen_at_utc,
                model_id="github-elo", model_version=model_version,
                p_home=home, p_draw=draw, p_away=away,
                probability_status="uncalibrated_research",
                training_matches=sum(count for (league, _), count in counts.items()
                                     if league == fixture["league"]) // 2)
