"""Standalone Elo 1X2 research engine for GitHub Models.

Only verified, published historical final scores may enter ratings.
Never imports or modifies MULTIMODEL production predictions.
"""
from datetime import datetime, timezone
from math import exp, log

def utc(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timezone_required")
    return stamp.astimezone(timezone.utc)

def train_elo(history, *, frozen_at_utc, k=20.0, home_advantage=65.0):
    cutoff = utc(frozen_at_utc)
    eligible = []
    for match in history:
        try:
            finished, published = utc(match["completed_at_utc"]), utc(match["published_at_utc"])
            home, away = match["home"], match["away"]
            hg, ag = match["home_goals"], match["away_goals"]
            if not all(isinstance(v, str) and v.strip() for v in (home, away, match["league"])):
                continue
            if home == away or any(type(v) is not int or v < 0 for v in (hg, ag)):
                continue
            if finished >= cutoff or published > cutoff or published < finished:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        eligible.append((finished, published, str(match["fixture_id"]), match))
    eligible.sort(key=lambda v: (v[0], v[1], v[2]))
    ratings = {}
    counts = {}
    for _, _, _, match in eligible:
        league = match["league"]
        h, a = (league, match["home"]), (league, match["away"])
        rh, ra = ratings.get(h, 1500.0), ratings.get(a, 1500.0)
        expected = 1 / (1 + 10 ** ((ra - rh - home_advantage) / 400))
        score = 1.0 if match["home_goals"] > match["away_goals"] else (
            0.5 if match["home_goals"] == match["away_goals"] else 0.0)
        ratings[h] = rh + k * (score - expected)
        ratings[a] = ra - k * (score - expected)
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    return ratings, counts

def predict_elo(history, fixture, *, frozen_at_utc, model_version="elo-v1",
                min_team_matches=5, draw_base=0.26):
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
    decisive_home = 1 / (1 + 10 ** (-advantage / 400))
    draw = draw_base * exp(-abs(advantage) / 500)
    home = (1 - draw) * decisive_home
    away = (1 - draw) * (1 - decisive_home)
    return dict(fixture_id=fixture["fixture_id"], league=fixture["league"],
                kickoff_utc=fixture["kickoff_utc"], frozen_at_utc=frozen_at_utc,
                model_id="github-elo", model_version=model_version,
                p_home=home, p_draw=draw, p_away=away,
                probability_status="uncalibrated_research",
                training_matches=sum(counts.values()) // 2)
