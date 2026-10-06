#!/usr/bin/env python3
"""Publish the complete API ranking; historical filename kept for workflow compatibility."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from api_market_policy import load_policy, quote_text, rank_positions, target_date
from datetime import datetime
from zoneinfo import ZoneInfo
from api_market_storage import archive_publication, atomic_write

TARGET = target_date(sys.argv[1] if len(sys.argv) > 1 else None)
PATH = Path("data/api_football/market_work") / f"{TARGET}.json"


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    policy = load_policy()
    candidates = payload.get("background_candidates") or []
    payload["top_positions"] = rank_positions(candidates, policy["publish_min_final_pct"])
    payload.setdefault("v3", {})["publication_policy"] = policy
    payload = archive_publication(payload, TARGET, policy)
    positions = payload["top_positions"]
    lines = [f"# API Market Scan - {TARGET}", "",
        f"Próg oceny końcowej: {policy['publish_min_final_pct']:g}. Bez limitu pozycji i bez limitu na mecz.",
        "API PURE to pokrycie historyczne; ocena końcowa uwzględnia próbę, rozgrywki, rynek i dostępny kontekst.",
        "Lista zawiera wyłącznie dokładnie kwotowane warianty: powyżej/poniżej, drużyna/cały mecz. Najpierw gole i rożne; w grupach malejąco ocena.",
        "Notowania pochodzą od bukmacherów wymienionych przy pozycji. Dostępność i kurs w STS pozostają niepotwierdzone bez notowania STS.",
        "Żółte kartki to odrębna statystyka; nie zastępują liczby/punktów kartek z uwzględnieniem czerwonych.", "",
        f"Odczyt notowań: {payload.get('generated_at_utc', payload['publication']['captured_at_utc'])} (UTC).",
        f"Wersja prognozy: `{payload['publication']['id']}`", ""]
    odds_errors = (payload.get("market_overlay") or {}).get("odds_errors") or []
    if odds_errors:
        lines += [f"Uwaga: pobranie notowań nie powiodło się dla {len(odds_errors)} meczów; lista może być niepełna.", ""]
    for index, item in enumerate(positions, 1):
        kickoff = datetime.fromisoformat(item["kickoff"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Warsaw")).strftime("%H:%M")
        lines += [f"## {index}. {item['selection']}",
            f"{kickoff} Polska | {item['home']} - {item['away']} ({item['competition']})",
            f"API PURE: {item['api_pure_pct']:.1f}% | Ocena końcowa: {item['final_assessment_pct']:.1f}/100",
            quote_text(item), item['sts_availability']['label'], item.get('final_comment', ''), ""]
    if not positions:
        lines += ["Brak kwotowanych wariantów z oceną od ustalonego progu. Nie zastępujemy ich liniami bez notowań.", ""]
    atomic_write(Path("reports/api_market_scan") / f"{TARGET}.md", "\n".join(lines))
    print(json.dumps({"date": TARGET, "background": len(candidates), "published": len(positions),
        "distinct_fixtures": len({x['fixture_id'] for x in positions}),
        "threshold": policy['publish_min_final_pct'], "prediction_id": payload['publication']['id'],
        "kb_n_effect": 0, "dev_n_effect": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
