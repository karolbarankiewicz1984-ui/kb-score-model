"""Strict, read-only KB Score 3 -> GitHub Models historical-results bridge.

Accepts only independently verifiable final results. Never imports KB3
probabilities, model weights, or training/test labels from forecast files.
"""
from datetime import datetime, timezone

def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timezone_required")
    return t.astimezone(timezone.utc)

def import_verified_results(rows, *, as_of_utc):
    cutoff = _utc(as_of_utc)
    accepted, rejected, seen = [], {}, set()
    for i, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise ValueError("not_mapping")
            if row.get("status") != "FINISHED":
                raise ValueError("not_finished")
            required = ("fixture_id", "league", "home", "away", "home_goals",
                        "away_goals", "completed_at_utc", "published_at_utc",
                        "source_provider", "source_record_id")
            if any(row.get(k) is None for k in required):
                raise ValueError("missing_provenance")
            if any(not isinstance(row[k], str) or not row[k].strip()
                   for k in ("fixture_id", "league", "home", "away",
                             "source_provider", "source_record_id")):
                raise ValueError("invalid_identity")
            if row["home"] == row["away"]:
                raise ValueError("same_team")
            if any(type(row[k]) is not int or row[k] < 0 for k in ("home_goals", "away_goals")):
                raise ValueError("invalid_goals")
            completed = _utc(row["completed_at_utc"])
            published = _utc(row["published_at_utc"])
            if completed > published or published > cutoff:
                raise ValueError("not_verified_before_cutoff")
            key = (row["source_provider"], row["source_record_id"])
            if key in seen:
                raise ValueError("duplicate_source_record")
            seen.add(key)
            accepted.append({k: row[k] for k in required if k != "source_provider" and k != "source_record_id"})
        except (ValueError, TypeError, KeyError) as exc:
            reason = str(exc)
            rejected[reason] = rejected.get(reason, 0) + 1
    return {"accepted": accepted, "accepted_count": len(accepted),
            "rejected_count": sum(rejected.values()), "rejection_reasons": rejected,
            "source": "kb-score-3-read-only-export", "production_models_unchanged": True}
