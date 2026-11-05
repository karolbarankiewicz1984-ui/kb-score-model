"""Audit whether historical result records can safely train Dixon-Coles.

Read-only and stdlib-only; no API calls, training or production modifications.
"""
from collections import Counter
from datetime import datetime, timezone

def _parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp_timezone_missing")
    return dt.astimezone(timezone.utc)

def audit_historical_results(records, *, as_of_utc):
    """Count accepted records and rejection reasons without guessing missing facts."""
    cutoff = _parse_utc(as_of_utc)
    reasons = Counter()
    accepted = []
    seen = set()
    for row in records:
        if not isinstance(row, dict):
            reasons["not_a_record"] += 1
            continue
        required = ("fixture_id", "league", "home", "away", "home_goals",
                    "away_goals", "completed_at_utc", "published_at_utc")
        if any(k not in row or row[k] is None for k in required):
            reasons["missing_verified_fields"] += 1
            continue
        try:
            completed = _parse_utc(row["completed_at_utc"])
            published = _parse_utc(row["published_at_utc"])
        except (ValueError, TypeError, OverflowError):
            reasons["invalid_timestamps"] += 1
            continue
        if completed >= cutoff or published > cutoff:
            reasons["not_known_before_cutoff"] += 1
            continue
        if published < completed:
            reasons["publication_before_completion"] += 1
            continue
        if any(not isinstance(row[k], str) or not row[k].strip()
               for k in ("fixture_id", "league", "home", "away")) or row["home"] == row["away"]:
            reasons["invalid_identity"] += 1
            continue
        if any(not isinstance(row[k], int) or isinstance(row[k], bool) or row[k] < 0
               for k in ("home_goals", "away_goals")):
            reasons["invalid_score"] += 1
            continue
        key = (row["league"], row["fixture_id"])
        if key in seen:
            reasons["duplicate_fixture"] += 1
            continue
        seen.add(key)
        accepted.append(row)
    return {"total": len(accepted) + sum(reasons.values()),
            "accepted": len(accepted), "rejected": sum(reasons.values()),
            "reasons": dict(sorted(reasons.items())),
            "eligible_for_training": bool(accepted)}
