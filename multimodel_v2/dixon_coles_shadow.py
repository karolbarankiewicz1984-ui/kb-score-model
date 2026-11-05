"""Optional Dixon-Coles shadow adapter; never called by production.

Requires separately installed dixon-coles package and verified historical outcomes.
"""
from datetime import datetime, timezone
from math import isfinite
from .external_model_shadow import validate_shadow_prediction

def _time(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone_required")
    return t.astimezone(timezone.utc)

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
        if end >= freeze or published > freeze:
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
    prediction = dict(fixture_id=fixture["fixture_id"], league=league,
                      kickoff_utc=fixture["kickoff_utc"], frozen_at_utc=frozen_at_utc,
                      model_id="callumfm-dixon-coles", model_version=model_version,
                      p_home=result["home_win"], p_draw=result["draw"], p_away=result["away_win"])
    return validate_shadow_prediction(prediction, as_of=frozen_at_utc)
