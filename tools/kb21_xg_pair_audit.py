"""Forward-only paired xG-vs-goals diagnostics for identical football fixtures.

Read genuine earlier GitHub artifacts, never recompute forecasts from results.
A single match counts once. Comparison uses paired multiclass 1X2 Brier,
binary over-2.5 Brier and top-direction hit rate, with no ROI/bet claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from tools.api_market_http import ApiClient
from tools.kb21_single_source_calendar import BASE, _iso_datetime, WARSAW, DAY_SCHEMA, SCHEMA as CALENDAR_SCHEMA
from tools.kb21_shadow_audit import settle, previous_warsaw_day
from tools.kb21_xg_pair_shadow import SCHEMA as PAIR_SCHEMA, MODEL, BASELINE, _valid

AUDIT_SCHEMA = "kb21-xg-vs-goals-prospective-comparison-v1"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_pairs(root, day):
    pairs, sources = [], 0
    for path in sorted(Path(root).glob("*/KB21_XG_V_GOALS_SHADOW_"+day+".json")):
        folder = path.parent
        names = ("SINGLE_SOURCE_MANIFEST.json",
                 "KB21_API_CALENDAR_"+day+".json",
                 "KB21_FORM_MANIFEST.json",
                 "KB21_SHADOW_"+day+".json",
                 "KB21_PREODDS_XG_MANIFEST.json",
                 "KB21_PREODDS_XG_"+day+".json")
        if not all((folder/name).is_file() for name in names):
            raise ValueError("Missing original pregame source chain")
        src, calendar, form, original, xgm, xgd = [_load(folder/x) for x in names]
        doc = _load(path)
        if (src.get("schema") != CALENDAR_SCHEMA or src.get("provider_count") != 1
                or src.get("authoritative_calendar_provider") != "API-Football"
                or src.get("single_source_gate") != "PASS_SOURCE"
                or src.get("safe_to_publish_play") is not False
                or day not in src.get("dates", [])
                or calendar.get("schema") != DAY_SCHEMA
                or calendar.get("date") != day
                or calendar.get("source") != "API-Football"
                or calendar.get("single_source_gate") != "PASS_SOURCE"
                or calendar.get("safe_to_publish_play") is not False
                or form.get("source") != "API-Football"
                or form.get("dates") != src.get("dates")
                or form.get("scoring_fields_filled_automatically") != 0
                or original.get("schema") != "kb21-api-shadow-forecast-snapshot-v1"
                or original.get("date") != day
                or original.get("isolated_from_original_kb21") is not True
                or original.get("register_writes") is not False
                or xgm.get("schema") != "kb21-preodds-pitchapi-xg-bridge-v1"
                or xgm.get("calendar_candidates") != src.get("total_research_candidates")
                or xgm.get("register_writes") is not False
                or xgm.get("external_api_calls") != 0
                or xgd.get("date") != day
                or doc.get("schema") != PAIR_SCHEMA
                or doc.get("date") != day
                or doc.get("baseline_model") != BASELINE
                or doc.get("xg_model") != MODEL
                or doc.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
                or doc.get("register_writes") is not False
                or doc.get("kb21_n_effect") != 0
                or doc.get("safe_to_publish_play") is not False
                or not isinstance(doc.get("pairs"), list)
                or doc.get("paired_count") != len(doc["pairs"])):
            raise ValueError("Invalid paired source chain")
        freeze = _iso_datetime(doc.get("created_at_utc"))
        caltime = _iso_datetime(calendar.get("snapshot_utc"))
        formtime = _iso_datetime(form.get("generated_at_utc"))
        goalstime = _iso_datetime(original.get("created_from_source_run_utc"))
        xgtime = _iso_datetime(xgm.get("generated_at_utc"))
        if (any(x is None for x in (freeze,caltime,formtime,goalstime,xgtime))
                or not caltime <= formtime == goalstime <= xgtime <= freeze):
            raise ValueError("Inconsistent premarket freeze chronology")
        candidates={}
        for m in calendar.get("candidates",[]):
            ident=m.get("fixture_id") if isinstance(m,dict) else None
            if type(ident) is not int or ident in candidates:
                raise ValueError("Duplicate calendar ID")
            candidates[ident]=m
        old={}
        for m in original.get("predictions",[]):
            ident=m.get("fixture_id") if isinstance(m,dict) else None
            if type(ident) is not int or ident in old:
                raise ValueError("Duplicate baseline ID")
            old[ident]=m
        xr={}
        for m in xgd.get("records",[]):
            ident=m.get("fixture_id") if isinstance(m,dict) else None
            if type(ident) is not int or ident in xr:
                raise ValueError("Duplicate xG source ID")
            xr[ident]=m
        seen=set()
        for p in doc["pairs"]:
            ident=p.get("fixture_id") if isinstance(p,dict) else None
            event=candidates.get(ident)
            older=old.get(ident)
            xgrow=xr.get(ident)
            kickoff=_iso_datetime(p.get("kickoff_utc")) if isinstance(p,dict) else None
            base_time=_iso_datetime(p.get("goal_shadow_freeze_utc")) if isinstance(p,dict) else None
            pitch_time=_iso_datetime(p.get("pitch_snapshot_utc")) if isinstance(p,dict) else None
            pair_time=_iso_datetime(p.get("pair_freeze_utc")) if isinstance(p,dict) else None
            if (type(ident) is not int or ident in seen or event is None or older is None
                    or xgrow is None or kickoff is None or base_time is None
                    or pitch_time is None or pair_time is None
                    or not base_time == goalstime or not pair_time == freeze
                    or pitch_time > pair_time or not pair_time < kickoff
                    or p.get("kickoff_utc") != event.get("kickoff_utc")
                    or p.get("event") != event.get("home")+" – "+event.get("away")
                    or p.get("event") != older.get("event")
                    or p.get("league") != event.get("league")
                    or p.get("baseline_model_id") != BASELINE
                    or p.get("experimental_model_id") != MODEL
                    or older.get("model_id") != BASELINE
                    or older.get("forecast_run_started_utc") != original["created_from_source_run_utc"]
                    or p.get("goals_baseline_probabilities") != older.get("probabilities_1x2_over25")
                    or not _valid(p.get("goals_baseline_probabilities"))
                    or not _valid(p.get("xg_shadow_probabilities"))
                    or xgrow.get("status") != "VERIFIED_PREMATCH_HISTORICAL_XG"
                    or p.get("pitch_match_id") != xgrow.get("pitch_match_id")
                    or p.get("pitch_snapshot_utc") != xgrow.get("snapshot_utc")
                    or p.get("xg_sample_sizes") != {
                        side: xgrow[side+"_xg"]["sample_size"] for side in ("home","away")}
                    or p.get("original_kb21_p_model") is not None
                    or p.get("model_calibrated") is not False
                    or any(p.get(k) is not None for k in ("odds","selection","ev","match_result"))
                    or p.get("safe_to_publish_play") is not False):
                raise ValueError("Rejected noncanonical or retroactive paired forecast")
            seen.add(ident)
            pairs.append({
                "fixture_id":ident,"event":p["event"],"kickoff_utc":p["kickoff_utc"],
                "freeze_utc":pair_time.isoformat(),
                "goals_probs":p["goals_baseline_probabilities"],
                "xg_probs":p["xg_shadow_probabilities"],
                "archive_run":folder.name,
                "pair_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            })
        sources+=1
    first={}
    for p in sorted(pairs,key=lambda x:(x["freeze_utc"],x["archive_run"])):
        first.setdefault(p["fixture_id"],p)
    return sorted(first.values(),key=lambda x:(x["kickoff_utc"],x["fixture_id"])),sources


def compare(day, pairs, results_feed, now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware comparison clock required")
    goal_rows=[dict(fixture_id=x["fixture_id"],event=x["event"],
                    kickoff_utc=x["kickoff_utc"],freeze_utc=x["freeze_utc"],
                    probabilities=x["goals_probs"]) for x in pairs]
    xg_rows=[dict(fixture_id=x["fixture_id"],event=x["event"],
                  kickoff_utc=x["kickoff_utc"],freeze_utc=x["freeze_utc"],
                  probabilities=x["xg_probs"]) for x in pairs]
    # Reuse canonical API-Football FT validation. The same result feed and
    # SAME fixture subset are used for both strategies.
    goals=settle(day,goal_rows,results_feed,now=now)
    xg=settle(day,xg_rows,results_feed,now=now)
    rows=[]
    for pair,g,x in zip(pairs,goals["results"],xg["results"]):
        if (g["fixture_id"]!=x["fixture_id"] or
                g["status"]!=x["status"] or g["final_score"]!=x["final_score"]):
            raise ValueError("Paired settlement diverged")
        rows.append({
            "fixture_id":pair["fixture_id"],"fixture":pair["event"],
            "archive_run":pair["archive_run"],
            "paired_forecast_frozen_utc":pair["freeze_utc"],
            "status":g["status"],"full_time_goals":g["final_score"],
            "goals_baseline_brier_1x2":g["brier_1x2"],
            "xg_shadow_brier_1x2":x["brier_1x2"],
            "goals_baseline_brier_over25":g["brier_over_2_5"],
            "xg_shadow_brier_over25":x["brier_over_2_5"],
            "goals_baseline_top_correct":g["top_pick_correct"],
            "xg_shadow_top_correct":x["top_pick_correct"],
        })
    finished=[r for r in rows if r["status"]=="SETTLED_FT"]
    n=len(finished)
    def average(key):
        return round(sum(r[key] for r in finished)/n,6) if n else None
    summary={
        "mean_1x2_brier_goals":average("goals_baseline_brier_1x2"),
        "mean_1x2_brier_xg":average("xg_shadow_brier_1x2"),
        "mean_over25_brier_goals":average("goals_baseline_brier_over25"),
        "mean_over25_brier_xg":average("xg_shadow_brier_over25"),
        "top_1x2_correct_goals":sum(bool(r["goals_baseline_top_correct"]) for r in finished),
        "top_1x2_correct_xg":sum(bool(r["xg_shadow_top_correct"]) for r in finished),
    }
    summary["brier_1x2_xg_minus_goals"]=round(
        summary["mean_1x2_brier_xg"]-summary["mean_1x2_brier_goals"],6) if n else None
    summary["brier_over25_xg_minus_goals"]=round(
        summary["mean_over25_brier_xg"]-summary["mean_over25_brier_goals"],6) if n else None
    return {
        "schema":AUDIT_SCHEMA,"date":day,"audited_at_utc":now.isoformat(),
        "publication":"RESEARCH_ONLY_NOT_PLAY",
        "paired_pregame_forecasts":len(pairs),"distinct_settled_FT_matches":n,
        "unresolved":len(pairs)-n,
        "summary":summary,"rows":rows,
        "original_kb21_n_effect":0,"register_writes":False,
        "safe_to_publish_play":False,
        "note":"Negative xG-minus-goals Brier is better on identical matches, not proof of "
               "persistent gain. At least tens/hundreds of independent future matches "
               "are needed; no odds, profit or ROI computed.",
    }


def render(report):
    s=report["summary"]
    def show(k):
        return "BRAK ROZLICZONYCH MECZÓW" if s[k] is None else str(s[k])
    out=["# KB21 — prospektywny audyt: xG kontra gole — "+report["date"],"",
         "**BADANIE, NIE TYP. Porównanie tych samych meczów FT, które miały OBIE prognozy przed startem.**",
         f"Par przedmeczowych: {report['paired_pregame_forecasts']}; "
         f"unikalnych rozliczonych: {report['distinct_settled_FT_matches']}; "
         f"nierozstrzygniętych: {report['unresolved']}.","",
         f"Brier 1/X/2 — GOLE: {show('mean_1x2_brier_goals')} / xG: {show('mean_1x2_brier_xg')}",
         f"Brier over 2,5 — GOLE: {show('mean_over25_brier_goals')} / xG: {show('mean_over25_brier_xg')}",
         f"Różnica xG minus gole (ujemna=lepsza): "
         f"1/X/2 {show('brier_1x2_xg_minus_goals')}, "
         f"over2,5 {show('brier_over25_xg_minus_goals')}", "",
         "| Mecz | FT | Brier 1/X/2 gole | Brier 1/X/2 xG | Status |",
         "|---|---|---:|---:|---|"]
    for row in report["rows"]:
        out.append(f"| {row['fixture']} | {row['full_time_goals'] or '—'} | "
                   f"{row['goals_baseline_brier_1x2'] if row['goals_baseline_brier_1x2'] is not None else '—'} | "
                   f"{row['xg_shadow_brier_1x2'] if row['xg_shadow_brier_1x2'] is not None else '—'} | "
                   f"{row['status']} |")
    if not report["rows"]:
        out.append("| Brak par prognoz przedmeczowych w archiwach | — | — | — | — |")
    out.extend(["", "Brak wyników lub bardzo mała próba nie pozwala oceniać wyższości "
                 "modelu ani rentowności zakładów. Stary KB Score i N bez zmian.",""])
    return "\n".join(out)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archives",required=True)
    p.add_argument("--output-dir",required=True)
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    target=previous_warsaw_day(now)
    pairs,count=load_pairs(args.archives,target)
    key=os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Missing API_FOOTBALL_KEY")
    payload,_=ApiClient().get(BASE,key,"fixtures",date=target,timezone="Europe/Warsaw")
    report=compare(target,pairs,payload,now=now)
    report["pregame_run_archives_with_comparison"]=count
    output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
    (output/("KB21_XG_V_GOALS_AUDIT_"+target+".json")).write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/("KB21_XG_V_GOALS_AUDIT_"+target+".md")).write_text(
        render(report),encoding="utf-8")
    print("KB21 paired audit:",target,"stored pairs",len(pairs),
          "settled FT",report["distinct_settled_FT_matches"],
          "model winner NOT certified, no PLAY")


if __name__=="__main__":
    main()
