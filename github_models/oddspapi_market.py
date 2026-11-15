"""Read-only OddsPapi v4 market adapter for isolated GitHub MultiModel research.

Captures ALL offered markets, not only fouls, and computes a no-vig reference
only for complete, active, same-bookmaker outcome sets. Never changes the
sports model or generates bookmaker odds. Requires ODDSPAPI_API_KEY in env.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

HOST = "https://api.oddspapi.io"
SAFE_ENDPOINTS = frozenset({"account", "markets", "bookmakers", "fixtures",
                            "odds", "odds-by-tournaments", "historical-odds"})
PROVIDER = "oddspapi-v4"


def utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_missing")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp_missing_timezone")
    return result.astimezone(timezone.utc)


def _json_file(path, value):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def api_get(endpoint, *, params=None, api_key=None):
    """Never include the key-bearing request URL or provider response in errors/logs."""
    if endpoint not in SAFE_ENDPOINTS:
        raise ValueError("unsupported_oddspapi_endpoint")
    key = api_key if api_key is not None else os.environ.get("ODDSPAPI_API_KEY")
    if not key:
        raise RuntimeError("ODDSPAPI_API_KEY_missing")
    args = dict(params or {})
    if "apiKey" in args:
        raise ValueError("api_key_must_not_be_passed_as_user_parameter")
    args["apiKey"] = key
    url = HOST + "/v4/" + endpoint + "?" + urlencode(args)
    try:
        with urlopen(url, timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError("oddspapi_http_" + str(exc.code)) from None
    except (URLError, TimeoutError):
        raise RuntimeError("oddspapi_connection_failed") from None
    except (UnicodeError, json.JSONDecodeError):
        raise RuntimeError("oddspapi_invalid_json") from None


def subscription_budget(account, *, requested=1, reserve=10):
    """Fail closed if active subscription quota cannot be established."""
    active_id = account.get("current_subscription_id")
    subs = [s for s in account.get("subscriptions", [])
            if s.get("is_active") and s.get("subscription_id") == active_id]
    if len(subs) != 1:
        raise RuntimeError("active_subscription_unverified")
    sub = subs[0]
    limit, count = sub.get("request_limit"), sub.get("request_count")
    if type(limit) is not int or type(count) is not int or limit < 1 or count < 0:
        raise RuntimeError("oddspapi_quota_unknown")
    if count + requested > max(0, limit - reserve):
        raise RuntimeError("oddspapi_quota_reserve_guard")
    return {"request_limit": limit, "request_count": count,
            "remaining_before_reserve": max(0, limit - count - reserve),
            "bookmakers_in_plan": sorted((sub.get("bookmakers") or {}).keys())}


def normalize_snapshot(payload, market_catalog, *, captured_at_utc, min_odd=1.20):
    """Preserve all active pre-match quotes and mark only complete-market no-vig."""
    captured = utc(captured_at_utc)
    kickoff = utc(payload.get("startTime"))
    if captured >= kickoff or payload.get("statusId") != 0:
        raise ValueError("snapshot_not_strictly_prematch")
    catalog = {str(m["marketId"]): m for m in market_catalog}
    quotes = []
    for bookmaker, block in (payload.get("bookmakerOdds") or {}).items():
        if not isinstance(block, dict) or not block.get("bookmakerIsActive") or block.get("suspended"):
            continue
        for market_id, market in (block.get("markets") or {}).items():
            if not market.get("marketActive"):
                continue
            info = catalog.get(str(market_id))
            for outcome_id, outcome in (market.get("outcomes") or {}).items():
                for player_id, quote in (outcome.get("players") or {}).items():
                    if not isinstance(quote, dict) or not quote.get("active"):
                        continue
                    price = quote.get("price")
                    if type(price) not in (int, float) or not math.isfinite(price) or price <= 1:
                        continue
                    changed_at = quote.get("changedAt")
                    if changed_at:
                        try:
                            if utc(changed_at) > captured:
                                continue
                        except ValueError:
                            continue
                    outcome_metadata = {}
                    if info:
                        outcome_metadata = next((o for o in info.get("outcomes", [])
                                                 if str(o.get("outcomeId")) == str(outcome_id)), {})
                    quotes.append({
                        "bookmaker": bookmaker, "market_id": str(market_id),
                        "market_name": info.get("marketName") if info else None,
                        "market_type": info.get("marketType") if info else None,
                        "period": info.get("period") if info else None,
                        "handicap": info.get("handicap") if info else None,
                        "player_prop": info.get("playerProp") if info else None,
                        "outcome_id": str(outcome_id),
                        "outcome_name": outcome_metadata.get("outcomeName"),
                        "player_id": str(player_id),
                        "player_name": quote.get("playerName"),
                        "bookmaker_outcome_id": quote.get("bookmakerOutcomeId"),
                        "odds": float(price),
                        "changed_at_utc": changed_at,
                        "timestamp_quality": "provider_and_snapshot" if changed_at else "snapshot_only",
                        "main_line": bool(quote.get("mainLine")),
                        "eligible_min_odd": price >= min_odd,
                        "no_vig_probability": None,
                    })
    groups = defaultdict(list)
    for row in quotes:
        groups[(row["bookmaker"], row["market_id"], row["player_id"])].append(row)
    for (_, market_id, _), group in groups.items():
        info = catalog.get(market_id)
        if not info:
            continue
        expected = {str(x.get("outcomeId")) for x in info.get("outcomes", [])}
        observed = [row["outcome_id"] for row in group]
        if not expected or len(expected) != info.get("marketLength") or len(observed) != len(expected):
            continue
        if set(observed) != expected or len(set(observed)) != len(observed):
            continue
        denom = sum(1.0 / row["odds"] for row in group)
        for row in group:
            row["no_vig_probability"] = round((1.0 / row["odds"]) / denom, 8)
    groups_by_market = defaultdict(list)
    for row in quotes:
        key = (row["market_id"], row["outcome_id"], row["player_id"])
        groups_by_market[key].append(row)
    summary = []
    for (market_id, outcome_id, player_id), group in sorted(groups_by_market.items()):
        prices = [r for r in group if r["eligible_min_odd"]]
        fair = [r["no_vig_probability"] for r in group if r["no_vig_probability"] is not None]
        best = max(prices, key=lambda r: r["odds"]) if prices else None
        summary.append({
            "market_id": market_id, "outcome_id": outcome_id, "player_id": player_id,
            "market_name": group[0]["market_name"], "period": group[0]["period"],
            "handicap": group[0]["handicap"], "outcome_name": group[0]["outcome_name"],
            "active_bookmakers": len({r["bookmaker"] for r in group}),
            "complete_bookmakers": len(fair),
            "consensus_no_vig_probability": round(statistics.median(fair), 8) if len(fair) >= 2 else None,
            "best_verified_price": best["odds"] if best else None,
            "best_price_bookmaker": best["bookmaker"] if best else None,
        })
    return {
        "schema": "github-models-oddspapi-market-overlay-v1",
        "research_only": True, "production_model_unchanged": True,
        "provider": PROVIDER, "fixture_id": payload.get("fixtureId"),
        "home": payload.get("participant1Name"), "away": payload.get("participant2Name"),
        "tournament_id": payload.get("tournamentId"),
        "kickoff_utc": kickoff.isoformat(), "captured_at_utc": captured.isoformat(),
        "min_practical_odd": min_odd, "market_catalog_complete": bool(market_catalog),
        "quotes": quotes, "market_summary": summary,
        "no_vig_note": "Complete active outcome sets at ONE bookmaker only; never mix books.",
        "matching_note": "No mapping to model predictions without verified fixture AND exact-market identity.",
    }



def normalize_history(payload, *, kickoff_utc):
    """Keep only recorded prices strictly earlier than a verified scheduled kickoff.

    This data is historical price evidence, NOT a retroactively frozen forecast.
    """
    cutoff = utc(kickoff_utc)
    filtered = []
    for bookmaker, b in (payload.get("bookmakers") or {}).items():
        for market_id, market in (b.get("markets") or {}).items():
            for outcome_id, outcome in (market.get("outcomes") or {}).items():
                for player_id, entries in (outcome.get("players") or {}).items():
                    for entry in entries if isinstance(entries, list) else []:
                        stamp, price = entry.get("createdAt"), entry.get("price")
                        try:
                            if utc(stamp) >= cutoff or type(price) not in (int, float) or not math.isfinite(price) or price <= 1:
                                continue
                        except (ValueError, TypeError):
                            continue
                        filtered.append({
                            "bookmaker": bookmaker, "market_id": str(market_id),
                            "outcome_id": str(outcome_id), "player_id": str(player_id),
                            "recorded_at_utc": stamp, "odds": float(price),
                            "active_at_record_time": entry.get("active"),
                            "limit": entry.get("limit"),
                        })
    return {"schema": "github-models-oddspapi-historical-prices-v1",
            "fixture_id": payload.get("fixtureId"), "scheduled_kickoff_utc": cutoff.isoformat(),
            "all_prices_strictly_prekickoff": True,
            "not_a_frozen_model_prediction": True, "provider": PROVIDER,
            "history": filtered}

def main(argv=None):
    p = argparse.ArgumentParser(description="Isolated OddsPapi catalog/quote snapshots")
    p.add_argument("mode", choices=("catalog", "snapshot", "history", "quota"))
    p.add_argument("--fixture-id")
    p.add_argument("--catalog")
    p.add_argument("--out")
    p.add_argument("--reserve", type=int, default=10)
    p.add_argument("--bookmakers", help="Comma-separated provider slugs, max 3 (history)")
    p.add_argument("--kickoff-utc", help="Verified scheduled kickoff ISO 8601 (history)")
    args = p.parse_args(argv)
    account = api_get("account")
    if args.mode == "quota":
        budget = subscription_budget(account, requested=0, reserve=args.reserve)
        print(json.dumps(budget))
        return
    if not args.out:
        p.error("--out is required")
    if args.mode in ("snapshot", "history") and not args.fixture_id:
        p.error("--fixture-id is required")
    if args.mode == "snapshot" and not args.catalog:
        p.error("--catalog is required")
    # Each billable request consumes one unit; historical odds are unmetered.
    subscription_budget(account, requested=0 if args.mode == "history" else 1, reserve=args.reserve)
    if args.mode == "catalog":
        result = api_get("markets", params={"language": "en"})
    elif args.mode == "history":
        books = [b.strip() for b in (args.bookmakers or "").split(",") if b.strip()]
        if not 1 <= len(books) <= 3 or len(set(books)) != len(books) or not args.kickoff_utc:
            p.error("history requires 1-3 distinct --bookmakers and --kickoff-utc")
        raw = api_get("historical-odds", params={"fixtureId": args.fixture_id,
                                                  "bookmakers": ",".join(books)})
        result = normalize_history(raw, kickoff_utc=args.kickoff_utc)
    else:
        catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        payload = api_get("odds", params={"fixtureId": args.fixture_id,
                                           "language": "en", "verbosity": 3})
        result = normalize_snapshot(payload, catalog,
                                    captured_at_utc=datetime.now(timezone.utc).isoformat())
    _json_file(args.out, result)
    print(json.dumps({"mode": args.mode, "saved": args.out,
                      "quotes": len(result.get("quotes", [])) if isinstance(result, dict) else None}))


if __name__ == "__main__":
    main()
