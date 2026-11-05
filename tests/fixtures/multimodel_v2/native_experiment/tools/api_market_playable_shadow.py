#!/usr/bin/env python3
"""Independent, read-only playable-odds shadow report. Never modifies production."""
from __future__ import annotations
import json
import math
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/api_market_playable_experiment.json"

def eligible_quotes(item, minimum=1.20):
    direction = item.get("direction", "over")
    if direction not in ("over", "under"):
        return []
    result = []
    for quote in (item.get("market_data") or {}).get("quotes") or []:
        price = quote.get(direction + "_odd")
        if isinstance(price, bool) or not isinstance(price, (float, int)):
            continue
        if math.isfinite(price) and price >= minimum:
            result.append({"bookmaker": str(quote.get("bookmaker") or "nieznany").strip(),
                           "odd": float(price)})
    return result

def evaluate(payload, cfg):
    reasons = Counter()
    accepted = []
    for item in payload.get("background_candidates") or []:
        score = item.get("final_assessment_pct")
        if not isinstance(score, (float, int)) or isinstance(score, bool) or not math.isfinite(score) or score < cfg["preserve_min_final_score"]:
            reasons["below_score_threshold"] += 1
            continue
        quotes = eligible_quotes(item, cfg["min_quoted_odds"])
        if not quotes:
            reasons["no_eligible_quote"] += 1
            continue
        item = dict(item)
        item["playable_quotes"] = quotes
        item["best_quote"] = max(quotes, key=lambda q: q["odd"])
        item["sts_quote"] = max((q["odd"] for q in quotes if q["bookmaker"].casefold() == "sts"), default=None)
        item["superbet_quote"] = max((q["odd"] for q in quotes if q["bookmaker"].casefold() == "superbet"), default=None)
        accepted.append(item)
    accepted.sort(key=lambda x: (-x["final_assessment_pct"], -float(x.get("api_pure_pct") or 0), str(x.get("fixture_id")), str(x.get("selection"))))
    return accepted, dict(reasons)

def export_position(item, target_date):
    """Machine-readable PREMATCH record for the independent MULTIMODEL bridge.

    A quoted price from the API is not independently verified as a live quote
    at STS or Superbet; no model scoring or production selections are changed.
    """
    best = item["best_quote"]
    matching = [q for q in ((item.get("market_data") or {}).get("quotes") or [])
                if str(q.get("bookmaker") or "").strip() == best["bookmaker"]
                and q.get("selected_odd") == best["odd"]]
    quoted = matching[0] if matching else {}
    return {
        "date": target_date,
        "fixture_id": item.get("fixture_id"),
        "home": item.get("home"),
        "away": item.get("away"),
        "kickoff": item.get("kickoff"),
        "competition": item.get("competition"),
        "market": item.get("market"),
        "market_scope": item.get("market_scope"),
        "team_side": item.get("team_side"),
        "team_id": item.get("team_id"),
        "bet_id": item.get("bet_id"),
        "line": item.get("line"),
        "direction": item.get("direction"),
        "settlement_period": item.get("settlement_period", "regulation_time"),
        "selection": item.get("selection"),
        "api_pure_pct": item.get("api_pure_pct"),
        "final_assessment_pct": item.get("final_assessment_pct"),
        "final_status": item.get("final_status"),
        "samples": item.get("samples"),
        "best_quote": {
            "bookmaker": best["bookmaker"],
            "odd": best["odd"],
            "provider_updated_at": quoted.get("provider_updated_at"),
            "bookmaker_id": quoted.get("bookmaker_id"),
        },
        "sts_quote": item.get("sts_quote"),
        "superbet_quote": item.get("superbet_quote"),
        "quote_source": "API-Football archived prematch bookmaker quotes",
        "verified_live_in_polish_bookmaker": False,
    }


def report(payload, cfg):
    positions, reasons = evaluate(payload, cfg)
    lines = [f"# API Market Scan — shadow playable — {payload.get('date', 'unknown')}", "",
             f"Minimum kursu: {cfg['min_quoted_odds']:.2f}. Próg oceny: {cfg['preserve_min_final_score']:g}/100.",
             f"Kandydaci: {len(payload.get('background_candidates') or [])}. Zakwalifikowani: {len(positions)}.",
             f"Odrzucenia: {json.dumps(reasons, ensure_ascii=False)}.",
             "STS i Superbet: brak notowania oznacza niepotwierdzone, nie niedostępne.",
             "Ocena /100 nie jest skalibrowanym prawdopodobieństwem.", ""]
    # PitchAPI review is optional. Only annotated historic evidence is added
    # to the display; original score, ranking, odds and selections stay intact.
    try:
        from pitchapi_market_validation import load_snapshot, review_position
        xg_snapshot = load_snapshot(str(payload.get('date')))
    except ImportError:
        xg_snapshot, review_position = None, None
    groups = {}
    for item in positions:
        groups.setdefault(str(item.get("fixture_id")), []).append(item)
    for fid, items in sorted(groups.items(), key=lambda kv: (str(kv[1][0].get("kickoff")), kv[0])):
        first = items[0]
        lines += [f"## {first.get('home')} – {first.get('away')} ({first.get('kickoff')})", "",
                  "| Typ | Ocena /100 | Najlepszy kurs | STS | Superbet |", "|---|---:|---|---|---|"]
        for item in items:
            best = item["best_quote"]
            fmt = lambda x: f"{x:.2f}" if x is not None else "niepotwierdzone"
            selection = str(item.get("selection", "")).replace("|", "\\|")
            if review_position is not None:
                review = review_position(item, xg_snapshot)
                if review and review["status"] not in ("no_data", "insufficient"):
                    tag = {"favors":"historia okazji sprzyja", "cautions":"OSTROZNIE: historia okazji ostrzega",
                           "mixed":"historia okazji bez wyraźnego sygnału"}[review["status"]]
                    selection += f" — PitchAPI: {tag} (poglądowo, ocena bez zmian)"
            lines.append(f"| {selection} | {item['final_assessment_pct']:.1f} | {best['odd']:.2f} ({best['bookmaker']}) | {fmt(item['sts_quote'])} | {fmt(item['superbet_quote'])} |")
        lines.append("")
    audit = {"candidate_count":len(payload.get("background_candidates") or []),
             "published_count":len(positions),"rejections":reasons,
             "schema":"api-market-playable-export-v2",
             "date":payload.get("date"),
             "generated_at_utc":datetime.now(timezone.utc).isoformat(),
             "positions":[export_position(item, payload.get("date")) for item in positions],
             "quote_verification":"API snapshot only; recheck exact market and live bookmaker quote before PLAY",
             "model_score_is_probability":False}
    return "\n".join(lines), audit

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date or len(date) != 10:
        raise SystemExit("Usage: python tools/api_market_playable_shadow.py YYYY-MM-DD")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = ROOT / "data/api_football/market_scan" / f"{date}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    markdown, audit = report(payload, cfg)
    dest = ROOT / "reports/api_market_scan/v2"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"API_MARKET_SCAN_PLAYABLE_{date}.md").write_text(markdown, encoding="utf-8")
    (dest / f"API_MARKET_SCAN_PLAYABLE_{date}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"date":audit["date"],"candidate_count":audit["candidate_count"],"published_count":audit["published_count"],"rejections":audit["rejections"],"position_export":"complete"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
