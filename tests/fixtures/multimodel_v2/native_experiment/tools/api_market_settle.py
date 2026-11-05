#!/usr/bin/env python3
"""Settle frozen API Market positions and rebuild calibration summary.

Settles all verified candidates from immutable API publications. No writes to KB Score CORE,
KB N or DEV N.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import api_market_scan as v2
from api_market_policy import target_date
from api_market_storage import frozen_candidates, atomic_write, dumps

WARSAW = ZoneInfo("Europe/Warsaw")
TARGET = target_date(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else (datetime.now(WARSAW).date() - timedelta(days=1)).isoformat())
SRC = Path("data/api_football/market_scan") / f"{TARGET}.json"
OUTDIR = Path("data/api_football/calibration")
CLOSE = Path("data/api_football/closing_snapshots") / TARGET

STAT_NAMES = {
    "yellow": "Yellow Cards",
    "corners": "Corner Kicks",
    "fouls": "Fouls",
    "shots": "Total Shots",
    "shots_on_goal": "Shots on Goal",
    "offsides": "Offsides",
    "goalkeeper_saves": "Goalkeeper Saves",
}


def stat_value(stats, name):
    for item in stats or []:
        if item.get("type") == name:
            return item.get("value")
    return None


def actual_metric(fixture, blocks, item):
    sides = ("home", "away") if item.get("market_scope") == "match" else (item.get("team_side"),)
    if item.get("market") == "team_goals":
        fulltime = (fixture.get("score") or {}).get("fulltime") or {}
        values = []
        for side in sides:
            value = fulltime.get(side)
            if value is None and fixture.get("fixture", {}).get("status", {}).get("short") == "FT":
                value = (fixture.get("goals") or {}).get(side)
            values.append(value)
        return sum(values) if all(isinstance(x, (int, float)) for x in values) else None
    if fixture.get("fixture", {}).get("status", {}).get("short") != "FT":
        return None  # No regulation-time statistical split for extra-time games.
    targets = [item.get("team_id")] if item.get("market_scope") != "match" else [
        (fixture.get("teams") or {}).get(side, {}).get("id") for side in sides]
    stat_name = STAT_NAMES.get(item.get("market"))
    if not stat_name:
        return None
    values = {block.get("team", {}).get("id"): stat_value(block.get("statistics") or [], stat_name)
              for block in blocks or []}
    actuals = [values.get(target) if target is not None else None for target in targets]
    return sum(actuals) if all(isinstance(x, (int, float)) for x in actuals) else None


def closing_for(item):
    if not CLOSE.exists():
        return None
    key = v2.market_key(item)
    try:
        kickoff = datetime.fromisoformat(str(item.get("kickoff") or "").replace("Z", "+00:00"))
    except Exception:
        kickoff = None
    best = None
    for path in sorted(CLOSE.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            captured = datetime.fromisoformat(str(payload.get("captured_at_utc") or "").replace("Z", "+00:00"))
        except Exception:
            continue
        if kickoff and captured > kickoff:
            continue
        for row in payload.get("items") or []:
            if row.get("key") == key and row.get("market_probability_pct") is not None:
                best = {
                    "captured_at_utc": payload.get("captured_at_utc"),
                    "market_probability_pct": row.get("market_probability_pct"),
                    "paired_books": row.get("paired_books"),
                    "bookmaker_spread_pp": row.get("bookmaker_spread_pp"),
                }
    return best


def brier(prob, outcome):
    if prob is None:
        return None
    return (float(prob) / 100.0 - float(outcome)) ** 2


def logloss(prob, outcome):
    if prob is None:
        return None
    q = min(0.999, max(0.001, float(prob) / 100.0))
    return -(outcome * math.log(q) + (1 - outcome) * math.log(1 - q))


def band(prob):
    if prob is None:
        return "NA"
    lo = int(float(prob) // 5) * 5
    return f"{lo}-{lo + 4}"


def mean_or_none(values):
    return round(sum(values) / len(values), 4) if values else None


def rebuild_summary():
    observations = []
    for path in OUTDIR.glob("20??-??-??.json"):
        try:
            observations.extend(json.loads(path.read_text(encoding="utf-8")).get("observations") or [])
        except Exception:
            pass

    # Repeated snapshots and settlement retries are never extra observations.
    observations = list({r["observation_id"]: r for r in observations
        if r.get("training_eligible") and r.get("observation_id")}.values())
    groups = {}
    def add(key, row):
        g = groups.setdefault(key, {"n": 0, "hits": 0, "brier_api": [], "brier_final": [], "logloss_api": [], "logloss_final": []})
        g["n"] += 1
        g["hits"] += int(row.get("hit") or 0)
        for field in ("brier_api", "brier_final", "logloss_api", "logloss_final"):
            value = row.get(field)
            if value is not None:
                g[field].append(value)

    for row in observations:
        add(f"version:{row.get('model_version')}", row)
        add("published:" + str(bool(row.get("published"))), row)
        add(f"market:{row.get('market')}", row)
        add(f"scope:{row.get('market_scope', 'team')}", row)
        add(f"direction:{row.get('direction', 'over')}", row)
        add(f"outcome:{row.get('market')}:{row.get('market_scope', 'team')}:{row.get('direction', 'over')}", row)
        add(f"status:{row.get('final_status') or 'LEGACY'}", row)
        add(f"api_band:{band(row.get('api_pure_pct'))}", row)
        add(f"final_band:{band(row.get('final_assessment_pct'))}", row)
        delta = float(row.get("market_delta_pp") or 0)
        add("market_direction:" + ("UP" if delta > 0.4 else "DOWN" if delta < -0.4 else "FLAT"), row)

    summary = {}
    for key, g in groups.items():
        summary[key] = {
            "n": g["n"],
            "hits": g["hits"],
            "hit_rate_pct": round(100.0 * g["hits"] / g["n"], 1) if g["n"] else None,
            "brier_api": mean_or_none(g["brier_api"]),
            "brier_final": mean_or_none(g["brier_final"]),
            "logloss_api": mean_or_none(g["logloss_api"]),
            "logloss_final": mean_or_none(g["logloss_final"]),
        }

    payload = {
        "schema": "api-market-calibration-summary-v1",
        "observations": len(observations),
        "distinct_fixtures": len({r["fixture_id"] for r in observations}),
        "correlation_note": "Different lines and markets of one fixture are correlated; checkpoints must consider distinct fixtures.",
        "groups": summary,
        "policy": {
            "n_lt_50": "observe_only",
            "n_50_99": "signals_only",
            "n_100_plus": "eligible_for_cautious_calibration",
            "n_250_plus": "stronger_basis",
            "automatic_weight_changes": False,
        },
        "isolation": "API_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }
    atomic_write(OUTDIR / "_summary.json", dumps(payload))
    return len(observations)


def main():
    positions = frozen_candidates(TARGET)
    if not positions:
        print(json.dumps({"date": TARGET, "status": "no-verified-prematch-predictions"}))
        return
    observations, errors, cache = [], [], {}

    for item in positions:
        fid = item.get("fixture_id")
        if fid is None:
            continue
        if fid not in cache:
            try:
                fp, _ = v2.api_get("fixtures", id=fid)
                if fp.get("errors"):
                    raise RuntimeError(json.dumps(fp["errors"]))
                fixtures = fp.get("response", [])
                sp, _ = v2.api_get("fixtures/statistics", fixture=fid)
                if sp.get("errors"):
                    raise RuntimeError(json.dumps(sp["errors"]))
                blocks = sp.get("response", [])
                cache[fid] = (fixtures[0] if fixtures else {}, blocks)
            except Exception as exc:
                errors.append({"fixture_id": fid, "error": str(exc)})
                cache[fid] = ({}, [])

        fixture, blocks = cache[fid]
        if fixture.get("fixture", {}).get("status", {}).get("short") not in {"FT", "AET", "PEN"}:
            continue
        actual = actual_metric(fixture, blocks, item)
        if not isinstance(actual, (int, float)):
            errors.append({"fixture_id": fid, "selection": item.get("selection"), "error": "missing_actual_metric"})
            continue

        hit = int(v2.outcome_hit(float(actual), float(item.get("line")), item.get("direction", "over")))
        final_pct = item.get("final_assessment_pct")
        if final_pct is None:
            final_pct = item.get("market_adjusted_pct", item.get("api_pure_pct"))
        final_status = item.get("final_status") or "LEGACY"
        row = {
            "date": TARGET,
            "observation_id": item["observation_id"],
            "prediction_id": item["prediction_id"],
            "prediction_path": item["prediction_path"],
            "captured_at_utc": item["captured_at_utc"],
            "model_version": item["model_version"],
            "training_eligible": item["training_eligible"],
            "published": item["published"],
            "ever_published": item["ever_published"],
            "team_id": item["team_id"],
            "kickoff": item.get("kickoff"),
            "fixture_id": fid,
            "selection": item.get("selection"),
            "competition": item.get("competition"),
            "category": item.get("category"),
            "market": item.get("market"),
            "market_scope": item.get("market_scope", "team"),
            "direction": item.get("direction", "over"),
            "team_side": item.get("team_side"),
            "bet_id": item.get("bet_id"),
            "line": item.get("line"),
            "actual": actual,
            "hit": hit,
            "api_pure_pct": item.get("api_pure_pct"),
            "competition_adjusted_pct": item.get("competition_adjusted_pct"),
            "samples": item.get("samples"),
            "context": item.get("context"),
            "market_data": item.get("market_data"),
            "reliability_adjusted_pct": item.get("reliability_adjusted_pct", item.get("api_pure_pct")),
            "market_adjusted_pct": item.get("market_adjusted_pct", item.get("api_pure_pct")),
            "market_delta_pp": item.get("market_delta_pp", 0),
            "final_assessment_pct": final_pct,
            "final_status": final_status,
            "closing": closing_for(item),
        }
        row["brier_api"] = brier(row["api_pure_pct"], hit)
        row["brier_final"] = brier(row["final_assessment_pct"], hit)
        row["logloss_api"] = logloss(row["api_pure_pct"], hit)
        row["logloss_final"] = logloss(row["final_assessment_pct"], hit)
        observations.append(row)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"{TARGET}.json"
    previous = json.loads(out.read_text(encoding="utf-8")).get("observations", []) if out.exists() else []
    merged = {x["observation_id"]: x for x in previous if x.get("observation_id")}
    merged.update({x["observation_id"]: x for x in observations})
    atomic_write(out, dumps({
        "schema": "api-market-settlement-v2",
        "date": TARGET,
        "source": "immutable-pre-match-publications",
        "observations": sorted(merged.values(), key=lambda x: x["observation_id"]),
        "errors": errors,
        "isolation": "API_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }))
    total = rebuild_summary()
    print(json.dumps({"date": TARGET, "settled": len(observations), "errors": len(errors), "calibration_total": total, "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
