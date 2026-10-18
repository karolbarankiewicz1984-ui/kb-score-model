"""New *experimental* xG shadow forecast paired with PRE-EXISTING goals shadow.

Both forecasts are fixed BEFORE kickoff and NEVER use market odds or final
scores. Original KB21 STR/QUAL/MATCH and P(model) are NEVER reconstructed.
No API requests; xG historical input has already been verified by the bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from tools.kb21_single_source_calendar import _iso_datetime
from tools.kb21_pitchapi_prematch_bridge import SCHEMA as XG_BRIDGE_SCHEMA
from tools.kb21_single_source_form import OUT_SCHEMA as FORM_SCHEMA

SCHEMA = "kb21-paired-xg-vs-goals-shadow-v1"
MODEL = "kb21-pitchapi-mean-xg-poisson-shadow-v1"
BASELINE = "kb21-api-last10-goals-shadow-v1"
GOALS_SCHEMA = "kb21-api-shadow-forecast-snapshot-v1"
REQUIRED = frozenset(("home", "draw", "away", "over_2_5"))


def _clock(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware capture clock is required")
    return now.astimezone(timezone.utc)


def _valid(p):
    return (isinstance(p, dict) and set(p) == REQUIRED and
            all(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1
                for v in p.values()) and
            abs(sum(p[k] for k in ("home", "draw", "away")) - 1) < .0002)


def experimental_xg_probabilities(home, away):
    """Fixed v1 baseline: average own historical xGF/opponent historical xGA.

    Independent Poisson 24-goal truncated mass, normalized. Rates are clamped
    to [.05, 8] for numerical protection only, not fitted from outcomes.
    No home edge, no league-specific calibration or odds. The evaluation
    determines whether this model improves on actual-goal proxy.
    """
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise ValueError("Both genuine historical xG summaries required")
    values = [home.get("mean_xg_for"), home.get("mean_xg_against"),
              away.get("mean_xg_for"), away.get("mean_xg_against")]
    samples = [home.get("sample_size"), away.get("sample_size")]
    if (not all(type(s) is int and 3 <= s <= 5 for s in samples)
            or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 20
                       for v in values)):
        raise ValueError("Invalid or incomplete historical PitchAPI xG values")
    lh = max(.05, min(8., (values[0] + values[3]) / 2))
    la = max(.05, min(8., (values[2] + values[1]) / 2))
    def poisson(lam, k):
        return math.exp(-lam + k * math.log(lam) - math.lgamma(k+1))
    h = [poisson(lh, k) for k in range(24)]
    a = [poisson(la, k) for k in range(24)]
    mass = sum(h) * sum(a)
    if not .999 < mass <= 1.0000001:
        raise ValueError("Insufficient Poisson grid coverage")
    ph = sum(h[i] * a[j] for i in range(24) for j in range(i))
    pd = sum(h[i] * a[i] for i in range(24))
    pa = sum(h[i] * a[j] for i in range(24) for j in range(i+1,24))
    total = ph + pd + pa
    out = {"home": round(ph / total, 5), "draw": round(pd / total, 5),
           "away": round(pa / total, 5)}
    # Explicit remainder ensures 1X2 adds to one after rounding.
    out["away"] = round(1 - out["home"] - out["draw"], 5)
    lam = lh + la
    out["over_2_5"] = round(1 - math.exp(-lam) * (1 + lam + .5*lam*lam), 5)
    if not _valid(out):
        raise ValueError("Invalid experimental xG forecast")
    return out, {"home": round(lh, 5), "away": round(la, 5)}


def freeze_pair(day, form_manifest, form, goals, xg_manifest, xg_day,
                *, now):
    """One forward-only paired run. Original goals probabilities are copied,
    not recomputed. Pairs cannot exist without earlier full source evidence.
    """
    now = _clock(now)
    generated = _iso_datetime(form_manifest.get("generated_at_utc"))
    xg_generated = _iso_datetime(xg_manifest.get("generated_at_utc"))
    original_time = _iso_datetime(goals.get("created_from_source_run_utc"))
    if (form_manifest.get("schema") != FORM_SCHEMA
            or form_manifest.get("source") != "API-Football"
            or form_manifest.get("safe_to_publish_play") is not False
            or form_manifest.get("scoring_fields_filled_automatically") != 0
            or form_manifest.get("register_writes") is not False
            or goals.get("schema") != GOALS_SCHEMA
            or goals.get("date") != day
            or goals.get("provider") != "API-Football"
            or goals.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
            or goals.get("isolated_from_original_kb21") is not True
            or goals.get("register_writes") is not False
            or goals.get("kb21_n_effect") != 0
            or xg_manifest.get("schema") != XG_BRIDGE_SCHEMA
            or xg_manifest.get("authoritative_fixture_calendar") != "API-Football"
            or xg_manifest.get("external_api_calls") != 0
            or xg_manifest.get("register_writes") is not False
            or xg_manifest.get("safe_to_publish_play") is not False
            or xg_manifest.get("automatic_p_model_count") != 0
            or day not in xg_manifest.get("dates", [])
            or form.get("day") != day or xg_day.get("date") != day
            or not isinstance(form.get("matches"), list)
            or not isinstance(goals.get("predictions"), list)
            or not isinstance(xg_day.get("records"), list)
            or any(x is None for x in (generated, xg_generated, original_time))
            or generated != original_time or not generated <= xg_generated <= now):
        raise ValueError("Paired xG run requires consistent real premarket source chain")
    source = {}
    for match in form["matches"]:
        fid = match.get("fixture_id") if isinstance(match, dict) else None
        if (type(fid) is not int or fid <= 0 or fid in source
                or match.get("odds") is not None or match.get("selection") is not None
                or match.get("safe_to_publish_play") is not False
                or match.get("analyst_assessment",{}).get("P_model_pre_odds") is not None):
            raise ValueError("Invalid goal form or duplicated fixture")
        source[fid] = match
    goal_by_id = {}
    for item in goals["predictions"]:
        fid = item.get("fixture_id") if isinstance(item, dict) else None
        if (type(fid) is not int or fid <= 0 or fid in goal_by_id
                or item.get("model_id") != BASELINE
                or item.get("forecast_run_started_utc") != goals["created_from_source_run_utc"]
                or item.get("odds") is not None or item.get("selection") is not None
                or item.get("original_kb21_p_model") is not None
                or item.get("calibrated") is not False):
            raise ValueError("Polluted or duplicated original goals shadow")
        goal_by_id[fid] = item
    if set(goal_by_id) != set(source):
        raise ValueError("Goal shadow fixture IDs differ from form")
    results, seen = [], set()
    for item in xg_day["records"]:
        fid = item.get("fixture_id") if isinstance(item, dict) else None
        match = source.get(fid)
        if type(fid) is not int or fid <= 0 or fid in seen:
            raise ValueError("Duplicated or invalid xG fixture ID")
        seen.add(fid)
        if match is None:
            continue  # Canonical calendar can contain un-enriched fixtures.
        shadow = goal_by_id[fid]
        if (item.get("fixture") != match["event"]
                or item.get("kickoff_utc") != match["kickoff_utc"]
                or shadow.get("event") != match["event"]
                or shadow.get("kickoff_utc") != match["kickoff_utc"]
                or item.get("original_kb21_p_model") is not None
                or item.get("odds") is not None or item.get("safe_to_publish_play") is not False):
            raise ValueError("Cross-run fixture mismatch or market contamination")
        if item.get("status") != "VERIFIED_PREMATCH_HISTORICAL_XG":
            continue
        kickoff = _iso_datetime(item["kickoff_utc"])
        pitch_time = _iso_datetime(item.get("snapshot_utc"))
        if not kickoff or not pitch_time or pitch_time >= kickoff or now >= kickoff:
            continue  # NEVER create a second forecast after kickoff.
        prior = shadow.get("probabilities_1x2_over25")
        if not _valid(prior):
            continue  # Fair comparison requires a real stored goals baseline.
        probs, rates = experimental_xg_probabilities(item.get("home_xg"), item.get("away_xg"))
        results.append({
            "fixture_id": fid, "event": match["event"],
            "kickoff_utc": match["kickoff_utc"],
            "league": match["league"], "pitch_match_id": item.get("pitch_match_id"),
            "pitch_snapshot_utc": pitch_time.isoformat(),
            "goal_shadow_freeze_utc": original_time.isoformat(),
            "pair_freeze_utc": now.isoformat(),
            "baseline_model_id": BASELINE, "experimental_model_id": MODEL,
            "goals_baseline_probabilities": dict(prior),
            "xg_shadow_probabilities": probs,
            "estimated_xg_goal_rates": rates,
            "xg_sample_sizes": {
                "home": item["home_xg"]["sample_size"],
                "away": item["away_xg"]["sample_size"]},
            "historical_xg_not_future_fixture_xg": True,
            "model_calibrated": False, "original_kb21_p_model": None,
            "odds": None, "selection": None, "ev": None, "match_result": None,
            "safe_to_publish_play": False,
        })
    if len(seen) != len(xg_day["records"]):
        raise ValueError("XG source record collision")
    return {
        "schema": SCHEMA, "date": day, "created_at_utc": now.isoformat(),
        "source": "API-Football calendar + archived PitchAPI historical xG",
        "baseline_model": BASELINE, "xg_model": MODEL,
        "method": "Independent Poisson using average own historical xGF/opponent historical xGA; 3-5 genuine earlier matches per team",
        "calibrated": False, "publication": "RESEARCH_ONLY_NOT_PLAY",
        "paired_count": len(results), "pairs": results,
        "original_kb21_p_model": None,
        "register_writes": False, "kb21_n_effect": 0,
        "safe_to_publish_play": False,
    }


def render(day):
    lines = ["# KB21 / prognozy cienia: gole vs historyczne xG / "+day["date"],
             "", "**WYŁĄCZNIE EKSPERYMENT. NIE SĄ TO TYPY ANI ORYGINALNE P(model).**",
             f"Przed startem zamrożono {day['paired_count']} par prognoz.", "",
             "| Mecz | Model goli 1/X/2 | Model xG 1/X/2 | Over2.5: gole/xG |",
             "|---|---:|---:|---:|"]
    for r in day["pairs"]:
        h, x = r["goals_baseline_probabilities"], r["xg_shadow_probabilities"]
        fmt=lambda v: "/".join(f"{100*v[k]:.1f}%" for k in ("home","draw","away"))
        lines.append(f"| {r['event']} | {fmt(h)} | {fmt(x)} | "
                     f"{100*h['over_2_5']:.1f}% / {100*x['over_2_5']:.1f}% |")
    if not day["pairs"]:
        lines.append("| Brak porównywalnych prognoz zapisanych przed meczem | — | — | — |")
    lines.extend(["", "Wnioski o skuteczności dopiero po rozliczeniu identycznych "
                  "spotkań rzeczywistym wynikiem. Model xG nie ma jeszcze kalibracji.",
                  "Brak danych nie jest zerem i nie staje się automatycznym PLAY.", ""])
    return "\n".join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-dir",required=True)
    parser.add_argument("--output-dir",required=True)
    args=parser.parse_args()
    root=Path(args.source_dir)
    form_manifest=json.loads((root/"KB21_FORM_MANIFEST.json").read_text())
    xg_manifest=json.loads((root/"KB21_PREODDS_XG_MANIFEST.json").read_text())
    output=Path(args.output_dir)
    output.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc)
    total=0
    for day in form_manifest["dates"]:
        form=json.loads((root/("KB21_FORM_"+day+".json")).read_text())
        goals=json.loads((root/("KB21_SHADOW_"+day+".json")).read_text())
        bridge=json.loads((root/("KB21_PREODDS_XG_"+day+".json")).read_text())
        doc=freeze_pair(day,form_manifest,form,goals,xg_manifest,bridge,now=now)
        total+=doc["paired_count"]
        (output/("KB21_XG_V_GOALS_SHADOW_"+day+".json")).write_text(
            json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (output/("KB21_XG_V_GOALS_SHADOW_"+day+".md")).write_text(render(doc),encoding="utf-8")
    print("KB21 paired prospective xG vs original-goals-shadow:",total,
          "frozen pairs across 2 days; no odds, no CORE P(model), no PLAY")


if __name__=="__main__":
    main()
