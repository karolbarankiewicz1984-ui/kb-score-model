"""Strict forward-only settlement of *experimental* KB21 shadow probabilities.

Inputs are immutable GitHub Actions archive contents saved before kickoff.
Scores are fetched only after the match and joined on original provider ID.
This NEVER settles original KB Score, makes a betting recommendation, or
writes KB/DEV N. Returns diagnostic 1X2 multiclass Brier and O2.5 Brier.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import math
import os

from tools.api_market_http import ApiClient
from tools.kb21_single_source_calendar import (
    BASE, DAY_SCHEMA, SCHEMA as CALENDAR_SCHEMA, WARSAW, _iso_datetime, _page
)

SHADOW_SCHEMA = "kb21-api-shadow-forecast-snapshot-v1"
AUDIT_SCHEMA = "kb21-shadow-forward-settlement-v1"
FORECAST_KEYS = {"home", "draw", "away", "over_2_5"}


def previous_warsaw_day(now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Need timezone-aware time")
    return (now.astimezone(WARSAW).date() - timedelta(days=1)).isoformat()


def _valid_probability(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 1)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_archives(root, date):
    """Read provider-bound forecast artifacts; earliest valid freeze wins."""
    candidates = []
    for path in sorted(Path(root).glob("*/KB21_SHADOW_" + date + ".json")):
        folder = path.parent
        required = ["SINGLE_SOURCE_MANIFEST.json",
                    "KB21_API_CALENDAR_" + date + ".json",
                    "KB21_FORM_MANIFEST.json"]
        if not all((folder / x).is_file() for x in required):
            raise ValueError("Incomplete or tampered source artifact: " + folder.name)
        calendar_manifest = _load(folder / required[0])
        calendar = _load(folder / required[1])
        form_manifest = _load(folder / required[2])
        snap = _load(path)
        if (calendar_manifest.get("schema") != CALENDAR_SCHEMA
                or calendar_manifest.get("provider_count") != 1
                or calendar_manifest.get("authoritative_calendar_provider") != "API-Football"
                or calendar_manifest.get("single_source_gate") != "PASS_SOURCE"
                or calendar_manifest.get("safe_to_publish_play") is not False
                or date not in calendar_manifest.get("dates", [])
                or calendar.get("schema") != DAY_SCHEMA
                or calendar.get("date") != date
                or calendar.get("source") != "API-Football"
                or calendar.get("single_source_gate") != "PASS_SOURCE"
                or calendar.get("safe_to_publish_play") is not False
                or form_manifest.get("source") != "API-Football"
                or form_manifest.get("dates") != calendar_manifest["dates"]
                or form_manifest.get("scoring_fields_filled_automatically") != 0
                or form_manifest.get("safe_to_publish_play") is not False
                or snap.get("schema") != SHADOW_SCHEMA
                or snap.get("date") != date
                or snap.get("provider") != "API-Football"
                or snap.get("isolated_from_original_kb21") is not True
                or snap.get("no_postmatch_prediction_regeneration") is not True
                or snap.get("register_writes") is not False
                or snap.get("kb21_n_effect") != 0
                or snap.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
                or not isinstance(snap.get("predictions"), list)):
            raise ValueError("Invalid KB21 shadow source chain: " + folder.name)
        created = _iso_datetime(snap.get("created_from_source_run_utc"))
        manifest_time = _iso_datetime(calendar_manifest.get("generated_at_utc"))
        source_time = _iso_datetime(calendar.get("snapshot_utc"))
        form_time = _iso_datetime(form_manifest.get("generated_at_utc"))
        if (created is None or manifest_time is None or source_time is None
                or form_time is None or created != form_time
                or manifest_time > source_time or source_time > created):
            raise ValueError("Inconsistent forecast timestamps")
        source = {}
        for event in calendar.get("candidates", []):
            ident = event.get("fixture_id") if isinstance(event, dict) else None
            if (not isinstance(ident, int) or isinstance(ident, bool)
                    or ident in source):
                raise ValueError("Duplicate source calendar candidate")
            source[ident] = event
        seen = set()
        for prediction in snap["predictions"]:
            ident = prediction.get("fixture_id") if isinstance(prediction, dict) else None
            event = source.get(ident)
            kickoff = _iso_datetime(prediction.get("kickoff_utc")) if isinstance(prediction, dict) else None
            if (not isinstance(ident, int) or isinstance(ident, bool)
                    or ident in seen or event is None or kickoff is None
                    or event.get("kickoff_utc") != prediction["kickoff_utc"]
                    or event.get("home") + " – " + event.get("away") != prediction.get("event")
                    or kickoff.astimezone(WARSAW).date().isoformat() != date
                    or event.get("status") != "NS"
                    or prediction.get("forecast_run_started_utc") != snap["created_from_source_run_utc"]
                    or prediction.get("model_id") != "kb21-api-last10-goals-shadow-v1"
                    or prediction.get("original_kb21_p_model") is not None
                    or prediction.get("selection") is not None
                    or prediction.get("odds") is not None
                    or prediction.get("ev") is not None
                    or prediction.get("match_result") is not None
                    or prediction.get("calibrated") is not False
                    or prediction.get("register_writes") is not False
                    or prediction.get("safe_to_publish_play") is not False):
                raise ValueError("Invalid or polluted source forecast")
            seen.add(ident)
            if created >= kickoff:
                raise ValueError("A purported forecast was captured at/after kickoff")
            probs = prediction.get("probabilities_1x2_over25")
            if probs is None:
                continue  # Explicitly no prediction; do not construct one later.
            if (not isinstance(probs, dict) or set(probs) != FORECAST_KEYS
                    or not all(_valid_probability(v) for v in probs.values())
                    or abs(sum(probs[k] for k in ("home", "draw", "away")) - 1) > .0002):
                raise ValueError("Invalid shadow probabilities")
            candidates.append({
                "fixture_id": ident, "event": prediction["event"],
                "kickoff_utc": prediction["kickoff_utc"],
                "freeze_utc": created.isoformat(), "probabilities": probs,
                "archive_run": folder.name,
                "snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    first = {}
    for forecast in sorted(candidates, key=lambda p: (p["freeze_utc"], p["archive_run"])):
        first.setdefault(forecast["fixture_id"], forecast)
    return list(sorted(first.values(), key=lambda x: (x["kickoff_utc"], x["fixture_id"]))), len(candidates)


def settle(target, forecasts, provider, now=None, source_snapshots=0):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Audit clock needs explicit timezone")
    now = now.astimezone(timezone.utc)
    if now.astimezone(WARSAW).date().isoformat() <= target:
        raise ValueError("Do not settle while target Warsaw day is still running")
    rows, pages = _page(provider, target, 1)
    if pages != 1:
        raise ValueError("Incomplete provider results response")
    actual = {}
    for event in rows:
        if not isinstance(event, dict) or not isinstance(event.get("fixture"), dict):
            raise ValueError("Malformed result event")
        fid = event["fixture"].get("id")
        if not isinstance(fid, int) or isinstance(fid, bool) or fid in actual:
            raise ValueError("Invalid result ID or duplicate")
        actual[fid] = event
    results = []
    seen = set()
    for prediction in forecasts:
        fid = prediction["fixture_id"]
        if fid in seen:
            raise ValueError("Duplicate prediction in audit")
        seen.add(fid)
        kickoff = _iso_datetime(prediction["kickoff_utc"])
        freeze = _iso_datetime(prediction["freeze_utc"])
        if kickoff is None or freeze is None or freeze >= kickoff:
            raise ValueError("Retrospective forecast is forbidden")
        p = prediction["probabilities"]
        if (set(p) != FORECAST_KEYS or not all(_valid_probability(x) for x in p.values())
                or abs(p["home"]+p["draw"]+p["away"]-1) > .0002):
            raise ValueError("Invalid forecast probabilities")
        row = {**prediction, "status": "UNRESOLVED",
               "final_score": None, "realized_1x2": None, "realized_over_2_5": None,
               "brier_1x2": None, "brier_over_2_5": None,
               "top_pick_correct": None}
        match = actual.get(fid)
        if match is None:
            row["status"] = "MISSING_FROM_RESULT_SOURCE"
        else:
            f = match["fixture"]
            current_kickoff = _iso_datetime(f.get("date"))
            if (current_kickoff is None
                    or abs((current_kickoff-kickoff).total_seconds()) > 300):
                row["status"] = "KICKOFF_CHANGED_NOT_SETTLED"
            elif (f.get("status") or {}).get("short") != "FT":
                row["status"] = "NOT_STANDARD_FULL_TIME"
            else:
                goals = match.get("goals") or {}
                score = (match.get("score") or {}).get("fulltime") or {}
                h, a = goals.get("home"), goals.get("away")
                sh, sa = score.get("home"), score.get("away")
                if (not all(isinstance(x, int) and not isinstance(x, bool)
                            and x >= 0 for x in (h, a, sh, sa))
                        or (h, a) != (sh, sa)):
                    row["status"] = "INCOMPLETE_OR_CONFLICTING_SCORE"
                else:
                    outcome = "home" if h > a else "away" if a > h else "draw"
                    over = int(h + a >= 3)
                    brier = sum((p[k] - int(k == outcome))**2
                                for k in ("home", "draw", "away"))
                    top = max(("home", "draw", "away"), key=lambda k: p[k])
                    row.update(status="SETTLED_FT", final_score=[h, a],
                               realized_1x2=outcome, realized_over_2_5=over,
                               brier_1x2=round(brier, 6),
                               brier_over_2_5=round((p["over_2_5"]-over)**2, 6),
                               top_pick_correct=(top == outcome))
        results.append(row)
    finished = [r for r in results if r["status"] == "SETTLED_FT"]
    n = len(finished)
    return {
        "schema": AUDIT_SCHEMA, "date": target, "audited_at_utc": now.isoformat(),
        "source": "API-Football result fixtures (same provider IDs)",
        "model": "kb21-api-last10-goals-shadow-v1",
        "publication": "RESEARCH_ONLY_NOT_PLAY",
        "archives_considered_predictions": source_snapshots,
        "unique_pregame_predictions": len(results), "distinct_settled_matches": n,
        "unresolved_matches": len(results)-n,
        "top_1x2_correct": sum(bool(r["top_pick_correct"]) for r in finished),
        "top_1x2_accuracy": round(sum(bool(r["top_pick_correct"]) for r in finished)/n, 4) if n else None,
        "mean_multiclass_brier_1x2": round(sum(r["brier_1x2"] for r in finished)/n, 6) if n else None,
        "mean_brier_over_2_5": round(sum(r["brier_over_2_5"] for r in finished)/n, 6) if n else None,
        "results": results, "old_kb21_n_effect": 0,
        "register_writes": False, "safe_to_publish_play": False,
        "note": "Strict pre-match shadow ONLY; one independent fixture counts once. "
                "Two markets on the same fixture are correlated. No betting claims.",
    }


def render(report):
    n = report["distinct_settled_matches"]
    lines = [
        "# KB21 — audyt prognoz eksperymentalnych — " + report["date"], "",
        "**BADANIE / NO PLAY. Nie jest to rozliczenie historycznego KB Score 2.1.**",
        "Prognozy pobrano WYŁĄCZNIE z wcześniejszych artefaktów GitHub Actions; "
        "wyniku nie wolno wykorzystać do ponownego obliczenia prognozy.", "",
        f"Prognoz przedmeczowych (unikalne ID): {report['unique_pregame_predictions']}.",
        f"Rozliczonych zakończonych meczów FT: {n}; pozostałe: {report['unresolved_matches']}.",
        ("Trafność najmocniejszego kierunku 1/X/2: "
         + (f"{100*report['top_1x2_accuracy']:.1f}%" if n else "BRAK PRÓBY")),
        ("Brier 1/X/2 (suma błędów 3 kategorii): "
         + (f"{report['mean_multiclass_brier_1x2']:.4f}" if n else "BRAK PRÓBY")),
        ("Brier over 2,5: "
         + (f"{report['mean_brier_over_2_5']:.4f}" if n else "BRAK PRÓBY")),
        "", "| Mecz | Wynik | Status | Prognoza 1/X/2 | Over 2,5 |",
        "|---|---|---|---|---|",
    ]
    for r in report["results"]:
        p = r["probabilities"]
        lines.append(f"| {r['event']} | "
                     f"{str(r['final_score']) if r['final_score'] is not None else '—'} | "
                     f"{r['status']} | "
                     f"{100*p['home']:.1f}/{100*p['draw']:.1f}/{100*p['away']:.1f}% | "
                     f"{100*p['over_2_5']:.1f}% |")
    if not report["results"]:
        lines.append("| Brak zachowanych prognoz sprzed spotkań dla tej daty | — | — | — | — |")
    lines.extend(["", "Mała próba nie wystarcza do kalibracji ani oceny opłacalności. "
                  "Brier mierzy jakość prawdopodobieństw, nie kursów. "
                  "Wyniki 1/X/2 i over 2,5 z tego samego meczu są skorelowane.",
                  "Zabronione dopisywanie wyników do historycznego N lub automatyczne PLAY.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", required=True)
    parser.add_argument("--date")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    target = args.date or previous_warsaw_day(now)
    if target != previous_warsaw_day(now):
        raise SystemExit("Daily audit restricted to yesterday, no retroactive re-prediction")
    forecasts, count = load_archives(args.archives, target)
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Missing API_FOOTBALL_KEY: cannot confirm real results")
    payload, _ = ApiClient().get(
        BASE, key, "fixtures", date=target, timezone="Europe/Warsaw")
    report = settle(target, forecasts, payload, now=now, source_snapshots=count)
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / ("KB21_SHADOW_AUDIT_"+target+".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (dest / ("KB21_SHADOW_AUDIT_"+target+".md")).write_text(
        render(report), encoding="utf-8")
    print("KB21 shadow audit:", target, "pregame:", len(forecasts),
          "settled:", report["distinct_settled_matches"], "PLAY: NO")


if __name__ == "__main__":
    main()
