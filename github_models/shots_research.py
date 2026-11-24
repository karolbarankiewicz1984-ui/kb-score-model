"""Uncalibrated full-time shots research using already published archives."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import exp, fsum, isfinite, lgamma, log

FAMILIES = ("shots_total", "shots_on_target")
SCOPES = ("home", "away", "match")
SELECTIONS = ("over", "under")
MIN_ODDS = 1.20
MIN_HISTORY = 5
MAX_HISTORY = 10
MIN_MATCH_DURATION = timedelta(minutes=90)
HISTORY_SOURCE = "api-football-archive"
FREEZE_SCHEMA = "multimodel-shots-shadow-v1"
LINES = {
    "shots_total": {"team": (9.5, 11.5, 13.5), "match": (21.5, 23.5, 25.5)},
    "shots_on_target": {"team": (2.5, 3.5, 4.5), "match": (6.5, 7.5, 8.5)},
}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timezone_missing")
    return parsed


def number(value):
    return type(value) in (float, int) and abs(value) <= 1e308 and isfinite(value)


def identifier(value):
    return type(value) is int and value > 0 or isinstance(value, str) and bool(value.strip())


def half_line(value):
    return number(value) and 0.5 <= value <= 200.5 and value % 1 == 0.5


def observation(row, *, forecast_cutoff_utc, fixture_kickoff_utc, fixture_id=None):
    """Validate chronology, scope, two shot counts and provenance for one row."""
    cutoff, kickoff = timestamp(forecast_cutoff_utc), timestamp(fixture_kickoff_utc)
    if cutoff >= kickoff:
        raise ValueError("forecast_not_before_kickoff")
    recorded = timestamp(row.get("published_at_utc"))
    past_kickoff = timestamp(row.get("kickoff_utc"))
    if not past_kickoff + MIN_MATCH_DURATION <= recorded <= cutoff:
        raise ValueError("historical_data_not_available_at_cutoff")
    if not all(identifier(row.get(k)) for k in ("source", "fixture_id", "team_id")):
        raise ValueError("missing_source_or_ids")
    if fixture_id is not None and str(row["fixture_id"]) == str(fixture_id):
        raise ValueError("target_fixture_in_history")
    if row.get("scope") != "team" or row.get("period") != "fulltime":
        raise ValueError("not_fulltime_team_match_observation")
    total, target = row.get("shots_total"), row.get("shots_on_target")
    if not (type(total) is type(target) is int and 0 <= target <= total <= 200):
        raise ValueError("invalid_shot_counts")
    if row.get("stat_definition_verified") is not True:
        raise ValueError("unverified_stat_definition")
    return total, target


def poisson_probability(mean, line, selection):
    if selection not in SELECTIONS or not half_line(line):
        raise ValueError("unsupported_half_line_market")
    if not number(mean) or mean < 0:
        raise ValueError("invalid_expected_count")
    if mean == 0:
        return float(selection == "under")
    k = int(line)
    if k < mean:
        under = min(1., fsum(exp(i * log(mean) - mean - lgamma(i + 1)) for i in range(k + 1)))
        return under if selection == "under" else 1. - under
    # Sum the upper tail directly to retain precision for low shot rates.
    i = k + 1
    term = exp(i * log(mean) - mean - lgamma(i + 1))
    over = term
    while term > over * 1e-16:
        i += 1
        term *= mean / i
        over += term
    return over if selection == "over" else 1. - over


def research_probability(history, *, family, selection, line,
                         forecast_cutoff_utc, fixture_kickoff_utc, fixture_id=None):
    if family not in FAMILIES or selection not in SELECTIONS or not half_line(line):
        raise ValueError("unsupported_half_line_market")
    values, seen, cohorts = [], set(), set()
    for row in history:
        shot_counts = observation(row, forecast_cutoff_utc=forecast_cutoff_utc,
                                  fixture_kickoff_utc=fixture_kickoff_utc, fixture_id=fixture_id)
        identity = str(row["fixture_id"])
        if identity in seen:
            raise ValueError("duplicate_historical_observation")
        seen.add(identity)
        cohorts.add((str(row["team_id"]), row["source"]))
        values.append(shot_counts[FAMILIES.index(family)])
    if len(cohorts) > 1:
        raise ValueError("mixed_team_or_source_history")
    if len(values) < MIN_HISTORY:
        return {"status": "insufficient_history", "probability": None, "history_n": len(values)}
    mean = fsum(values) / len(values)
    return {"status": "research_only_uncalibrated", "history_n": len(values),
            "probability": poisson_probability(mean, line, selection), "expected_count": mean,
            "source": "historical_poisson_baseline"}


def archived_quote_eligible(quote, *, fixture_kickoff_utc, forecast_cutoff_utc, fixture_id, team_id=None):
    if (quote.get("bookmaker") != "superbet.pl" or quote.get("source") != "oddspapi-v4"
            or not identifier(quote.get("fixture_id")) or str(quote["fixture_id"]) != str(fixture_id)
            or not all(identifier(quote.get(k)) for k in ("odds_fixture_id", "market_id", "outcome_id"))
            or quote.get("family") not in FAMILIES or quote.get("scope") not in SCOPES
            or quote.get("period") != "fulltime" or quote.get("selection") not in SELECTIONS
            or quote.get("market_identity_verified") is not True or not half_line(quote.get("line"))
            or not number(quote.get("odds")) or quote["odds"] < MIN_ODDS):
        return False
    if quote["scope"] == "match":
        if team_id is not None or quote.get("team_id") is not None:
            return False
    elif not identifier(team_id) or str(quote.get("team_id")) != str(team_id):
        return False
    try:
        changed = timestamp(quote.get("changed_at_utc"))
        captured = timestamp(quote.get("captured_at_utc"))
        cutoff = timestamp(forecast_cutoff_utc)
        kickoff = timestamp(fixture_kickoff_utc)
        return changed <= captured <= cutoff < kickoff
    except ValueError:
        return False


def combined_match_history(home_history, away_history, *, forecast_cutoff_utc,
                           fixture_kickoff_utc):
    """Aggregate both sides of the same historical fixture and source."""
    def index(rows):
        indexed = {}
        for row in rows:
            observation(row, forecast_cutoff_utc=forecast_cutoff_utc,
                        fixture_kickoff_utc=fixture_kickoff_utc)
            identity = str(row["fixture_id"])
            if identity in indexed:
                raise ValueError("duplicate_fixture_id")
            indexed[identity] = row
        return indexed

    home, away = index(home_history), index(away_history)
    paired = []
    for fid in sorted(home.keys() & away.keys()):
        h, a = home[fid], away[fid]
        if (str(h["team_id"]) == str(a["team_id"]) or h["source"] != a["source"]
                or timestamp(h["kickoff_utc"]) != timestamp(a["kickoff_utc"])):
            raise ValueError("inconsistent_historical_fixture_pair")
        paired.append({"fixture_id": fid, **{f: h[f] + a[f] for f in FAMILIES}})
    return paired
