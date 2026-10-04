#!/usr/bin/env python3
"""API Market Scan — separate statistical layer for KB Score project.

Reads locally stored API-Football history, fetches fixtures for a target day and
ranks team-market candidates by historical coverage. This module NEVER changes
KB Score 2.1 CORE, KB/DEV registers, model parameters, KB N or DEV N.

Output:
  data/api_football/market_scan/YYYY-MM-DD.json
  reports/api_market_scan/YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
TARGET = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

OUT_JSON = Path("data/api_football/market_scan")
OUT_MD = Path("reports/api_market_scan")

DOMESTIC = {
    ("England", "Premier League"), ("Spain", "La Liga"), ("Italy", "Serie A"),
    ("Germany", "Bundesliga"), ("France", "Ligue 1"),
    ("Portugal", "Primeira Liga"), ("Netherlands", "Eredivisie"),
    ("Belgium", "Jupiler Pro League"), ("Turkey", "Süper Lig"),
    ("Poland", "Ekstraklasa"),
}
CLUB_INTL = {
    "UEFA Champions League", "UEFA Europa League",
    "UEFA Europa Conference League", "UEFA Super Cup",
}
NATIONAL = {
    "World Cup", "World Cup - Qualification Europe", "Euro Championship",
    "Euro Championship - Qualification", "UEFA Nations League", "Friendlies",
}

# Statistical lines only — no bookmaker-settlement assumptions are hidden.
# Cards are explicitly YELLOW cards, not bookmaker card-points.
MARKETS = {
    "team_goals": {"label": "gole drużyny", "lines": [0.5, 1.5, 2.5]},
    "yellow": {"label": "żółte kartki drużyny", "lines": [0.5, 1.5, 2.5, 3.5]},
    "corners": {"label": "rożne drużyny", "lines": [2.5, 3.5, 4.5, 5.5, 6.5, 7.5]},
    "fouls": {"label": "faule drużyny", "lines": [7.5, 9.5, 11.5, 13.5, 15.5]},
    "shots": {"label": "strzały drużyny", "lines": [7.5, 9.5, 11.5, 13.5, 15.5]},
    "shots_on_goal": {"label": "strzały celne drużyny", "lines": [2.5, 3.5, 4.5, 5.5, 6.5]},
    "offsides": {"label": "spalone drużyny", "lines": [0.5, 1.5, 2.5, 3.5]},
    "goalkeeper_saves": {"label": "interwencje bramkarza", "lines": [1.5, 2.5, 3.5, 4.5, 5.5]},
}

MIN_COMBINED = 72.0
MIN_OWN_L10 = 60.0
MIN_OPP_L10 = 50.0
MIN_SIDE_SAMPLE = 7
TOP_N = 10


def api_get(endpoint: str, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response), {k.lower(): v for k, v in response.headers.items()}


def competition_category(league: dict) -> str | None:
    country, name = league.get("country"), league.get("name")
    if (country, name) in DOMESTIC:
        return "domestic"
    if name in CLUB_INTL:
        return "international_club"
    if name in NATIONAL:
        return "national_team"
    return None


def row_category(row: dict) -> str | None:
    name = row.get("league") or row.get("competition")
    country = row.get("country")
    if (country, name) in DOMESTIC:
        return "domestic"
    if name in CLUB_INTL:
        return "international_club"
    if name in NATIONAL:
        return "national_team"
    return row.get("category") if row.get("category") in {"domestic", "international_club", "national_team"} else None


def parse_dt(value: str | None):
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.min


def load_rows():
    files = []
    files += list(Path("data/api_football/backfill_5m").glob("*.json"))
    files += list(Path("data/api_football/daily").glob("*.json"))
    files += list(Path("data/api_football/international_5m/club").glob("*.json"))
    files += list(Path("data/api_football/international_5m/national").glob("*.json"))

    by_id = {}
    for path in files:
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in payload.get("rows", []):
            fid = row.get("fixture_id")
            if fid is None:
                continue
            cat = row_category(row)
            if not cat:
                continue
            row = dict(row)
            row["_category"] = cat
            # Prefer a record with detailed team blocks if duplicates exist.
            old = by_id.get(fid)
            if old is None or len(row.get("teams") or []) > len(old.get("teams") or []):
                by_id[fid] = row
    return sorted(by_id.values(), key=lambda r: parse_dt(r.get("date")))


def team_block(row: dict, team_id: int):
    for block in row.get("teams") or []:
        if block.get("team_id") == team_id:
            return block
    # Older domestic rows may not have team_id inside blocks; resolve by home/away order/name.
    h_id, a_id = row.get("home_id"), row.get("away_id")
    blocks = row.get("teams") or []
    if len(blocks) == 2:
        if team_id == h_id:
            return blocks[0]
        if team_id == a_id:
            return blocks[1]
    return None


def opponent_id(row: dict, team_id: int):
    if row.get("home_id") == team_id:
        return row.get("away_id")
    if row.get("away_id") == team_id:
        return row.get("home_id")
    return None


def metric_value(row: dict, team_id: int, market: str):
    if market == "team_goals":
        goals = row.get("goals") or {}
        if row.get("home_id") == team_id:
            return goals.get("home")
        if row.get("away_id") == team_id:
            return goals.get("away")
        return None
    block = team_block(row, team_id)
    if not block:
        return None
    return block.get(market)


def team_history(rows, team_id: int, fixture_dt: datetime, scope: str):
    result = []
    for row in rows:
        if parse_dt(row.get("date")) >= fixture_dt:
            continue
        if team_id not in {row.get("home_id"), row.get("away_id")}:
            continue
        cat = row.get("_category")
        if scope == "national" and cat != "national_team":
            continue
        if scope == "domestic" and cat != "domestic":
            continue
        if scope == "club_all" and cat not in {"domestic", "international_club"}:
            continue
        if scope == "europe_only" and cat != "international_club":
            continue
        result.append(row)
    return result


def coverage(values, line: float, n: int):
    vals = [v for v in values if isinstance(v, (int, float))][-n:]
    if not vals:
        return None
    hits = sum(1 for value in vals if value > line)
    return {"hits": hits, "n": len(vals), "pct": 100.0 * hits / len(vals)}


def window_set(values, line):
    return {f"L{n}": coverage(values, line, n) for n in (5, 10, 15)}


def weighted_windows(windows):
    weights = {"L5": 0.20, "L10": 0.30, "L15": 0.50}
    items = [(windows[k]["pct"], weights[k]) for k in weights if windows.get(k)]
    if not items:
        return None
    denom = sum(w for _, w in items)
    return sum(v * w for v, w in items) / denom


def venue_values(history, team_id, market, current_is_home):
    vals = []
    for row in history:
        same = (row.get("home_id") == team_id) if current_is_home else (row.get("away_id") == team_id)
        if same:
            value = metric_value(row, team_id, market)
            if isinstance(value, (int, float)):
                vals.append(value)
    return vals


def opponent_allowed_values(history, opponent_team_id, market):
    vals = []
    for row in history:
        other = opponent_id(row, opponent_team_id)
        if other is None:
            continue
        value = metric_value(row, other, market)
        if isinstance(value, (int, float)):
            vals.append(value)
    return vals


def agreement_score(pcts):
    pcts = [p for p in pcts if p is not None]
    if len(pcts) < 2:
        return 0.5
    mean = sum(pcts) / len(pcts)
    variance = sum((p - mean) ** 2 for p in pcts) / len(pcts)
    sd = math.sqrt(variance)
    return max(0.0, min(1.0, 1.0 - sd / 35.0))


def build_candidate(rows, fixture, team_side: str, market: str, line: float):
    league = fixture.get("league", {})
    cat = competition_category(league)
    fixture_dt = parse_dt(fixture.get("fixture", {}).get("date"))
    team = fixture.get("teams", {}).get(team_side, {})
    opp_side = "away" if team_side == "home" else "home"
    opp = fixture.get("teams", {}).get(opp_side, {})
    team_id, opp_id = team.get("id"), opp.get("id")
    if team_id is None or opp_id is None:
        return None

    if cat == "national_team":
        scope, scope_label = "national", "reprezentacje"
    elif cat == "international_club":
        scope, scope_label = "club_all", "klub: liga + Europa"
    else:
        scope, scope_label = "domestic", "liga krajowa"

    own_hist = team_history(rows, team_id, fixture_dt, scope)
    opp_hist = team_history(rows, opp_id, fixture_dt, scope)
    own_vals = [metric_value(row, team_id, market) for row in own_hist]
    own_vals = [v for v in own_vals if isinstance(v, (int, float))]
    allowed_vals = opponent_allowed_values(opp_hist, opp_id, market)

    if len(own_vals) < MIN_SIDE_SAMPLE or len(allowed_vals) < MIN_SIDE_SAMPLE:
        return None

    own_w = window_set(own_vals, line)
    opp_w = window_set(allowed_vals, line)
    own_score = weighted_windows(own_w)
    opp_score = weighted_windows(opp_w)
    if own_score is None or opp_score is None:
        return None

    own_l10 = own_w.get("L10")
    opp_l10 = opp_w.get("L10")
    if not own_l10 or not opp_l10 or own_l10["pct"] < MIN_OWN_L10 or opp_l10["pct"] < MIN_OPP_L10:
        return None

    venue_vals = venue_values(own_hist, team_id, market, team_side == "home")
    venue = coverage(venue_vals, line, 10) if len(venue_vals) >= 4 else None

    # Primary coverage: own trend has greatest weight, opponent allowance confirms it.
    if venue:
        combined = 0.55 * own_score + 0.35 * opp_score + 0.10 * venue["pct"]
    else:
        combined = 0.61 * own_score + 0.39 * opp_score

    if combined < MIN_COMBINED:
        return None

    pcts = []
    for block in (own_w, opp_w):
        pcts += [block[k]["pct"] for k in ("L5", "L10", "L15") if block.get(k)]
    if venue:
        pcts.append(venue["pct"])
    agreement = agreement_score(pcts)
    sample_factor = min(1.0, (min(len(own_vals), 15) + min(len(allowed_vals), 15)) / 30.0)
    confidence = 10.0 * (0.62 * (combined / 100.0) + 0.23 * sample_factor + 0.15 * agreement)

    europe = None
    if cat == "international_club":
        euro_hist = team_history(rows, team_id, fixture_dt, "europe_only")
        euro_vals = [metric_value(row, team_id, market) for row in euro_hist]
        euro_vals = [v for v in euro_vals if isinstance(v, (int, float))]
        if len(euro_vals) >= 4:
            europe = window_set(euro_vals, line)

    return {
        "fixture_id": fixture.get("fixture", {}).get("id"),
        "kickoff": fixture.get("fixture", {}).get("date"),
        "competition": league.get("name"),
        "category": cat,
        "home": fixture.get("teams", {}).get("home", {}).get("name"),
        "away": fixture.get("teams", {}).get("away", {}).get("name"),
        "team_id": team_id,
        "team": team.get("name"),
        "opponent": opp.get("name"),
        "team_side": team_side,
        "market": market,
        "market_label": MARKETS[market]["label"],
        "line": line,
        "selection": f"{team.get('name')} over {line:.1f} — {MARKETS[market]['label']}",
        "coverage_pct": round(combined, 1),
        "confidence_kb_api": round(confidence, 1),
        "scope": scope_label,
        "own": own_w,
        "opponent_allowed": opp_w,
        "venue": venue,
        "europe_only": europe,
        "samples": {"own_available": len(own_vals), "opponent_allowed_available": len(allowed_vals)},
    }


def fmt_window(block, key):
    item = block.get(key) if block else None
    if not item:
        return "—"
    return f"{item['hits']}/{item['n']} ({item['pct']:.0f}%)"


def explanation(candidate):
    parts = [
        f"własne L15 {fmt_window(candidate['own'], 'L15')}",
        f"rywal dopuszcza L15 {fmt_window(candidate['opponent_allowed'], 'L15')}",
    ]
    if candidate.get("venue"):
        v = candidate["venue"]
        parts.append(f"dom/wyjazd {v['hits']}/{v['n']} ({v['pct']:.0f}%)")
    if candidate.get("europe_only") and candidate["europe_only"].get("L10"):
        parts.append(f"Europa L10 {fmt_window(candidate['europe_only'], 'L10')}")
    return "; ".join(parts) + "."


def main():
    rows = load_rows()
    fixtures_payload, headers = api_get("fixtures", date=TARGET, timezone="Europe/Warsaw")
    if fixtures_payload.get("errors"):
        raise RuntimeError(json.dumps(fixtures_payload.get("errors"), ensure_ascii=False))

    fixtures = []
    for fixture in fixtures_payload.get("response", []):
        cat = competition_category(fixture.get("league", {}))
        status = fixture.get("fixture", {}).get("status", {}).get("short")
        if cat and status not in {"PST", "CANC", "ABD"}:
            fixtures.append(fixture)

    candidates = []
    for fixture in fixtures:
        for side in ("home", "away"):
            for market, spec in MARKETS.items():
                for line in spec["lines"]:
                    cand = build_candidate(rows, fixture, side, market, line)
                    if cand:
                        candidates.append(cand)

    # Avoid stacking many adjacent lines for the same team/market. Keep the strongest line.
    best_by_market = {}
    for cand in candidates:
        key = (cand["fixture_id"], cand["team_id"], cand["market"])
        old = best_by_market.get(key)
        rank = (cand["coverage_pct"], cand["confidence_kb_api"], cand["line"])
        if old is None or rank > (old["coverage_pct"], old["confidence_kb_api"], old["line"]):
            best_by_market[key] = cand

    ranked = sorted(
        best_by_market.values(),
        key=lambda c: (c["coverage_pct"], c["confidence_kb_api"], c["samples"]["own_available"]),
        reverse=True,
    )[:TOP_N]

    for item in ranked:
        item["explanation"] = explanation(item)

    payload = {
        "schema": "api-market-scan-v1",
        "date": TARGET,
        "fixtures_scanned": len(fixtures),
        "history_matches_loaded": len(rows),
        "candidate_markets_before_dedupe": len(candidates),
        "top_positions": ranked,
        "thresholds": {
            "min_combined_coverage_pct": MIN_COMBINED,
            "min_own_L10_pct": MIN_OWN_L10,
            "min_opponent_allowed_L10_pct": MIN_OPP_L10,
            "min_side_sample": MIN_SIDE_SAMPLE,
            "top_n": TOP_N,
        },
        "rate_limit_remaining": headers.get("x-ratelimit-requests-remaining"),
        "isolation": "API_COVERAGE_ONLY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }

    OUT_JSON.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)
    (OUT_JSON / f"{TARGET}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# API Market Scan — {TARGET}", "",
        "> Osobna warstwa statystyczna. Nie zmienia KB Score 2.1 CORE, KB N ani DEV N.", "",
        f"Przeskanowane mecze: **{len(fixtures)}**  ",
        f"Historia w bazie: **{len(rows)} meczów**  ",
        f"Minimalne pokrycie rankingu: **{MIN_COMBINED:.0f}%**", "",
    ]
    if not ranked:
        lines += ["## Brak pozycji spełniających dzisiejsze progi", "", "System nie dobija listy słabszymi kandydatami."]
    else:
        lines.append("## TOP pozycje API")
        lines.append("")
        for idx, item in enumerate(ranked, 1):
            lines += [
                f"### {idx}. {item['selection']}",
                f"**Pokrycie:** {item['coverage_pct']:.1f}%  ",
                f"**Confidence API:** {item['confidence_kb_api']:.1f}/10  ",
                f"**Mecz:** {item['home']} – {item['away']} ({item['competition']})  ",
                f"**L5/L10/L15 własne:** {fmt_window(item['own'],'L5')} / {fmt_window(item['own'],'L10')} / {fmt_window(item['own'],'L15')}  ",
                f"**L5/L10/L15 od strony rywala:** {fmt_window(item['opponent_allowed'],'L5')} / {fmt_window(item['opponent_allowed'],'L10')} / {fmt_window(item['opponent_allowed'],'L15')}  ",
                f"**Dlaczego:** {item['explanation']}", "",
            ]
    (OUT_MD / f"{TARGET}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "date": TARGET,
        "fixtures_scanned": len(fixtures),
        "history_matches_loaded": len(rows),
        "top_positions": len(ranked),
        "json": str(OUT_JSON / f"{TARGET}.json"),
        "report": str(OUT_MD / f"{TARGET}.md"),
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
