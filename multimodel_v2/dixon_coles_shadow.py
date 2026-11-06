"""Optional Dixon-Coles shadow adapter; never called by production.

Requires separately installed dixon-coles package and verified historical outcomes.
"""
from datetime import datetime, timezone
from math import fsum, isfinite
from .external_model_shadow import validate_shadow_prediction

def _time(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone_required")
    return t.astimezone(timezone.utc)

def normalize_dixon_probabilities(result):
    """Upstream rounds 1X2 to four decimals; preserve strict probability sum."""
    try:
        values = [result[k] for k in ("home_win", "draw", "away_win")]
        if any(isinstance(value, bool) for value in values):
            raise ValueError("boolean_probability")
        raw = [float(value) for value in values]
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid_dixon_coles_probabilities") from exc
    if not all(isfinite(p) and 0 <= p <= 1 for p in raw):
        raise ValueError("invalid_dixon_coles_probabilities")
    total = fsum(raw)
    # Three probabilities rounded to four decimals can differ from one by
    # at most 0.00015. Do not turn arbitrary weights into invented forecasts.
    if total <= 0 or abs(total - 1) > 0.000150000001:
        raise ValueError("invalid_dixon_coles_probabilities")
    return [p / total for p in raw]

def forecast_dixon_coles(history, fixture, *, frozen_at_utc, model_version,
                         min_matches=30, xg_weight=1.0):
    """Fit solely on fully completed, published pre-freeze matches of ONE league.

    xg_weight=1 uses goals only; never infer historical xG availability.
    """
    freeze = _time(frozen_at_utc)
    kickoff = _time(fixture["kickoff_utc"])
    if not freeze < kickoff:
        raise ValueError("freeze_must_precede_kickoff")
    if not 0 <= xg_weight <= 1:
        raise ValueError("invalid_xg_weight")
    league = fixture["league"]
    accepted = []
    for h in history:
        if h["league"] != league:
            continue
        end = _time(h["completed_at_utc"])
        published = _time(h["published_at_utc"])
        if end >= freeze or published > freeze or published < end:
            continue
        if h["home"] == h["away"]:
            raise ValueError("invalid_training_match")
        goals = (h["home_goals"], h["away_goals"])
        if any(not isinstance(g, int) or isinstance(g, bool) or g < 0 for g in goals):
            raise ValueError("invalid_training_goals")
        accepted.append(h)
    if len(accepted) < min_matches:
        raise ValueError("insufficient_verified_training_matches")
    if xg_weight != 1.0:
        for h in accepted:
            if not all(k in h for k in ("home_xg", "away_xg", "xg_published_at_utc")):
                raise ValueError("xg_provenance_missing")
            if _time(h["xg_published_at_utc"]) > freeze:
                raise ValueError("xg_not_published_before_freeze")
            if any(not isfinite(float(h[k])) or float(h[k]) < 0 for k in ("home_xg", "away_xg")):
                raise ValueError("invalid_xg")
    try:
        import numpy as np
        import dixon_coles as dc
    except ImportError as exc:
        raise RuntimeError("optional_dixon_coles_dependency_not_installed") from exc
    model = dc.DixonColesModel(seed=42, xg_weight=xg_weight)
    inputs = dict(home_teams=np.array([h["home"] for h in accepted]),
                  away_teams=np.array([h["away"] for h in accepted]),
                  home_goals=np.array([h["home_goals"] for h in accepted], dtype=int),
                  away_goals=np.array([h["away_goals"] for h in accepted], dtype=int),
                  dates=np.array([np.datetime64(_time(h["completed_at_utc"]).replace(tzinfo=None), "D") for h in accepted]))
    if xg_weight != 1.0:
        inputs.update(home_xg=np.array([float(h["home_xg"]) for h in accepted]),
                      away_xg=np.array([float(h["away_xg"]) for h in accepted]))
    model.fit(**inputs)
    result = model.predict(fixture["home"], fixture["away"])
    # Upstream predict() rounds to 4 decimals; normalize to satisfy strict 1e-6 contract.
    probs = normalize_dixon_probabilities(result)
    prediction = dict(fixture_id=fixture["fixture_id"], league=league,
                      kickoff_utc=fixture["kickoff_utc"], frozen_at_utc=frozen_at_utc,
                      model_id="callumfm-dixon-coles", model_version=model_version,
                      p_home=probs[0], p_draw=probs[1], p_away=probs[2])
    return validate_shadow_prediction(prediction, as_of=frozen_at_utc)
