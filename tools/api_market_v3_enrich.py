#!/usr/bin/env python3
"""API Market Scan v3 background enrichment.

Reads the v2 freeze, preserves API PURE provenance, then adds:
- reliability-adjusted conservative score (Wilson lower bounds),
- national-team competition weighting + cached last-20 history,
- domestic vs Europe context for international club matches,
- current injuries/referee/lineup context for audit,
- final assessment + simple STRONG/ACCEPT/WATCH status.

No writes to KB Score CORE, KB N or DEV N.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import api_market_scan as v2

WARSAW = ZoneInfo("Europe/Warsaw")
TARGET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else datetime.now(WARSAW).date().isoformat()
SOURCE = Path("data/api_football/market_scan") / f"{TARGET}.json"
OUT = SOURCE
NATIONAL_CACHE = Path("data/api_football/national_dynamic")
MAX_PUBLISH = 10
MIN_PUBLISH_FINAL = 75.0

NATIONAL_WEIGHTS = {
    "Friendlies": 0.55,
    "UEFA Nations League": 0.85,
    "World Cup": 1.00,
    "World Cup - Qualification Europe": 0.95,
    "Euro Championship": 1.00,
    "Euro Championship - Qualification": 0.95,
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def sv(stats, name):
    for x in stats or []:
        if x.get("type") == name:
            return x.get("value")
    return None


def stat_row_from_fixture(g, blocks):
    teams = []
    for b in blocks or []:
        s = b.get("statistics") or []
        teams.append({
            "team_id": b.get("team", {}).get("id"),
            "team": b.get("team", {}).get("name"),
            "corners": sv(s, "Corner Kicks"),
            "fouls": sv(s, "Fouls"),
            "yellow": sv(s, "Yellow Cards"),
            "red": sv(s, "Red Cards"),
            "shots": sv(s, "Total Shots"),
            "shots_on_goal": sv(s, "Shots on Goal"),
            "offsides": sv(s, "Offsides"),
            "goalkeeper_saves": sv(s, "Goalkeeper Saves"),
        })
    return {
        "fixture_id": g.get("fixture", {}).get("id"),
        "date": g.get("fixture", {}).get("date"),
        "referee": g.get("fixture", {}).get("referee"),
        "league": g.get("league", {}).get("name"),
        "country": g.get("league", {}).get("country"),
        "season": g.get("league", {}).get("season"),
        "home": g.get("teams", {}).get("home", {}).get("name"),
        "away": g.get("teams", {}).get("away", {}).get("name"),
        "home_id": g.get("teams", {}).get("home", {}).get("id"),
        "away_id": g.get("teams", {}).get("away", {}).get("id"),
        "goals": g.get("goals", {}),
        "score": g.get("score", {}),
        "teams": teams,
        "category": "national_team",
    }


def load_dynamic_rows():
    rows = []
    if not NATIONAL_CACHE.exists():
        return rows
    for p in NATIONAL_CACHE.glob("team_*.json"):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            rows.extend(payload.get("rows") or [])
        except Exception:
            pass
    return rows


def merge_rows(base, extra):
    by_id = {}
    for row in list(base) + list(extra):
        fid = row.get("fixture_id")
        if fid is None:
            continue
        r = dict(row)
        if "_category" not in r:
            r["_category"] = v2.row_category(r) or r.get("category")
        old = by_id.get(fid)
        if old is None or len(r.get("teams") or []) >= len(old.get("teams") or []):
            by_id[fid] = r
    return sorted(by_id.values(), key=lambda r: v2.parse_dt(r.get("date")))


def refresh_national_history(fixtures, base_rows):
    NATIONAL_CACHE.mkdir(parents=True, exist_ok=True)
    existing = {r.get("fixture_id"): r for r in merge_rows(base_rows, load_dynamic_rows())}
    team_ids = set()
    for g in fixtures:
        if v2.competition_category(g.get("league", {})) != "national_team":
            continue
        for side in ("home", "away"):
            tid = g.get("teams", {}).get(side, {}).get("id")
            if tid:
                team_ids.add(tid)

    summary = {"teams": len(team_ids), "new_statistics_calls": 0, "errors": []}
    for tid in sorted(team_ids):
        try:
            payload, _ = v2.api_get_all_pages("fixtures", team=tid, last=20, timezone="Europe/Warsaw")
            games = [] if payload.get("errors") else payload.get("response", [])
        except Exception as exc:
            summary["errors"].append({"team_id": tid, "stage": "fixtures", "error": str(exc)})
            continue
        rows = []
        for g in games:
            if g.get("fixture", {}).get("status", {}).get("short") not in {"FT", "AET", "PEN"}:
                continue
            if v2.competition_category(g.get("league", {})) != "national_team":
                continue
            fid = g.get("fixture", {}).get("id")
            if fid in existing and existing[fid].get("teams"):
                rows.append(existing[fid])
                continue
            try:
                detail, _ = v2.api_get("fixtures/statistics", fixture=fid)
                blocks = [] if detail.get("errors") else detail.get("response", [])
                row = stat_row_from_fixture(g, blocks)
                rows.append(row)
                existing[fid] = row
                summary["new_statistics_calls"] += 1
            except Exception as exc:
                summary["errors"].append({"fixture_id": fid, "stage": "statistics", "error": str(exc)})
        path = NATIONAL_CACHE / f"team_{tid}.json"
        path.write_text(json.dumps({
            "schema": "api-national-dynamic-v1",
            "team_id": tid,
            "target": TARGET,
            "rows": rows,
            "isolation": "API_DATA_ONLY_NO_KB_SCORE_CORE_WRITES",
            "kb_n_effect": 0,
            "dev_n_effect": 0,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def weighted_cov(series, line, n):
    vals = series[-n:]
    if not vals:
        return None
    denom = sum(w for _, w in vals)
    if denom <= 0:
        return None
    hits = sum(w for value, w in vals if value > line)
    raw_hits = sum(1 for value, _ in vals if value > line)
    return {"hits": raw_hits, "n": len(vals), "weighted_n": round(denom, 2), "pct": 100.0 * hits / denom}


def weighted_windows(series, line):
    return {f"L{n}": weighted_cov(series, line, n) for n in (5, 10, 15)}


def weighted_window_score(windows):
    weights = {"L5": 0.20, "L10": 0.30, "L15": 0.50}
    pairs = [(windows[k]["pct"], weights[k]) for k in weights if windows.get(k)]
    if not pairs:
        return None
    d = sum(w for _, w in pairs)
    return sum(p * w for p, w in pairs) / d


def national_series(history, team_id, market, opponent_allowed=False):
    out = []
    for row in history:
        league = row.get("league") or row.get("competition")
        weight = NATIONAL_WEIGHTS.get(league, 0.80)
        if opponent_allowed:
            other = v2.opponent_id(row, team_id)
            if other is None:
                continue
            value = v2.metric_value(row, other, market)
        else:
            value = v2.metric_value(row, team_id, market)
        if isinstance(value, (int, float)):
            out.append((float(value), weight))
    return out


def wilson_lower_pct(hits, n, z=1.0):
    if not n:
        return None
    p = float(hits) / float(n)
    den = 1.0 + z * z / n
    center = p + z * z / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return 100.0 * (center - margin) / den


def block_lower(block):
    if not block:
        return None
    return wilson_lower_pct(block.get("hits", 0), block.get("n", 0))


def reliability_from_blocks(own_l15, opp_l15, venue=None, venue_weight=0.10):
    a, b = block_lower(own_l15), block_lower(opp_l15)
    if a is None or b is None:
        return None
    if venue and block_lower(venue) is not None and venue_weight > 0:
        return (1.0 - venue_weight) * (0.61 * a + 0.39 * b) + venue_weight * block_lower(venue)
    return 0.61 * a + 0.39 * b


def recompute_national(item, fixture, rows):
    team_id = item["team_id"]
    opp_side = "away" if item["team_side"] == "home" else "home"
    opp_id = fixture.get("teams", {}).get(opp_side, {}).get("id")
    dt = v2.parse_dt(item.get("kickoff"))
    own_hist = v2.team_history(rows, team_id, dt, "national")
    opp_hist = v2.team_history(rows, opp_id, dt, "national")
    own_series = national_series(own_hist, team_id, item["market"], False)
    opp_series = national_series(opp_hist, opp_id, item["market"], True)
    if len(own_series) < 7 or len(opp_series) < 7:
        return None
    own_w = weighted_windows(own_series, item["line"])
    opp_w = weighted_windows(opp_series, item["line"])
    own_score, opp_score = weighted_window_score(own_w), weighted_window_score(opp_w)
    if own_score is None or opp_score is None:
        return None
    pure = 0.60 * own_score + 0.40 * opp_score
    reliability = reliability_from_blocks(own_w.get("L15"), opp_w.get("L15"), None, 0)
    return {
        "api_pure_pct": round(pure, 1),
        "reliability_adjusted_pct": round(reliability, 1) if reliability is not None else round(pure, 1),
        "national_weighting": {"own": own_w, "opponent_allowed": opp_w, "matches_own": len(own_series), "matches_opponent": len(opp_series)},
    }


def simple_combined(rows, team_id, opp_id, dt, market, line, scope):
    own_hist = v2.team_history(rows, team_id, dt, scope)
    opp_hist = v2.team_history(rows, opp_id, dt, scope)
    own_vals = [v2.metric_value(r, team_id, market) for r in own_hist]
    own_vals = [x for x in own_vals if isinstance(x, (int, float))]
    opp_vals = v2.opponent_allowed_values(opp_hist, opp_id, market)
    if len(own_vals) < 4 or len(opp_vals) < 4:
        return None
    ow, pw = v2.window_set(own_vals, line), v2.window_set(opp_vals, line)
    os, ps = v2.weighted_windows(ow), v2.weighted_windows(pw)
    if os is None or ps is None:
        return None
    pure = 0.61 * os + 0.39 * ps
    reliability = reliability_from_blocks(ow.get("L15"), pw.get("L15"), None, 0)
    return {"pure": pure, "reliability": reliability, "own": ow, "opp": pw, "n": min(len(own_vals), len(opp_vals))}


def recompute_europe(item, fixture, rows):
    team_id = item["team_id"]
    opp_side = "away" if item["team_side"] == "home" else "home"
    opp_id = fixture.get("teams", {}).get(opp_side, {}).get("id")
    dt = v2.parse_dt(item.get("kickoff"))
    domestic = simple_combined(rows, team_id, opp_id, dt, item["market"], item["line"], "domestic")
    europe = simple_combined(rows, team_id, opp_id, dt, item["market"], item["line"], "europe_only")
    if not domestic:
        return None
    w_euro = 0.0
    if europe:
        w_euro = clamp(0.15 + 0.025 * europe["n"], 0.20, 0.35)
    pure = domestic["pure"] if not europe else (1 - w_euro) * domestic["pure"] + w_euro * europe["pure"]
    rel = domestic["reliability"] if not europe else (1 - w_euro) * domestic["reliability"] + w_euro * europe["reliability"]
    return {
        "api_pure_pct": round(pure, 1),
        "reliability_adjusted_pct": round(rel, 1),
        "competition_split": {"domestic": domestic, "europe": europe, "europe_weight": round(w_euro, 3)},
    }


def reliability_existing(item):
    rel = reliability_from_blocks((item.get("own") or {}).get("L15"), (item.get("opponent_allowed") or {}).get("L15"), item.get("venue"), 0.10)
    return round(rel if rel is not None else float(item["api_pure_pct"]), 1)


def fetch_context(fixtures, positions):
    context = {"injuries": {}, "lineups": {}, "errors": []}
    try:
        injuries, _ = v2.api_get_all_pages("injuries", date=TARGET, timezone="Europe/Warsaw")
        for x in injuries.get("response", []) if not injuries.get("errors") else []:
            fid = x.get("fixture", {}).get("id")
            tid = x.get("team", {}).get("id")
            if fid and tid:
                key = f"{fid}|{tid}"
                slot = context["injuries"].setdefault(key, {"missing": 0, "questionable": 0, "items": []})
                typ = (x.get("player", {}).get("type") or "").lower()
                if "question" in typ:
                    slot["questionable"] += 1
                else:
                    slot["missing"] += 1
                slot["items"].append({"player": x.get("player", {}).get("name"), "type": x.get("player", {}).get("type"), "reason": x.get("player", {}).get("reason")})
    except Exception as exc:
        context["errors"].append({"stage": "injuries", "error": str(exc)})

    now = datetime.now(timezone.utc)
    for fid, g in fixtures.items():
        try:
            ko = datetime.fromisoformat(g.get("fixture", {}).get("date", "").replace("Z", "+00:00"))
            mins = (ko.astimezone(timezone.utc) - now).total_seconds() / 60.0
            if -5 <= mins <= 120:
                lineups, _ = v2.api_get("fixtures/lineups", fixture=fid)
                if not lineups.get("errors") and lineups.get("response"):
                    context["lineups"][str(fid)] = lineups.get("response")
        except Exception as exc:
            context["errors"].append({"fixture_id": fid, "stage": "lineups", "error": str(exc)})
    return context


def context_for_item(item, fixture, ctx):
    opp_side = "away" if item["team_side"] == "home" else "home"
    opp_id = fixture.get("teams", {}).get(opp_side, {}).get("id")
    own = ctx["injuries"].get(f"{item['fixture_id']}|{item['team_id']}", {"missing": 0, "questionable": 0})
    opp = ctx["injuries"].get(f"{item['fixture_id']}|{opp_id}", {"missing": 0, "questionable": 0})
    lineup_available = str(item["fixture_id"]) in ctx["lineups"]
    referee = fixture.get("fixture", {}).get("referee")
    # Context is audit-first in v3. It is not allowed to add positive points until calibrated.
    delta = 0.0
    flags = []
    if own.get("missing", 0) >= opp.get("missing", 0) + 4:
        delta -= 1.0
        flags.append("selected_team_more_missing")
    if own.get("missing", 0) >= 6:
        delta -= 0.5
        flags.append("selected_team_many_missing")
    delta = max(-1.5, delta)
    return {
        "adjustment_pp": delta,
        "selected_team_missing": own.get("missing", 0),
        "selected_team_questionable": own.get("questionable", 0),
        "opponent_missing": opp.get("missing", 0),
        "opponent_questionable": opp.get("questionable", 0),
        "official_lineup_available": lineup_available,
        "referee": referee,
        "flags": flags,
        "policy": "audit-first; only conservative negative guard before calibration",
    }


def status_for(final, market_signal):
    if final >= 84 and market_signal not in {"WARNING", "STRONG_WARNING"}:
        return "STRONG"
    if final >= 75 and market_signal != "STRONG_WARNING":
        return "ACCEPT"
    return "WATCH"


def comment_for(item):
    bits = []
    pure = item["api_pure_pct"]
    rel = item["reliability_adjusted_pct"]
    if rel <= pure - 6:
        bits.append("Historia wygląda mocno, ale wielkość lub stabilność próby obniża pewność.")
    elif rel <= pure - 2:
        bits.append("Próba jest wystarczająca, choć reliability lekko studzi surowy wynik historii.")
    else:
        bits.append("Wynik historyczny jest dobrze podparty wielkością próby.")
    sig = item.get("market_signal")
    if sig in {"STRONG_CONFIRMATION", "CONFIRMATION"}:
        bits.append("Rynek potwierdza kierunek.")
    elif sig in {"WARNING", "STRONG_WARNING"}:
        bits.append("Rynek jest ostrożniejszy i obniża ocenę.")
    else:
        bits.append("Rynek nie daje silnego sygnału w żadną stronę.")
    ctx = item.get("context") or {}
    if ctx.get("adjustment_pp", 0) < 0:
        bits.append("Bieżący kontekst kadrowy daje dodatkowy sygnał ostrożności.")
    elif ctx.get("official_lineup_available"):
        bits.append("Oficjalny skład jest już dostępny i nie uruchomił negatywnego filtra.")
    return " ".join(bits)


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing v2 source: {SOURCE}")
    base = json.loads(SOURCE.read_text(encoding="utf-8"))
    if base.get("schema") not in {"api-market-scan-v2", "api-market-scan-v3"}:
        raise SystemExit(f"Unexpected schema: {base.get('schema')}")

    fixtures_payload, headers = v2.api_get_all_pages("fixtures", date=TARGET, timezone="Europe/Warsaw")
    fixtures_all = fixtures_payload.get("response", []) if not fixtures_payload.get("errors") else []
    fixture_map = {g.get("fixture", {}).get("id"): g for g in fixtures_all}

    base_rows = v2.load_rows()
    national_refresh = refresh_national_history(fixtures_all, base_rows)
    rows = merge_rows(base_rows, load_dynamic_rows())

    raw_positions = base.get("background_candidates") or base.get("top_positions") or []
    context = fetch_context(fixture_map, raw_positions)
    prior = v2.load_prior_market_probabilities(TARGET)
    enriched = []

    for old in raw_positions:
        item = dict(old)
        fixture = fixture_map.get(item.get("fixture_id"))
        if not fixture:
            continue
        if item.get("category") == "national_team":
            rec = recompute_national(item, fixture, rows)
        elif item.get("category") == "international_club":
            rec = recompute_europe(item, fixture, rows)
        else:
            rec = {"api_pure_pct": float(item["api_pure_pct"]), "reliability_adjusted_pct": reliability_existing(item)}
        if rec:
            item.update(rec)

        # Re-apply the same market evidence against the v3 API PURE baseline.
        market = item.get("market_data") or {}
        market_item = v2.apply_market_overlay(item, market, prior)
        item.update({k: market_item[k] for k in ("market_adjusted_pct", "market_delta_pp", "market_signal", "market_reliability", "market_data", "market_movement_pp", "market_comment")})

        c = context_for_item(item, fixture, context)
        item["context"] = c
        rel_penalty = clamp(float(item["reliability_adjusted_pct"]) - float(item["api_pure_pct"]), -12.0, 0.0)
        item["reliability_penalty_pp"] = round(rel_penalty, 1)
        final = clamp(float(item["market_adjusted_pct"]) + rel_penalty + float(c["adjustment_pp"]), 1.0, 99.0)
        item["final_assessment_pct"] = round(final, 1)
        item["final_status"] = status_for(final, item.get("market_signal"))
        item["final_comment"] = comment_for(item)
        enriched.append(item)

    enriched.sort(key=lambda x: ({"STRONG": 2, "ACCEPT": 1, "WATCH": 0}[x["final_status"]], x["final_assessment_pct"], x["reliability_adjusted_pct"], x["confidence_api"]), reverse=True)
    published = [x for x in enriched if x["final_status"] in {"STRONG", "ACCEPT"} and x["final_assessment_pct"] >= MIN_PUBLISH_FINAL][:MAX_PUBLISH]

    payload = dict(base)
    payload.update({
        "schema": "api-market-scan-v3",
        "top_positions": published,
        "background_candidates": enriched,
        "v3": {
            "method": "API PURE + reliability guard + competition context + market overlay + conservative live context",
            "reliability": "Wilson lower-bound guard; never raises API PURE",
            "national_history": "cached last-20 national-team fixtures; competition weighted",
            "national_competition_weights": NATIONAL_WEIGHTS,
            "international_club": "domestic and Europe histories kept separate then blended by Europe sample",
            "context": "injuries/referee/near-kickoff official lineups; audit-first with max -1.5pp negative guard before calibration",
            "publish_min_final_pct": MIN_PUBLISH_FINAL,
            "national_refresh": national_refresh,
            "context_errors": context.get("errors", []),
        },
        "rate_limit_remaining_v3": headers.get("x-ratelimit-requests-remaining"),
        "isolation": "API_V3_ONLY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE_ON_KB_SCORE_CORE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    })
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": "api-market-scan-v3", "date": TARGET, "background": len(enriched), "published": len(published), "national_cache_rows": len(load_dynamic_rows()), "kb_n_effect": 0, "dev_n_effect": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
