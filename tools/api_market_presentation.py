"""Read-only match grouping shared by API reports; never changes predictions."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def kickoff_time(item):
    value = datetime.fromisoformat(item["kickoff"].replace("Z", "+00:00"))
    return value.astimezone(ZoneInfo("Europe/Warsaw")).strftime("%H:%M")


def group_positions(positions):
    """Keep every row and its within-match ranking, then order matches by start."""
    groups = {}
    for item in positions:
        groups.setdefault(item["fixture_id"], []).append(item)
    return sorted(groups.values(), key=lambda items: (
        datetime.fromisoformat(items[0]["kickoff"].replace("Z", "+00:00")).astimezone(timezone.utc),
        str(items[0].get("home", "")).casefold(),
        str(items[0].get("away", "")).casefold(),
        str(items[0]["fixture_id"]),
    ))


def markdown_cell(value):
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def grouped_markdown(payload, floor):
    positions = payload.get("top_positions") or []
    groups = group_positions(positions)
    from api_market_policy import quote_text
    lines = [f"# API Market Scan - {payload['date']} - według meczów", "",
        f"Mecze: {len(groups)}. Typy: {len(positions)}. Próg oceny końcowej: {floor:g}/100. Bez limitu pozycji.",
        "Mecze według godziny rozpoczęcia w Polsce. Pod każdym meczem wszystkie jego typy w kolejności z rankingu API.",
        "API PURE to pokrycie historyczne; ocena końcowa uwzględnia próbę, rozgrywki, rynek i dostępny kontekst. Ocena /100 nie jest skalibrowanym prawdopodobieństwem.",
        "Notowania pochodzą od wymienionych bukmacherów. Dostępność i kurs w STS pozostają niepotwierdzone bez notowania STS.",
        "Żółte kartki to odrębna statystyka; nie zastępują liczby/punktów kartek z uwzględnieniem czerwonych.", "",
        f"Odczyt notowań: {payload.get('generated_at_utc') or payload.get('publication', {}).get('captured_at_utc')} (UTC).",
        f"Wersja prognozy: `{payload.get('publication', {}).get('id', '-')}`", ""]
    errors = (payload.get("market_overlay") or {}).get("odds_errors") or []
    if errors:
        lines += [f"Uwaga: pobranie notowań nie powiodło się dla {len(errors)} meczów; lista może być niepełna.", ""]
    for index, items in enumerate(groups, 1):
        first = items[0]
        lines += [f"## {index}. {first['home']} - {first['away']}",
            f"{kickoff_time(first)} Polska | {first['competition']} | Liczba typów: {len(items)}", "",
            "| Typ | API PURE | Ocena /100 | Kursy i dostępność | Komentarz |",
            "| --- | ---: | ---: | --- | --- |"]
        for item in items:
            availability = (item.get("sts_availability") or {}).get("label", "STS: niepotwierdzone.")
            cells = [item['selection'], f"{item['api_pure_pct']:.1f}%", f"{item['final_assessment_pct']:.1f}",
                quote_text(item) + " " + availability, item.get('final_comment') or item.get('market_comment') or ""]
            lines.append("| " + " | ".join(markdown_cell(cell) for cell in cells) + " |")
        lines.append("")
    if not positions:
        lines += ["Brak kwotowanych wariantów z oceną od ustalonego progu.", ""]
    return "\n".join(lines)
