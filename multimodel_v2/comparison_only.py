"""Comparison-only analysis of independent frozen forecasts.

This module cannot mutate, promote or publish MULTIMODEL production picks.
It only compares external predictions against a separately supplied frozen baseline.
"""
from .external_model_shadow import validate_shadow_prediction

def compare_frozen_forecasts(baseline, challengers, *, as_of):
    """Return immutable-style comparison rows; no weighting or selection."""
    base = validate_shadow_prediction(baseline, as_of=as_of)
    comparisons = []
    for challenger in challengers:
        other = validate_shadow_prediction(challenger, as_of=as_of)
        if (base["fixture_id"], base["league"], base["kickoff_utc"]) != (
            other["fixture_id"], other["league"], other["kickoff_utc"]
        ):
            raise ValueError("fixture_mismatch")
        if base["model_id"] == other["model_id"]:
            raise ValueError("baseline_model_not_independent")
        comparisons.append({
            "fixture_id": base["fixture_id"],
            "league": base["league"],
            "kickoff_utc": base["kickoff_utc"],
            "baseline_model": base["model_id"],
            "challenger_model": other["model_id"],
            "delta_home": round(other["p_home"] - base["p_home"], 8),
            "delta_draw": round(other["p_draw"] - base["p_draw"], 8),
            "delta_away": round(other["p_away"] - base["p_away"], 8),
            "comparison_only": True,
            "production_eligible": False,
            "ranking_weight": 0,
        })
    return comparisons
