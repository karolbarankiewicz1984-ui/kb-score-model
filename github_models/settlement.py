"""Conservative research settlement with exact, auditable match identity."""
import math
import re
from datetime import date
from zoneinfo import ZoneInfo
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize
from github_models.elo_engine import utc

COUNTRY_ZONES = {"ENG": "Europe/London", "DEU": "Europe/Berlin", "GER": "Europe/Berlin",
                 "ITA": "Europe/Rome", "ESP": "Europe/Madrid", "FRA": "Europe/Paris",
                 "NLD": "Europe/Amsterdam", "PRT": "Europe/Lisbon", "TUR": "Europe/Istanbul",
                 "BEL": "Europe/Brussels", "AUT": "Europe/Vienna",
                 "SCO": "Europe/London", "GRC": "Europe/Athens"}


def fixture_index(queue):
    """A duplicated queue identity must never silently overwrite another match."""
    fixtures = {}
    for row in queue["fixtures"]:
        value = row["fixture_id"]
        key = str(value)
        if value is None or isinstance(value, bool) or not key.strip() or key in fixtures:
            raise ValueError("duplicate_or_invalid_fixture_identity")
        fixtures[key] = row
    return fixtures


def probability_vector(prediction):
    values = [prediction[k] for k in ("p_home", "p_draw", "p_away")]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
           for v in values) or abs(sum(values) - 1) > 1e-6:
        raise ValueError("invalid_probabilities")
    return values


def source_match_date(row):
    """Use explicit dates or dated football-data IDs, never infer actual kickoff.

    completed_at_utc is either an actual completion time or a conservative bound.
    Subtracting two days from an arbitrary provider timestamp can settle the
    wrong match, so undated legacy rows remain unresolved.
    """
    dates = []
    if row.get("match_date"):
        dates.append(date.fromisoformat(row["match_date"]))
    if row.get("kickoff_utc"):
        zone = ZoneInfo(COUNTRY_ZONES.get(canonicalize(row).get("country_code"), "UTC"))
        dates.append(utc(row["kickoff_utc"]).astimezone(zone).date())
    match = re.match(r"^fdco:[^:]+:[^:]+:(\d{4}-\d{2}-\d{2}):", str(row.get("fixture_id", "")))
    if match:
        dates.append(date.fromisoformat(match[1]))
    if len(set(dates)) > 1:
        raise ValueError("historical_match_date_conflict")
    if dates:
        return dates[0]
    raise ValueError("historical_match_date_unverified")


def _frozen_team_id(identity, side):
    """Read synonymous native keys without inventing a cross-provider ID map."""
    values = []
    for field in (side + "_id", side + "_team_id"):
        value = identity.get(field)
        if value is not None:
            if type(value) not in (str, int) or not str(value).strip():
                raise ValueError("frozen_fixture_identity_mismatch")
            values.append(str(value).strip())
    if len(set(values)) > 1:
        raise ValueError("frozen_fixture_identity_mismatch")
    return values[0] if values else None


def matching_outcomes(fixture, pool, *, as_of_utc, resolved_identity=None):
    """Return exact league, ordered-team and local-date candidates available now."""
    now = utc(as_of_utc)
    eligible = []
    for row in pool:
        try:
            completed, published = utc(row["completed_at_utc"]), utc(row["published_at_utc"])
            if not completed <= published <= now or completed >= now:
                continue
            if row.get("status", "FINISHED") != "FINISHED":
                continue
            eligible.append(row)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    mapped = resolve(canonicalize(fixture), eligible)
    if resolved_identity is not None:
        original = canonicalize(resolved_identity)
        if any(mapped.get(k) != original.get(k) for k in ("league", "home", "away")):
            raise ValueError("frozen_fixture_identity_mismatch")
        for field in ("country_code", "league_id"):
            if original.get(field) is not None and str(mapped.get(field)) != str(original[field]):
                raise ValueError("frozen_fixture_identity_mismatch")
        original_provider = original.get("source_provider")
        current_provider = mapped.get("source_provider")
        if original_provider is not None:
            if (not isinstance(original_provider, str) or not original_provider.strip()
                    or not isinstance(current_provider, str)
                    or current_provider.strip().casefold() != original_provider.strip().casefold()):
                raise ValueError("frozen_fixture_identity_mismatch")
        for side in ("home", "away"):
            original_id = _frozen_team_id(original, side)
            current_id = _frozen_team_id(mapped, side)
            if original_id is not None:
                # A native ID is meaningful only inside its frozen provider
                # namespace. Outcome-provider IDs are never compared here.
                if original_provider is None or current_id != original_id:
                    raise ValueError("frozen_fixture_identity_mismatch")
    zone = ZoneInfo(COUNTRY_ZONES.get(mapped.get("country_code"), "UTC"))
    day = utc(fixture["kickoff_utc"]).astimezone(zone).date()
    matches = []
    for row in eligible:
        try:
            canonical = canonicalize(row)
            if (canonical["league"], row["home"], row["away"]) != (mapped["league"], mapped["home"], mapped["away"]):
                continue
            if (source_match_date(row) == day
                    and utc(row["completed_at_utc"]) > utc(fixture["kickoff_utc"])):
                matches.append(row)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return matches


def settle(predictions, queue, history, as_of_utc):
    now = utc(as_of_utc)
    fixtures = fixture_index(queue)
    out = []
    matches_cache = {}
    for p in predictions["predictions"]:
        f = fixtures[str(p["fixture_id"])]
        kick, frozen = utc(f["kickoff_utc"]), utc(p["frozen_at_utc"])
        if frozen >= kick:
            raise ValueError("not_prematch")
        if frozen > now:
            raise ValueError("forecast_not_yet_frozen")
        prob = probability_vector(p)
        row = {"fixture_id": p["fixture_id"], "model_id": p["model_id"], "status": "pending"}
        if kick < now:
            try:
                cache_key = (str(p["fixture_id"]), repr(p.get("resolved_identity")))
                if cache_key not in matches_cache:
                    try:
                        matches_cache[cache_key] = (matching_outcomes(
                            f, history, as_of_utc=as_of_utc,
                            resolved_identity=p.get("resolved_identity")), None)
                    except (ValueError, KeyError, TypeError, AttributeError) as error:
                        matches_cache[cache_key] = (None, error)
                matches, error = matches_cache[cache_key]
                if error is not None:
                    raise error
                if len(matches) == 1:
                    h = matches[0]
                    if any(type(h[k]) is not int or h[k] < 0 for k in ("home_goals", "away_goals")):
                        raise ValueError("invalid_final_goals")
                    actual = 0 if h["home_goals"] > h["away_goals"] else 1 if h["home_goals"] == h["away_goals"] else 2
                    row.update(status="settled", actual=("1", "X", "2")[actual],
                        source_fixture_id=h.get("fixture_id"), source_match_date=source_match_date(h).isoformat(),
                        brier=sum((v - (i == actual))**2 for i, v in enumerate(prob)),
                        log_loss=-math.log(max(prob[actual], 1e-15)))
                elif len(matches) > 1:
                    row.update(status="ambiguous", reason="multiple_verified_outcomes")
                else:
                    row["reason"] = "no_exact_verified_outcome"
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                row.update(status="unmapped", reason=str(exc))
        out.append(row)
    return {"schema": "github-models-settlement-v1", "as_of_utc": as_of_utc, "settlements": out}
