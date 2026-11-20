"""Independent, uncalibrated SHADOW markets from pre-match observed final scores.

No bookmaker calls. Never modifies original A/B/C selections or probabilities.
Only BTTS and half-goal handicaps have a supported final-score settlement source.
Shots, shots on target and offsides explicitly remain blocked.
"""
from __future__ import annotations

from collections import defaultdict
from math import exp, isfinite
from github_models.competition_identity import canonicalize
from github_models.elo_engine import eligible_history, utc
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.settlement import fixture_index

MIN_LEAGUE, MIN_TEAM = 60, 8
SHADOW_MARKETS = ("btts", "handicap")
UNSUPPORTED = ("shots", "shots_on_target", "offsides")


def _pmf(rate, limit=30):
    if type(rate) not in (int, float) or not isfinite(rate) or not 0 <= rate <= 5:
        raise ValueError("invalid_shadow_rate")
    values = [exp(-rate)]
    for n in range(1, limit + 1):
        values.append(values[-1] * rate / n)
    total = sum(values)
    if total < 0.999999:
        raise ValueError("poisson_tail_too_large")
    return [x / total for x in values]


def _margin_p(home_rate, away_rate, line):
    """P(home goals + half-integer line > away goals), independent-Poisson proxy."""
    if line not in (-1.5, 1.5):
        raise ValueError("only_verified_half_goal_handicap_lines")
    h, a = _pmf(home_rate), _pmf(away_rate)
    return sum(ph * pa for hg, ph in enumerate(h) for ag, pa in enumerate(a)
               if hg + line > ag)


def _rates(league, home, away):
    """Source-backed league and team goals; conservative shrinkage to league baseline."""
    if len(league) < MIN_LEAGUE:
        return None
    h = [r for r in league if home in (r["home"], r["away"])]
    a = [r for r in league if away in (r["home"], r["away"])]
    if min(len(h), len(a)) < MIN_TEAM:
        return None
    league_home = sum(r["home_goals"] for r in league) / len(league)
    league_away = sum(r["away_goals"] for r in league) / len(league)

    def scored(rows, team):
        return [r["home_goals"] if r["home"] == team else r["away_goals"]
                for r in rows]

    def conceded(rows, team):
        return [r["away_goals"] if r["home"] == team else r["home_goals"]
                for r in rows]

    # Weights explicitly documented; retrospective proxy, NOT calibrated.
    home_goals = scored(h, home) + conceded(a, away)
    away_goals = scored(a, away) + conceded(h, home)
    home_rate = (sum(home_goals) + 20 * league_home) / (len(home_goals) + 20)
    away_rate = (sum(away_goals) + 20 * league_away) / (len(away_goals) + 20)
    if not all(isfinite(v) and 0 <= v <= 5 for v in (home_rate, away_rate)):
        return None
    return home_rate, away_rate, len(league), len(h), len(a)


def run(queue, historical_results, as_of_utc):
    cutoff = utc(as_of_utc)
    fixture_index(queue)
    history = eligible_history(historical_results, frozen_at_utc=as_of_utc)
    by_league = defaultdict(list)
    for row in history:
        by_league[row["league"]].append(row)
    results, blockers = [], []
    for f in queue["fixtures"]:
        fid = f["fixture_id"]
        if utc(f["kickoff_utc"]) <= cutoff:
            continue
        try:
            mapped = resolve(canonicalize(f), history)
            rates = _rates(by_league[mapped["league"]], mapped["home"], mapped["away"])
        except (KeyError, ValueError, TypeError):
            rates = None
            mapped = None
        if rates is None:
            blockers.append({"fixture_id": fid, "reason": "unverified_identity_or_goal_history",
                             "markets": list(SHADOW_MARKETS)})
            continue
        lh, la, league_n, home_n, away_n = rates
        identity = {key: mapped[key] for key in (
            "league", "country_code", "league_id", "home", "away", "home_id",
            "away_id", "home_team_id", "away_team_id", "source_provider")
            if key in mapped}
        common = dict(fixture_id=fid, frozen_at_utc=as_of_utc,
                      model_id="shadow-goals-independent-poisson-v1",
                      probability_status="uncalibrated_research",
                      scope="SHADOW_NOT_PRODUCTION", bookmaker_odds_verified=False,
                      expected_home_goals=round(lh, 6), expected_away_goals=round(la, 6),
                      league_n=league_n, home_n=home_n, away_n=away_n,
                      resolved_identity=identity)
        p_yes = (1 - exp(-lh)) * (1 - exp(-la))
        for side, p in (("yes", p_yes), ("no", 1 - p_yes)):
            results.append(dict(common, market="btts", selection=side, line=None,
                                probability=round(p, 6)))
        for line in (-1.5, 1.5):
            p_home = _margin_p(lh, la, line)
            results.append(dict(common, market="handicap", selection="home",
                                line=line, probability=round(p_home, 6)))
            results.append(dict(common, market="handicap", selection="away",
                                line=-line, probability=round(1 - p_home, 6)))
    return dict(schema="multimodel-v2-shadow-markets-v1", generated_at_utc=as_of_utc,
                model_status="uncalibrated_research", odds_verified=False,
                odds_minimum=1.20, no_67_point_quality_gate=True,
                no_change_to_abc=True, candidates=results, blockers=blockers,
                unsupported_markets={market: "independent_verified_history_missing"
                                     for market in UNSUPPORTED},
                note="Prospective frozen scores only; exact market and price require separate verification.")
