"""Strict, read-only KB Score 3 -> GitHub Models historical-results bridge.

Accepts only independently verifiable final results. Never imports KB3
probabilities, model weights, or training/test labels from forecast files.
"""
from datetime import date, datetime, timezone
from collections import Counter
from github_models.competition_identity import canonicalize

def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timezone_required")
    return t.astimezone(timezone.utc)

def import_verified_results(rows, *, as_of_utc):
    cutoff = _utc(as_of_utc)
    rows = list(rows)
    source_counts = Counter((row.get("source_provider"), row.get("source_record_id"))
        for row in rows if isinstance(row, dict)
        and isinstance(row.get("source_provider"), str)
        and isinstance(row.get("source_record_id"), str))
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
            if source_counts[key] > 1 or key in seen:
                raise ValueError("duplicate_source_record")
            canonical = canonicalize(row)  # Reject contradictory supplied identifiers.
            result = {k: canonical[k] for k in required if k != "source_provider" and k != "source_record_id"}
            if row.get("match_date") is not None:
                day = date.fromisoformat(row["match_date"])
                if day > completed.date():
                    raise ValueError("match_date_after_completion")
                result["match_date"] = day.isoformat()
            if row.get("kickoff_utc") is not None:
                if _utc(row["kickoff_utc"]) >= completed:
                    raise ValueError("kickoff_not_before_completion")
                result["kickoff_utc"] = row["kickoff_utc"]
            for field in ("league_id", "country_code", "home_id", "away_id"):
                if field in canonical:
                    result[field] = canonical[field]
            seen.add(key)
            accepted.append(result)
        except (ValueError, TypeError, KeyError) as exc:
            reason = str(exc)
            rejected[reason] = rejected.get(reason, 0) + 1
    return {"accepted": accepted, "accepted_count": len(accepted),
            "rejected_count": sum(rejected.values()), "rejection_reasons": rejected,
            "source": "kb-score-3-read-only-export", "production_models_unchanged": True}
