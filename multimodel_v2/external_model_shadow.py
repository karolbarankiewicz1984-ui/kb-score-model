"""Strict read-only contract for external model predictions in MULTIMODEL shadow.

No training, data fetches, production scoring, bookmaker odds or persistence.
"""
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping

REQUIRED = ("fixture_id", "league", "kickoff_utc", "frozen_at_utc",
            "model_id", "model_version", "p_home", "p_draw", "p_away")

def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone_required")
    return stamp.astimezone(timezone.utc)

def validate_shadow_prediction(row: Mapping, *, as_of: str) -> dict:
    """Accept only frozen, normalized, future-match 1X2 probabilities."""
    if not isinstance(row, Mapping):
        raise ValueError("mapping_required")
    if any(key not in row for key in REQUIRED):
        raise ValueError("missing_required_field")
    if any(not isinstance(row[key], str) or not row[key].strip()
           for key in REQUIRED[:6]):
        raise ValueError("invalid_identity")
    kickoff = _utc(row["kickoff_utc"])
    frozen = _utc(row["frozen_at_utc"])
    cutoff = _utc(as_of)
    if not frozen < kickoff:
        raise ValueError("post_kickoff_freeze")
    if frozen > cutoff:
        raise ValueError("future_freeze")
    if kickoff <= cutoff:
        raise ValueError("already_started")
    try:
        probabilities = [float(row[key]) for key in ("p_home", "p_draw", "p_away")]
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_probabilities") from exc
    if any(not isfinite(p) or p < 0 or p > 1 for p in probabilities):
        raise ValueError("probability_out_of_range")
    if abs(sum(probabilities) - 1) > 1e-6:
        raise ValueError("probabilities_not_normalized")
    return {key: row[key] for key in REQUIRED}
