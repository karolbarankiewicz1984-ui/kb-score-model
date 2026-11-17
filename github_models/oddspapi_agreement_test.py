"""Prospective, matched-cohort test of whether Superbet agreement improves hits.

All, concordant and discordant are subsets of exactly the same frozen-price
population. We first select one predeclared strongest side per match-market-line,
then cap to three picks per fixture. No cherry-picked final outcomes, false EV
claims, production promotion or mixing market-implied P with model accuracy.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from statistics import mean

THRESHOLDS = (.67, .70, .75, .80)
AGREEMENT_MAX_PP = .10
REVIEW_MIN_UNIQUE_GAMES = 100
MIN_PER_GROUP_GAMES = 30


def _stats(rows):
    if not rows:
        return {"positions": 0, "distinct_matches": 0, "hit_rate": None,
                "brier": None, "log_loss": None, "gross_simulated_roi": None}
    h = lambda r: float(r["hit"])
    return {
        "positions": len(rows),
        "distinct_matches": len({r["fixture_id"] for r in rows}),
        "hit_rate": round(mean(h(r) for r in rows), 6),
        "brier": round(mean((r["p_model"] - h(r)) ** 2 for r in rows), 6),
        "log_loss": round(mean(-math.log(max(1e-12, r["p_model"] if r["hit"]
                                               else 1-r["p_model"])) for r in rows), 6),
        "gross_simulated_roi": round(mean(r["price"]*h(r)-1 for r in rows), 6),
    }


def _bootstrap_by_match(rows, *, trials=400):
    """Cluster resampling by fixture, not by correlated market selections."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["fixture_id"]].append(r)
    fixture_ids = sorted(groups)
    rng = random.Random(20261117)
    diffs = []
    for _ in range(trials):
        picked = [rng.choice(fixture_ids) for __ in fixture_ids]
        agreed = [r for fid in picked for r in groups[fid] if r["agreement"] == "agree"]
        disagreed = [r for fid in picked for r in groups[fid] if r["agreement"] == "disagree"]
        if not agreed or not disagreed:
            continue
        diffs.append(mean(float(x["hit"]) for x in agreed) -
                     mean(float(x["hit"]) for x in disagreed))
    if len(diffs) < int(.9 * trials):
        return None
    diffs.sort()
    return {"method": "fixture_cluster_bootstrap",
            "trials": len(diffs),
            "difference_agree_minus_disagree_pp": [
                round(100*diffs[int(.025*(len(diffs)-1))],2),
                round(100*diffs[int(.975*(len(diffs)-1))],2)]}


def compare_agreement(uniques, *, min_p=.67):
    """Accept conservative first-quote, independent-final, post-settlement records."""
    eligible = []
    dropped = Counter()
    for row in uniques:
        if row.get("status") != "settled" or type(row.get("hit")) is not bool:
            dropped["unsettled"] += 1
            continue
        p, fair, price = (row.get(x) for x in ("p_model", "p_market", "price"))
        if (type(p) not in (float, int) or type(fair) not in (float, int)
                or type(price) not in (float, int)
                or any(not math.isfinite(v) for v in (p,fair,price))
                or not 0<=p<=1 or not 0<=fair<=1 or price<1.20):
            dropped["unverified_fair_price_or_probability"] += 1
            continue
        if p < min_p:
            dropped["model_below_confidence_threshold"] += 1
            continue
        candidate = dict(row)
        candidate["agreement"] = ("agree" if abs(p-fair) <= AGREEMENT_MAX_PP
                                  else "disagree")
        eligible.append(candidate)
    # Avoid counting both directions of the same mutually exclusive O/U line.
    by_line = defaultdict(list)
    for row in eligible:
        by_line[(row["fixture_id"],row["market"],row["line"])].append(row)
    single = [sorted(group, key=lambda r: (-r["p_model"],r["selection"]))[0]
              for group in by_line.values()]
    by_fixture=defaultdict(list)
    for row in single:
        by_fixture[row["fixture_id"]].append(row)
    shortlist = [r for fid in sorted(by_fixture)
                 for r in sorted(by_fixture[fid],
                                 key=lambda r: (-r["p_model"],r["market"],r["line"]))[:3]]
    def groups(rows):
        return {name: _stats([r for r in rows if
                (name=="all" or r["agreement"] == name)])
                for name in ("all","agree","disagree")}
    totals=groups(shortlist)
    market_summary={}
    for market in sorted({r["market"] for r in shortlist}):
        market_summary[market]=groups([r for r in shortlist if r["market"] == market])
    thresholds={}
    for t in THRESHOLDS:
        thresholds[str(t)]=groups([r for r in shortlist if r["p_model"]>=t])
    # Only consider an inference when the groups contain enough independent
    # fixture outcomes. Still NOT authorization to promote model parameters.
    enough=(totals["all"]["distinct_matches"] >= REVIEW_MIN_UNIQUE_GAMES
            and totals["agree"]["distinct_matches"]>=MIN_PER_GROUP_GAMES
            and totals["disagree"]["distinct_matches"]>=MIN_PER_GROUP_GAMES)
    hits_a=totals["agree"]["hit_rate"]
    hits_d=totals["disagree"]["hit_rate"]
    interval=_bootstrap_by_match(shortlist) if enough else None
    return {
        "schema":"github-models-oddspapi-market-agreement-test-v1",
        "filter_pp": 10,
        "min_model_probability": min_p,
        "minimum_verified_price":1.20,
        "one_side_per_exact_match_market_line": True,
        "maximum_picks_per_match":3,
        "eligible_distinct_matches":totals["all"]["distinct_matches"],
        "excluded_reasons":dict(dropped),
        "suppressed_correlated_opposite_sides":len(eligible)-len(single),
        "suppressed_over_three_per_game":len(single)-len(shortlist),
        "same_population_comparison":totals,
        "by_market":market_summary,
        "by_probability_threshold":thresholds,
        "agree_minus_disagree_hit_rate_pp":
            round(100*(hits_a-hits_d),2) if hits_a is not None and hits_d is not None else None,
        "confidence_interval":interval,
        "minimum_evidence_reached":enough,
        "decision":("DESCRIPTIVE_TEST_ONLY_REQUIRES_HOLDOUT" if enough and interval
                    else "NOT_ENOUGH_INDEPENDENT_SETTLED_MATCHES"),
        "production_weights_unchanged":True,
        "note":"Non-randomized retrospective comparison; selection bias and within-fixture correlation. "
               "No causal attribution or independent bookmaker edge demonstrated.",
    }
