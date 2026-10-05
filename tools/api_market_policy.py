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
    return f"{item['fixture_id']}|{item['team_id']}|{item['market']}|{float(item['line']):.1f}"


def sts_availability(item):
    """A missing provider quote is not proof of STS unavailability."""
    market = item.get("market_data") or {}
    quotes = market.get("quotes") or []
    direct = any(str(q.get("bookmaker") or "").strip().casefold() == "sts" for q in quotes)
    if direct:
        return {"status": "verified_quote", "preference": 3,
                "label": "STS: dokładna linia potwierdzona w notowaniu."}
    practical_lines = {"team_goals": {0.5, 1.5, 2.5},
                       "corners": {3.5, 4.5, 5.5, 6.5}, "yellow": {1.5, 2.5, 3.5}}
    usual_line = float(item.get("line", -1)) in practical_lines.get(item.get("market"), set())
    if usual_line and market.get("exact_line_available"):
        return {"status": "unverified_common_market", "preference": 2,
                "label": "Typowy rynek; linia dostępna u innych bukmacherów. Sprawdź STS."}
    if market.get("exact_line_available"):
        return {"status": "unverified_specialist_market", "preference": 1,
                "label": "Rynek specjalistyczny; linia jest u innych bukmacherów. STS do sprawdzenia."}
    return {"status": "unknown", "preference": 0,
            "label": "Dostępność niepotwierdzona: brak dokładnej linii w danych kursowych. Sprawdź STS."}


def rank_positions(candidates, floor):
    """The only score gate is final >= floor. Never cap, dedupe, or veto a signal."""
    result = []
    for old in candidates:
        score = old.get("final_assessment_pct")
        if not isinstance(score, (int, float)) or not math.isfinite(score) or score < floor:
            continue
        item = dict(old)
        item["sts_availability"] = sts_availability(item)
        result.append(item)
    result.sort(key=lambda x: (
        -x["sts_availability"]["preference"],
        -float(x["final_assessment_pct"]),
        -float(x.get("api_pure_pct") or 0),
        candidate_key(x),
    ))
    return result
