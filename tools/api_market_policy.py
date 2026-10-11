"""Policy owned exclusively by API Market Scan. No KB Score dependencies."""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG = Path(__file__).resolve().parents[1] / "config/api_market.json"


def load_policy():
    policy = json.loads(CONFIG.read_text(encoding="utf-8"))
    floor = float(policy["publish_min_final_pct"])
    if not math.isfinite(floor) or not 0 <= floor <= 100:
        raise ValueError("Invalid API publication threshold")
    if policy["calibration"].get("kb_score_integration") is not False:
        raise ValueError("KB Score integration is forbidden")
    return policy


def target_date(value=None):
    value = value or datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def candidate_key(item):
    base = f"{item['fixture_id']}|{item['team_id']}|{item['market']}|{float(item['line']):.1f}"
    scope, direction = item.get("market_scope", "team"), item.get("direction", "over")
    # Preserve old OVER/team archive identities; new outcomes must not collide.
    return base if (scope, direction) == ("team", "over") else f"{base}|{scope}|{direction}"


def selection_quotes(item):
    direction = item.get("direction", "over")
    result = []
    for quote in (item.get("market_data") or {}).get("quotes") or []:
        odd = quote.get(direction + "_odd")
        if isinstance(odd, (int, float)) and math.isfinite(odd) and odd > 1:
            result.append(dict(quote, selected_odd=odd))
    return result


def quote_text(item):
    quotes = selection_quotes(item)
    if not quotes:
        return "Brak notowania wybranego wariantu."
    prices = [q["selected_odd"] for q in quotes]
    price = f"{min(prices):.2f}" if min(prices) == max(prices) else f"{min(prices):.2f}–{max(prices):.2f}"
    names = sorted({str(q.get("bookmaker") or "nieznany") for q in quotes}, key=str.casefold)
    names_text = ", ".join(names[:3]) + (f" i {len(names)-3} innych" if len(names) > 3 else "")
    return f"Kursy w API: {price}. Źródła notowań: {names_text}."


def sts_availability(item):
    """A missing provider quote is not proof of STS unavailability."""
    quotes = selection_quotes(item)
    direct = any(str(q.get("bookmaker") or "").strip().casefold() == "sts" for q in quotes)
    if direct:
        return {"status": "verified_quote", "preference": 3,
                "label": "STS: dokładny wariant ma notowanie w danych API."}
    if quotes and item.get("market") in {"team_goals", "corners"}:
        return {"status": "unverified_common_market", "preference": 2,
                "label": "Gole/rożne: dokładny wariant ma notowania. Dostępność w STS niepotwierdzona."}
    if quotes:
        return {"status": "unverified_specialist_market", "preference": 1,
                "label": "Statystyka szczegółowa: dokładny wariant ma notowania. Sprawdź linię i zasady rozliczenia w STS."}
    return {"status": "unknown", "preference": 0,
            "label": "Dostępność niepotwierdzona: brak dokładnej linii w danych kursowych. Sprawdź STS."}


def rank_positions(candidates, floor):
    """Rank quoted outcomes at final >= floor, without quantity or status gates."""
    result = []
    for old in candidates:
        score = old.get("final_assessment_pct")
        if not isinstance(score, (int, float)) or not math.isfinite(score) or score < floor:
            continue
        if not selection_quotes(old):
            continue
        item = dict(old)
        item["sts_availability"] = {"status":"not_evaluated","preference":0,"label":"Bez dopasowywania do STS i Superbet."}
        result.append(item)
    result.sort(key=lambda x: (
        -float(x["final_assessment_pct"]),
        -float(x.get("api_pure_pct") or 0),
        candidate_key(x),
    ))
    return result
