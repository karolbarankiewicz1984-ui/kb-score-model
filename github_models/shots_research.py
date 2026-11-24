"""Isolated, offline MultiModel shots research. No API calls or production writes.

Strict source cutoffs and market identity guard; probabilities are exploratory
Poisson baselines, never betting recommendations. Postmatch labels cannot
be used as prematch features for the same fixture.
"""
from __future__ import annotations
from datetime import datetime
from math import exp, isfinite
from typing import Mapping

FAMILIES = ("shots_total", "shots_on_target")
SCOPES = ("home", "away", "match")
MIN_ODDS = 1.20
MIN_HISTORY = 5


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("timezone_missing")
    return d


def number(value):
    return type(value) in (float, int) and isfinite(value)


def observation(row: Mapping, *, forecast_cutoff_utc: str, fixture_kickoff_utc: str):
    """Validate an independently observed, historical team-match record."""
    cutoff, kickoff = timestamp(forecast_cutoff_utc), timestamp(fixture_kickoff_utc)
    if cutoff >= kickoff:
        raise ValueError("forecast_not_before_kickoff")
    recorded = timestamp(row["published_at_utc"])
    past_kickoff = timestamp(row["kickoff_utc"])
    if recorded > cutoff or past_kickoff >= cutoff:
        raise ValueError("historical_data_not_available_at_cutoff")
    if not row.get("source") or not row.get("fixture_id") or not row.get("team_id"):
        raise ValueError("missing_source_or_ids")
    if row.get("scope") not in ("team",):
        raise ValueError("not_team_match_observation")
    total, target = row.get("shots_total"), row.get("shots_on_target")
    if (type(total) is not int or type(target) is not int or
            total < 0 or target < 0 or target > total):
        raise ValueError("invalid_shot_counts")
    if row.get("stat_definition_verified") is not True:
        raise ValueError("unverified_stat_definition")
    return total, target


def research_probability(history, *, family, selection, line,
                         forecast_cutoff_utc, fixture_kickoff_utc):
    """Poisson baseline from 5+ historical observations, not calibrated."""
    if family not in FAMILIES or selection not in ("over", "under"):
        raise ValueError("unsupported_market")
    if not number(line) or line < .5 or (line % 1) != .5:
        raise ValueError("half_integer_line_required")
    if not isinstance(history, list):
        raise ValueError("history_list_required")
    values = [observation(r, forecast_cutoff_utc=forecast_cutoff_utc,
                          fixture_kickoff_utc=fixture_kickoff_utc)[0 if family == "shots_total" else 1]
              for r in history]
    # A duplicate record must not contribute multiple times.
    identities = [(str(r["fixture_id"]), str(r["team_id"])) for r in history]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate_historical_observation")
    if len(values) < MIN_HISTORY:
        return {"status": "insufficient_history", "probability": None,
                "history_n": len(values)}
    lam = sum(values) / len(values)
    k = int(line // 1)
    term = exp(-lam)
    cdf = term
    for i in range(1, k + 1):
        term *= lam / i
        cdf += term
    p = (1 - cdf) if selection == "over" else cdf
    return {"status": "research_only_uncalibrated", "probability": max(0., min(1., p)),
            "history_n": len(values), "expected_count": lam,
            "source": "historical_poisson_baseline_not_a_betting_pick"}


def archived_quote_eligible(quote, *, fixture_kickoff_utc):
    """Never equate unspecified provider shot scopes/markets with Superbet."""
    if quote.get("bookmaker") != "superbet.pl":
        return False
    if quote.get("family") not in FAMILIES or quote.get("scope") not in SCOPES:
        return False
    if (quote.get("period") != "fulltime" or
            quote.get("selection") not in ("over", "under") or
            quote.get("market_identity_verified") is not True):
        return False
    if (not number(quote.get("line")) or quote["line"] < .5 or
            quote["line"] % 1 != .5 or not number(quote.get("odds")) or
            quote["odds"] < MIN_ODDS):
        return False
    if quote["scope"] != "match" and not quote.get("team_id"):
        return False
    return timestamp(quote["captured_at_utc"]) < timestamp(fixture_kickoff_utc)


def combined_match_history(home_history, away_history, *, forecast_cutoff_utc,
                           fixture_kickoff_utc):
    """Join per match only when both teams have paired independently observed stats."""
    def index(rows):
        out = {}
        for r in rows:
            observation(r, forecast_cutoff_utc=forecast_cutoff_utc,
                        fixture_kickoff_utc=fixture_kickoff_utc)
            fid = str(r["fixture_id"])
            if fid in out:
                raise ValueError("duplicate_fixture_id")
            out[fid] = r
        return out
    h, a = index(home_history), index(away_history)
    paired = []
    for fid in sorted(h.keys() & a.keys()):
        if h[fid]["team_id"] == a[fid]["team_id"]:
            raise ValueError("same_team_on_both_sides")
        paired.append({"fixture_id": fid, "shots_total": h[fid]["shots_total"] + a[fid]["shots_total"],
                       "shots_on_target": h[fid]["shots_on_target"] + a[fid]["shots_on_target"]})
    return paired
