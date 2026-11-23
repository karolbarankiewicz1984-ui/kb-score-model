"""Read-only Superbet/OddsPapi market-identity safety audit.

This module NEVER promotes odds to a model prediction or claims that a provider's
disciplinary statistics match an independently sourced settlement feed.
It consumes existing archived quotes only (no network or bookmaker API).
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from math import isfinite
from pathlib import Path
from github_models.disciplinary_rules import review_football_data_schema, SUPERBET_FOOTBALL_RULES, SUPERBET_OPTA_NOTICE

POLISH_BOOKMAKER = "superbet.pl"
RULES_VERSION = "2026-11-20-research-v1"
MIN_ODDS = 1.20

# Names/types observed in OddsPapi snapshots are NOT necessarily the names
# shown to players on Superbet. Exact quote identity and provider conventions
# require independent confirmation before any promotion to a playable market.
GOALS = ("over under full time", "totals")
CORNERS = ("corners - over under full time", "totals-corners")
BTTS = ("both teams to score", "btts")


def _fold(value):
    return " ".join(str(value or "").casefold().split())


def _time(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt


def _is_number(value):
    return type(value) in (int, float) and isfinite(value)


def classify_quote(q):
    """Conservative research classification; never imply official settlement."""
    if q.get("bookmaker") != POLISH_BOOKMAKER:
        raise ValueError("unapproved_bookmaker")
    name, kind = _fold(q.get("market_name")), _fold(q.get("market_type"))
    period = _fold(q.get("period"))
    player = bool(q.get("player_prop")) or str(q.get("player_id", "0")) != "0"
    outcome = _fold(q.get("outcome_name"))
    line = q.get("handicap")
    if not _is_number(q.get("odds")) or q["odds"] <= 1:
        return {"family": "invalid", "reason": "invalid_price",
                "comparison_allowed": False, "settlement_allowed": False}
    price_eligible = q["odds"] >= MIN_ODDS
    if player or "player" in name or kind.startswith("player"):
        reason = "player_scope_not_match_total"
        family = ("player_fouls" if "foul" in name else
                  "player_cards" if "card" in name else
                  "player_props")
    elif "foul" in name:
        family = "match_fouls"
        if period != "fulltime":
            reason = "period_not_fulltime"
        elif name in ("fouls over under full time", "total fouls over under full time"):
            reason = "independent_foul_stat_source_unverified"
        else:
            reason = "market_identity_not_verified"
    elif "booking" in name or "card" in name:
        family = "bookings_or_cards"
        reason = ("period_not_fulltime" if period != "fulltime"
                  else "booking_vs_yellow_card_units_unverified")
    elif "handicap" in name:
        if "european" in name or kind == "spreads-european":
            family, reason = "european_handicap", "three_way_not_asian_handicap"
        elif name == "asian handicap" and kind == "spreads":
            family, reason = "asian_handicap", ("period_not_fulltime" if period != "fulltime"
                                               else "provider_line_sign_and_side_unverified")
        else:
            family, reason = "other_handicap", "market_identity_not_verified"
    elif (name, kind) == GOALS and period == "fulltime" and not player:
        family, reason = "goals", "existing_exact_comparison_only"
    elif (name, kind) == CORNERS and period == "fulltime" and not player:
        family, reason = "corners", "existing_exact_comparison_only"
    elif name == BTTS[0] and period == "fulltime" and outcome in ("yes", "no"):
        family, reason = "btts", "research_exact_fulltime_quote"
    else:
        family, reason = "other", "unmapped_or_different_scope"
    if family in ("goals", "corners", "btts"):
        if family != "btts" and (not _is_number(line) or line < 0 or outcome not in ("over", "under")):
            reason = "line_or_selection_not_verified"
        if not price_eligible:
            reason = "price_below_1_20"
    safe_comparison = family in ("goals", "corners", "btts") and reason in (
        "existing_exact_comparison_only", "research_exact_fulltime_quote")
    return {
        "family": family, "reason": reason, "period": period,
        "market_id": str(q.get("market_id", "")),
        "selection": outcome, "line": line if _is_number(line) else None,
        "price_eligible": bool(price_eligible),
        # This audit does not have independently reconciled official settlement
        # records; even recognized prices are NOT a verified betting outcome.
        "comparison_allowed": safe_comparison,
        "settlement_allowed": False,
        "requires_official_rule_and_stat_source_match": True,
    }


def settle_half_goal_handicap(home_goals, away_goals, *, team, line):
    """Test *mathematics only*, not OddsPapi's sign/side conventions.

    Half-goal handicap: no push. Quarter/integer lines are rejected rather
    than being silently treated as equivalent.
    """
    if (type(home_goals) is not int or type(away_goals) is not int or
            min(home_goals, away_goals) < 0 or team not in ("home", "away") or
            not _is_number(line) or
            line not in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)):
        raise ValueError("unsupported_half_goal_handicap_identity")
    own, opp = (home_goals, away_goals) if team == "home" else (away_goals, home_goals)
    return own + line > opp


def audit(collection, gaps=None):
    """Group observed quote semantics, do not infer bookmaker equivalence."""
    if collection.get("bookmakers") != [POLISH_BOOKMAKER]:
        raise ValueError("only_superbet_scope_is_allowed")
    counter = Counter()
    families = Counter()
    sample_ids = {}
    count = 0
    snapshots = collection.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("missing_collection_snapshots")
    for snapshot in snapshots:
        if snapshot.get("provider") != "oddspapi-v4":
            raise ValueError("unexpected_provider")
        if not _time(snapshot["captured_at_utc"]) < _time(snapshot["kickoff_utc"]):
            raise ValueError("quote_snapshot_not_prematch")
        for q in snapshot.get("quotes", []):
            assessed = classify_quote(q)
            if q.get("changed_at_utc"):
                try:
                    if _time(q["changed_at_utc"]) >= _time(snapshot["kickoff_utc"]):
                        counter["provider_quote_after_kickoff"] += 1
                        continue
                except (TypeError, ValueError):
                    counter["invalid_provider_quote_time"] += 1
                    continue
            families[assessed["family"]] += 1
            counter[assessed["reason"]] += 1
            if assessed["comparison_allowed"]:
                counter["known_exact_comparison_quote_not_settlement"] += 1
            if assessed["settlement_allowed"]:
                raise AssertionError("unsafe_automatic_settlement")
            if assessed["family"] not in sample_ids:
                # Exclude any athlete names, source access keys or raw responses.
                sample_ids[assessed["family"]] = {
                    "market_id": assessed["market_id"],
                    "market_name": q.get("market_name"),
                    "market_type": q.get("market_type"),
                    "period": assessed["period"],
                    "outcome_name": q.get("outcome_name"),
                    "handicap": assessed["line"],
                }
            count += 1
    mismatch = {}
    if gaps is not None:
        if gaps.get("bookmaker") != POLISH_BOOKMAKER:
            raise ValueError("market_gap_bookmaker_mismatch")
        by = gaps.get("by_market", {})
        for family in ("fouls", "cards"):
            row = by.get(family, {})
            mismatch[family] = {
                "modeled_candidates": row.get("high_confidence_candidates"),
                "without_comparable_offer": row.get("no_verified_comparable_quote"),
                "reasons": row.get("reasons", {}),
            }
    return {
        "schema": "multimodel-market-rule-gate-v1",
        "rules_version": RULES_VERSION,
        "source_snapshot_utc": collection.get("as_of_utc"),
        "bookmaker": POLISH_BOOKMAKER,
        "snapshots_checked": len(snapshots),
        "quotes_checked": count,
        "family_counts": dict(sorted(families.items())),
        "reason_counts": dict(sorted(counter.items())),
        "representative_market_identifiers": sample_ids,
        "model_vs_bookmaker_gaps": mismatch,
        "settlement_rule_state": {
            "match_fouls": "blocked_until_independent_foul_stat_source_equivalence",
            "bookings_or_cards": "blocked_until_booking_unit_and_card_rules_verified",
            "asian_handicap": "blocked_until_odds_side_sign_convention_verified",
            "european_handicap": "not_equivalent_to_asian_half_goal",
        },
        "disciplinary_source_validation": review_football_data_schema(),
        "bookings_unit_status": "provider_confirmation_missing_oddsPapi_v4",
        "independent_opta_per_match_coverage_outside_PL": 0,
        "official_superbet_rules": {
            "football_effective": "2025-12-16",
            "official_stats_source_notice_effective": "2026-04-29",
            "fouls": "referee_whistled_only_advantage_excluded",
            "cards": "yellow_one_straight_red_two_second_yellow_dismissal_three",
            "staff_bench_postwhistle": "excluded",
            "corner_counts": "awarded_but_not_taken_excluded",
            "sources": [SUPERBET_FOOTBALL_RULES,SUPERBET_OPTA_NOTICE],
        },
        "automatically_promoted_markets": [],
        "new_paid_api_calls": 0,
        "production_models_unchanged": True,
        "quality_score_67_100_mandatory": False,
        "note": "Only historical archived market-name and price inventory; never infer bookmaker official settlement.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--collection", required=True)
    p.add_argument("--gaps")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    result = audit(read(a.collection), read(a.gaps) if a.gaps else None)
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print("MARKET_RULES_AUDIT=PASS")
    print("MARKET_RULES_QUOTES=" + str(result["quotes_checked"]))
    for family in ("match_fouls", "player_fouls", "bookings_or_cards",
                   "asian_handicap", "european_handicap"):
        print("MARKET_RULES_" + family.upper() + "=" + str(result["family_counts"].get(family, 0)))


if __name__ == "__main__":
    main()
