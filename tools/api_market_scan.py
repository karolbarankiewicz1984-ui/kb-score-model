#!/usr/bin/env python3
"""API Market Scan v2 — PURE history plus a separate pre-match market overlay.

The script deliberately keeps two values:
  1) API PURE: historical coverage calculated only from stored match statistics.
  2) MARKET ADJUSTED: a conservative overlay from current bookmaker consensus
     and, when available, line movement between our own saved odds snapshots.

It NEVER changes KB Score 2.1 CORE, KB/DEV registers, model parameters, KB N or
DEV N. Market data can change only the separate MARKET ADJUSTED field.

Outputs:
  data/api_football/market_work/YYYY-MM-DD.json
  data/api_football/market_snapshots/YYYY-MM-DD/*.json
  reports/api_market_scan/YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median, pstdev

from api_market_policy import target_date

BASE = "https://v3.football.api-sports.io"
KEY = os.environ.get("API_FOOTBALL_KEY")
TARGET = target_date(sys.argv[1] if len(sys.argv) > 1 else None)

OUT_JSON = Path("data/api_football/market_work")
OUT_MD = Path("reports/api_market_scan")
OUT_SNAPSHOTS = Path("data/api_football/market_snapshots")

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

# PURE lines we are willing to evaluate. Half-lines avoid push ambiguity.
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

# Exact API-Football pre-match bet IDs, synced from /odds/bets.
# PURE yellow cards are matched only to yellow-card markets, not generic card points.
BET_IDS = {
    "team_goals": {"home": 16, "away": 17},             # Total - Home/Away
    "yellow": {"home": 150, "away": 151},              # Home/Away Team Yellow Cards
    "corners": {"home": 57, "away": 58},               # Home/Away Corners O/U
    "fouls": {"home": 171, "away": 170},               # Fouls Home/Away Total
    "shots": {"home": 221, "away": 220},               # Shots Home/Away Total
    "shots_on_goal": {"home": 88, "away": 89},         # Home/Away Total ShotOnGoal
    "offsides": {"home": 167, "away": 168},            # Offsides Home/Away Total
    "goalkeeper_saves": {"home": 268, "away": 274},    # Home/Away Goalkeeper Saves
}

MAX_MARKET_ADJUSTMENT_PP = 10.0
MAX_MOVEMENT_COMPONENT_PP = 2.0


def api_get(endpoint: str, **params):
    if not KEY:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response), {k.lower(): v for k, v in response.headers.items()}


def api_get_all_pages(endpoint: str, **params):
    page = 1
    merged = []
    last_headers = {}
    while True:
        payload, last_headers = api_get(endpoint, page=page, **params)
        if payload.get("errors"):
            return payload, last_headers
        merged.extend(payload.get("response", []))
        paging = payload.get("paging") or {}
        total = int(paging.get("total") or 1)
        if page >= total:
            break
        page += 1
    return {"errors": [], "response": merged, "pages": page}, last_headers


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
            old = by_id.get(fid)
            if old is None or len(row.get("teams") or []) > len(old.get("teams") or []):
                by_id[fid] = row
    return sorted(by_id.values(), key=lambda r: parse_dt(r.get("date")))


def team_block(row: dict, team_id: int):
    for block in row.get("teams") or []:
        if block.get("team_id") == team_id:
            return block
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
    return block.get(market) if block else None


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
    if not own_vals or not allowed_vals:
        return None

    own_w = window_set(own_vals, line)
    opp_w = window_set(allowed_vals, line)
    own_score = weighted_windows(own_w)
    opp_score = weighted_windows(opp_w)
    if own_score is None or opp_score is None:
        return None

    venue_vals = venue_values(own_hist, team_id, market, team_side == "home")
    venue = coverage(venue_vals, line, 10) if len(venue_vals) >= 4 else None
    if venue:
        combined = 0.55 * own_score + 0.35 * opp_score + 0.10 * venue["pct"]
    else:
        combined = 0.61 * own_score + 0.39 * opp_score

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
        "api_pure_pct": round(combined, 1),
        "confidence_api": round(confidence, 1),
        "scope": scope_label,
        "own": own_w,
        "opponent_allowed": opp_w,
        "venue": venue,
        "europe_only": europe,
        "samples": {"own_available": len(own_vals), "opponent_allowed_available": len(allowed_vals)},
    }


def parse_decimal(value):
    try:
        x = float(str(value).replace(",", "."))
        return x if x > 1.0 else None
    except Exception:
        return None


def parse_ou_value(value, handicap=None):
    text = str(value or "").strip()
    low = text.lower()
    side = "over" if "over" in low else "under" if "under" in low else None
    if not side:
        return None, None
    numbers = re.findall(r"[-+]?\d+(?:[\.,]\d+)?", text)
    if numbers:
        line = float(numbers[-1].replace(",", "."))
    else:
        try:
            line = float(str(handicap).replace(",", ".")) if handicap is not None else None
        except Exception:
            line = None
    return side, line


def extract_market_quotes(odds_response, candidate):
    bet_id = BET_IDS[candidate["market"]][candidate["team_side"]]
    target_line = float(candidate["line"])
    books = []
    offered_books = 0

    for fixture_block in odds_response:
        for bookmaker in fixture_block.get("bookmakers") or []:
            bname = bookmaker.get("name") or f"bookmaker-{bookmaker.get('id')}"
            for bet in bookmaker.get("bets") or []:
                if int(bet.get("id") or -1) != bet_id:
                    continue
                pair = {"over": None, "under": None}
                for item in bet.get("values") or []:
                    side, line = parse_ou_value(item.get("value"), item.get("handicap"))
                    if side is None or line is None or abs(line - target_line) > 1e-6:
                        continue
                    odd = parse_decimal(item.get("odd"))
                    if odd:
                        pair[side] = odd
                if pair["over"] or pair["under"]:
                    offered_books += 1
                if pair["over"] and pair["under"]:
                    raw_over = 1.0 / pair["over"]
                    raw_under = 1.0 / pair["under"]
                    devig = raw_over / (raw_over + raw_under)
                    books.append({
                        "bookmaker": bname,
                        "over_odd": round(pair["over"], 4),
                        "under_odd": round(pair["under"], 4),
                        "devig_over_probability": round(devig * 100.0, 2),
                    })
                break

    probs = [b["devig_over_probability"] for b in books]
    if not probs:
        return {
            "bet_id": bet_id,
            "exact_line_available": offered_books > 0,
            "offered_books": offered_books,
            "paired_books": 0,
            "market_probability_pct": None,
            "bookmaker_spread_pp": None,
            "quotes": [],
        }
    spread = pstdev(probs) if len(probs) >= 2 else 0.0
    return {
        "bet_id": bet_id,
        "exact_line_available": True,
        "offered_books": offered_books,
        "paired_books": len(books),
        "market_probability_pct": round(median(probs), 1),
        "bookmaker_spread_pp": round(spread, 1),
        "quotes": books,
    }


def market_key(candidate):
    return f"{candidate['fixture_id']}|{candidate['team_id']}|{candidate['market']}|{candidate['line']:.1f}"


def load_prior_market_probabilities(target):
    folder = OUT_SNAPSHOTS / target
    prior = {}
    if not folder.exists():
        return prior
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("items", []):
            p = item.get("market_probability_pct")
            if p is None:
                continue
            key = item.get("key")
            if key and key not in prior:
                prior[key] = {"probability": float(p), "snapshot": path.name}
    return prior


def clamp(value, low, high):
    return max(low, min(high, value))


def market_weight(paired_books, spread_pp):
    if paired_books < 2:
        return 0.0, "insufficient"
    if paired_books >= 6 and (spread_pp is None or spread_pp <= 6.0):
        return 0.35, "strong"
    if paired_books >= 3 and (spread_pp is None or spread_pp <= 10.0):
        return 0.25, "medium"
    return 0.15, "weak"


def apply_market_overlay(candidate, market, prior):
    pure = float(candidate["api_pure_pct"])
    market_prob = market.get("market_probability_pct")
    movement_pp = None
    weight, reliability = market_weight(market.get("paired_books", 0), market.get("bookmaker_spread_pp"))

    key = market_key(candidate)
    if market_prob is not None and key in prior:
        movement_pp = round(float(market_prob) - float(prior[key]["probability"]), 1)

    if market_prob is None or weight == 0.0:
        adjusted = pure
        delta = 0.0
        movement_component = 0.0
    else:
        consensus_component = (float(market_prob) - pure) * weight
        movement_component = 0.0 if movement_pp is None else clamp(movement_pp * 0.25, -MAX_MOVEMENT_COMPONENT_PP, MAX_MOVEMENT_COMPONENT_PP)
        delta = clamp(consensus_component + movement_component, -MAX_MARKET_ADJUSTMENT_PP, MAX_MARKET_ADJUSTMENT_PP)
        adjusted = clamp(pure + delta, 1.0, 99.0)

    delta = round(adjusted - pure, 1)
    adjusted = round(adjusted, 1)
    signal = market_signal(delta, market, reliability)
    result = dict(candidate)
    result.update({
        "market_adjusted_pct": adjusted,
        "market_delta_pp": delta,
        "market_signal": signal,
        "market_reliability": reliability,
        "market_data": market,
        "market_movement_pp": movement_pp,
        "market_comment": market_comment(delta, market, reliability, movement_pp),
    })
    return result


def market_signal(delta, market, reliability):
    if not market.get("exact_line_available"):
        return "NO_MARKET_LINE"
    if market.get("paired_books", 0) < 2:
        return "THIN_MARKET"
    if delta >= 4.0:
        return "STRONG_CONFIRMATION"
    if delta >= 1.5:
        return "CONFIRMATION"
    if delta <= -4.0:
        return "STRONG_WARNING"
    if delta <= -1.5:
        return "WARNING"
    return "NEUTRAL"


def market_comment(delta, market, reliability, movement_pp):
    if not market.get("exact_line_available"):
        return "Dla tej dokładnej linii nie znalazłem bieżącej oferty w danych rynkowych. Korekta samego rynku wynosi zero."
    if market.get("paired_books", 0) < 2:
        return "Linia jest dostępna, ale rynek jest zbyt wąski, żeby bezpiecznie korygować statystykę historyczną. Korekta samego rynku wynosi zero."

    if delta >= 4.0:
        opening = "Rynek wyraźnie potwierdza kierunek wskazany przez historię i podnosi ocenę."
    elif delta >= 1.5:
        opening = "Rynek umiarkowanie potwierdza sygnał historyczny, dlatego ocena rośnie."
    elif delta <= -4.0:
        opening = "Rynek wyraźnie nie zgadza się z mocnym wynikiem historycznym, więc ocena zostaje istotnie obniżona."
    elif delta <= -1.5:
        opening = "Rynek jest ostrożniejszy niż sama historia i lekko obniża ocenę."
    else:
        opening = "Rynek jest zasadniczo zgodny z historią i nie daje powodu do większej korekty."

    extras = []
    spread = market.get("bookmaker_spread_pp")
    paired = market.get("paired_books", 0)
    if reliability == "strong":
        extras.append("Notowania wielu bukmacherów są spójne.")
    elif paired <= 2:
        extras.append("Dostępnych jest tylko kilka pełnych notowań, dlatego korekta jest ograniczona.")
    elif spread is not None and spread > 10:
        extras.append("Między bukmacherami widać większy rozrzut, dlatego korekta jest ograniczona.")
    elif reliability == "medium":
        extras.append("Konsensus rynku jest wystarczająco szeroki do umiarkowanej korekty.")

    if movement_pp is not None:
        if movement_pp >= 3.0:
            extras.append("Od wcześniejszego odczytu rynek przesuwa się dodatkowo w stronę over.")
        elif movement_pp <= -3.0:
            extras.append("Od wcześniejszego odczytu rynek przesuwa się przeciwko over.")
        else:
            extras.append("Od wcześniejszego odczytu nie ma istotnego ruchu rynku.")
    else:
        extras.append("To pierwszy zapis rynku dla tej pozycji, więc ruch kursu nie jest jeszcze oceniany.")
    return " ".join([opening] + extras)


def arrow(delta):
    if delta > 0.4:
        return "↑"
    if delta < -0.4:
        return "↓"
    return "→"


def signal_label(signal):
    return {
        "STRONG_CONFIRMATION": "mocne potwierdzenie",
        "CONFIRMATION": "potwierdzenie",
        "NEUTRAL": "neutralny",
        "WARNING": "ostrzeżenie",
        "STRONG_WARNING": "mocne ostrzeżenie",
        "THIN_MARKET": "zbyt mało danych rynkowych",
        "NO_MARKET_LINE": "brak dokładnej linii rynkowej",
    }.get(signal, signal)


def main():
    rows = load_rows()
    fixtures_payload, fixture_headers = api_get("fixtures", date=TARGET, timezone="Europe/Warsaw")
    if fixtures_payload.get("errors"):
        raise RuntimeError(json.dumps(fixtures_payload.get("errors"), ensure_ascii=False))

    # v2 scans only matches that have not started. Finished/live fixtures never enter a betting shortlist.
    fixtures = []
    for fixture in fixtures_payload.get("response", []):
        cat = competition_category(fixture.get("league", {}))
        status = fixture.get("fixture", {}).get("status", {}).get("short")
        if cat and status in {"NS", "TBD"}:
            fixtures.append(fixture)

    pure_candidates = []
    for fixture in fixtures:
        for side in ("home", "away"):
            for market, spec in MARKETS.items():
                for line in spec["lines"]:
                    cand = build_candidate(rows, fixture, side, market, line)
                    if cand:
                        pure_candidates.append(cand)

    odds_by_fixture = {}
    odds_errors = []
    odds_requests = 0
    last_odds_headers = {}
    for fixture in fixtures:
        fid = fixture.get("fixture", {}).get("id")
        try:
            payload, last_odds_headers = api_get_all_pages("odds", fixture=fid)
            odds_requests += int(payload.get("pages") or 1)
            if payload.get("errors"):
                odds_errors.append({"fixture_id": fid, "errors": payload.get("errors")})
                odds_by_fixture[fid] = []
            else:
                odds_by_fixture[fid] = payload.get("response", [])
        except Exception as exc:
            odds_errors.append({"fixture_id": fid, "error": str(exc)})
            odds_by_fixture[fid] = []

    prior = load_prior_market_probabilities(TARGET)
    enriched = []
    snapshot_items = []
    for candidate in pure_candidates:
        market = extract_market_quotes(odds_by_fixture.get(candidate["fixture_id"], []), candidate)
        item = apply_market_overlay(candidate, market, prior)
        enriched.append(item)
        snapshot_items.append({
            "key": market_key(candidate),
            "fixture_id": candidate["fixture_id"],
            "team": candidate["team"],
            "market": candidate["market"],
            "line": candidate["line"],
            "market_probability_pct": market.get("market_probability_pct"),
            "paired_books": market.get("paired_books", 0),
            "bookmaker_spread_pp": market.get("bookmaker_spread_pp"),
        })

    # Preserve every calculable line. Selection happens only after all API layers.
    ranked = sorted(enriched, key=lambda c: (c["api_pure_pct"], c["confidence_api"]), reverse=True)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%H%M%S")
    snapshot_folder = OUT_SNAPSHOTS / TARGET
    snapshot_folder.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_folder / f"{stamp}.json"
    snapshot_payload = {
        "schema": "api-market-snapshot-v1",
        "date": TARGET,
        "captured_at_utc": now.isoformat(),
        "items": snapshot_items,
        "isolation": "MARKET_OVERLAY_ONLY_NO_KB_SCORE_CORE_WRITES",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }
    snapshot_path.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    payload = {
        "schema": "api-market-scan-v2",
        "date": TARGET,
        "fixtures_scanned": len(fixtures),
        "history_matches_loaded": len(rows),
        "pure_candidates_before_dedupe": len(pure_candidates),
        "background_candidates": ranked,
        "generated_at_utc": now.isoformat(),
        "top_positions": ranked,
        "market_overlay": {
            "method": "devigged multi-bookmaker consensus + own snapshot movement",
            "max_adjustment_pp": MAX_MARKET_ADJUSTMENT_PP,
            "odds_requests": odds_requests,
            "odds_errors": odds_errors,
            "snapshot": str(snapshot_path),
        },
        "thresholds": {
            "raw_coverage_threshold": None,
            "raw_sample_gate": "nonempty numeric history on both sides",
            "top_n": None,
        },
        "rate_limit_remaining": last_odds_headers.get("x-ratelimit-requests-remaining") or fixture_headers.get("x-ratelimit-requests-remaining"),
        "isolation": "API_PURE_PLUS_MARKET_OVERLAY_NO_KB_SCORE_CORE_WRITES",
        "model_effect": "NONE",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }

    OUT_JSON.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)
    (OUT_JSON / f"{TARGET}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "schema": "api-market-scan-v2",
        "date": TARGET,
        "fixtures_scanned": len(fixtures),
        "history_matches_loaded": len(rows),
        "top_positions": len(ranked),
        "odds_requests": odds_requests,
        "snapshot": str(snapshot_path),
        "working_file": str(OUT_JSON / f"{TARGET}.json"),
        "kb_n_effect": 0,
        "dev_n_effect": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
