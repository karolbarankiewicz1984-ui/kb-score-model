"""Uniform readable A/B/C research shortlist from frozen original forecasts.

Output JSON is unchanged and retains every qualifying candidate.
PDF is an overview, not a bookmaker ticket or a claim of calibrated accuracy.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from github_models.abc_filter import evaluate
from github_models.abc_pdf_style import p, render, styles, table

LABELS = {"1X2": "Wynik 1X2", "goals": "Bramki",
          "fouls": "Faule", "cards": "Żółte kartki",
          "corners": "Rożne"}
MARKET_ORDER = ("1X2", "goals", "fouls", "cards", "corners")
THRESHOLDS = {"A": 70, "B": 75, "C": 80}
# A compact, reproducible cross-market sample, not the full candidate pool.
PER_MARKET = 3

def label_market(row):
    market = row["market"]
    if market == "1X2":
        return "Wynik meczu: " + {"1": "1 (gospodarze)", "X": "X (remis)",
                                 "2": "2 (goście)"}.get(row["selection"], str(row["selection"]))
    if market not in LABELS:
        return str(market) + " " + str(row.get("line", "")) + " " + str(row["selection"])
    direction = {"over": "Powyżej", "under": "Poniżej"}[row["selection"]]
    return LABELS[market] + ": " + direction + " " + str(row["line"]).replace(".", ",")

def kick_off(fixture):
    raw = fixture.get("kickoff_utc")
    if not raw:
        return "brak danych"
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return "niezweryfik."
        return stamp.astimezone(ZoneInfo("Europe/Warsaw")).strftime("%d.%m %H:%M")
    except (ValueError, TypeError, OverflowError):
        return "niezweryfik."

def probability(row):
    return row.get("probability_min", row.get("probability"))

def select_overview(candidates, *, limit_each=PER_MARKET):
    # Show the strongest candidates in EVERY supported market; prevent
    # fouls from displacing all other markets in the editorial shortlist.
    buckets = defaultdict(list)
    for row in candidates:
        buckets[row["market"]].append(row)
    selected = []
    for market in MARKET_ORDER:
        selected.extend(sorted(buckets.pop(market, []),
                               key=lambda r: (-probability(r), str(r["fixture_id"]),
                                              str(r.get("line", "")), r["selection"]))[:limit_each])
    for market in sorted(buckets):
        selected.extend(sorted(buckets[market], key=lambda r: (-probability(r),
                               str(r["fixture_id"])))[:limit_each])
    return sorted(selected, key=lambda r: (-probability(r), str(r["fixture_id"]),
                                             r["market"], r["selection"]))

def report_day(output_pdf, queue):
    name = Path(output_pdf).stem
    if len(name) >= 10:
        try:
            return datetime.strptime(name[-10:], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return str(queue.get("date") or "brak daty raportu")

def build(predictions, events, queue, output_json, output_pdf):
    result = evaluate(predictions, events)
    fixtures = {str(f["fixture_id"]): f for f in queue["fixtures"]}
    if len(fixtures) != len(queue["fixtures"]):
        raise ValueError("duplicate_fixture")
    if any(str(row["fixture_id"]) not in fixtures for row in result["candidates"]):
        raise ValueError("unknown_fixture")
    result["queue_fixtures"] = len(fixtures)
    result["input_cutoff_utc"] = (predictions.get("generated_at_utc") or
                                  predictions.get("as_of_utc") or
                                  predictions.get("frozen_at_utc"))
    result["rules"] = {"A": "P>=70%", "B": "P>=75%", "C": "P>=80%",
                       "1X2": "both Elo and Dixon-Coles pass; max 10pp difference",
                       "events": "single-model, mathematically complete over/under pairs"}
    target = Path(output_json)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")

    from github_models.abc_chronological_pdf import render_day
    render_day(result, fixtures, output_pdf, report_day(output_pdf, queue),
               source="GitHub Models V2 — A/B/C: zamrożone dane wejściowe")
    return result

def main():
    parser = argparse.ArgumentParser()
    for name in ("predictions", "events", "queue", "output-json", "output-pdf"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    build(read(args.predictions), read(args.events), read(args.queue),
          args.output_json, args.output_pdf)

if __name__ == "__main__":
    main()
