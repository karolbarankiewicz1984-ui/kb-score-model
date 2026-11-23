"""Transparent gaps: original models' goals/corners/fouls/cards vs real Superbet quotes.

No alternative sportsbook, player-foul substitutions, or unsupported yellow-card
settlement equivalence. The absence of quotes never deletes a frozen prediction.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

from github_models.oddspapi_integration import classify_market, _selection
from github_models.oddspapi_market import utc

MODEL_MARKETS = ("goals", "corners", "fouls", "cards")
THRESHOLD = .67


def coverage(collection, frozen_events, *, as_of_utc, threshold=THRESHOLD):
    now = utc(as_of_utc)
    if collection.get("bookmakers") != ["superbet.pl"]:
        raise ValueError("invalid_bookmaker_scope")
    if not isinstance(frozen_events.get("markets"), list):
        raise ValueError("frozen_events_missing")
    links = {str(x["fixture_id"]): x for x in collection["links"]["links"]
             if x.get("status") == "matched"}
    fixtures = {}
    observed_names = Counter()
    for snap in collection.get("snapshots", []):
        if snap.get("provider") != "oddspapi-v4":
            raise ValueError("provider_mismatch")
        fid = str(snap.get("pitch_fixture_id", ""))
        if fid not in links or links[fid]["odds_fixture_id"] != str(snap["fixture_id"]):
            raise ValueError("unverified_snapshot_fixture_link")
        if utc(snap["captured_at_utc"]) > now or utc(snap["captured_at_utc"]) >= utc(snap["kickoff_utc"]):
            raise ValueError("snapshot_not_prematch")
        if fid in fixtures:
            raise ValueError("duplicate_snapshot")
        fixtures[fid] = snap
        for quote in snap.get("quotes", []):
            if quote.get("bookmaker") != "superbet.pl":
                raise ValueError("non_superbet_quote")
            observed_names[classify_market(quote)["family"]] += 1
    candidate_groups = defaultdict(list)
    for r in frozen_events["markets"]:
        if r.get("market") not in MODEL_MARKETS:
            continue
        fid = str(r.get("fixture_id"))
        if fid not in fixtures:
            continue
        try:
            frozen = utc(r["frozen_at_utc"])
            kick = utc(fixtures[fid]["kickoff_utc"])
            score = r["probability"]
            line = r["line"]
            if (frozen > now or frozen >= kick or
                    type(score) not in (int, float) or not math.isfinite(score)
                    or type(line) not in (int, float) or not math.isfinite(line)
                    or not 0 <= score <= 1 or line < 0 or
                    r["selection"] not in {"over", "under"}):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        candidate_groups[(fid, r["market"], float(line))].append(r)
    candidates = []
    for (fid, market, line), both_sides in candidate_groups.items():
        top = max(both_sides, key=lambda r: (r["probability"], r["selection"]))
        p = top["probability"]
        if p < threshold:
            continue
        snapshot = fixtures[fid]
        exact = []
        similar = Counter()
        for quote in snapshot.get("quotes", []):
            ident = classify_market(quote)
            similar[ident["family"]] += 1
            if (ident["model_market"] == market
                    and type(ident["line"]) in (int, float)
                    and float(ident["line"]) == line
                    and _selection(quote, ident) == top["selection"]):
                exact.append(quote)
        eligible = [q for q in exact if type(q.get("odds")) in (int, float)
                    and math.isfinite(q["odds"]) and q["odds"] >= 1.20]
        if market == "cards":
            # A bookings total is not necessarily the yellow-card event total.
            status = ("booking_rules_unverified" if similar["cards_bookings"]
                      else "no_verified_yellow_cards_offer")
        elif eligible:
            status = "matched_priced_offer"
        elif exact:
            status = "only_offer_below_minimum_odds"
        elif market == "fouls" and similar["player_prop"]:
            status = "player_props_not_match_total"
        else:
            status = "no_exact_market_line"
        candidates.append({
            "fixture_id": fid, "home": snapshot["home"], "away": snapshot["away"],
            "kickoff_utc": snapshot["kickoff_utc"], "market": market,
            "line": line, "selection": top["selection"],
            "model_probability": p, "model_id": top.get("model_id"),
            "status": status,
            "verified_offer": (max(q["odds"] for q in eligible) if eligible else None),
            "available_booking_quotes": similar["cards_bookings"] if market == "cards" else None,
            "available_player_props": similar["player_prop"] if market == "fouls" else None,
        })
    counts = Counter(x["status"] for x in candidates)
    by_market = {}
    for market in MODEL_MARKETS:
        items = [x for x in candidates if x["market"] == market]
        by_market[market] = {"high_confidence_candidates": len(items),
                             "priced_and_settlement_compatible":
                                 sum(x["status"] == "matched_priced_offer" for x in items),
                             "no_verified_comparable_quote":
                                 sum(x["status"] != "matched_priced_offer" for x in items),
                             "reasons": dict(Counter(x["status"] for x in items))}
    return {
        "schema": "github-models-oddspapi-market-gaps-v1",
        "as_of_utc": as_of_utc,
        "bookmaker": "superbet.pl", "min_real_odds": 1.20,
        "min_frozen_probability": threshold,
        "available_snapshot_count": len(fixtures),
        "quote_categories": dict(observed_names),
        "candidate_count": len(candidates),
        "reason_counts": dict(counts),
        "by_market": by_market,
        "model_only_candidates": sorted(
            (r for r in candidates if r["status"] != "matched_priced_offer"),
            key=lambda r: (-r["model_probability"], r["kickoff_utc"], r["fixture_id"], r["market"]))[:80],
        "notes": [
            "Quotes missing from a bookmaker are not fabricated or replaced by different providers.",
            "Bookings/disciplinary points do not prove identical settlement to yellow-card counts.",
            "Player fouls cannot be treated as total match fouls.",
            "Frozen model-only predictions remain visible but not bookmaker-actionable.",
        ],
        "original_forecast_unchanged": True,
    }


if __name__ == "__main__":
    raise SystemExit("Use github_models.oddspapi_produce to build the market-gap report.")
