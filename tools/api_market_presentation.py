"""Read-only match grouping shared by API reports; never changes predictions."""
from datetime import datetime, timezone


def practical_shortlist(positions, limit=None, min_odd=1.20, max_per_match=3, min_score=67.0):
    """Display-only shortlist; original rankings and archives remain untouched."""
    from api_market_policy import selection_quotes
    ranked = sorted(positions, key=lambda x: (-float(x.get("final_assessment_pct") or 0), str(x.get("fixture_id"))))
    selected, counts, seen_families = [], {}, set()
    for item in ranked:
        odds = [q["selected_odd"] for q in selection_quotes(item)]
        if (float(item.get("final_assessment_pct") or 0) < min_score or not odds
                or max(odds) < min_odd or counts.get(item["fixture_id"], 0) >= max_per_match):
            continue
        # Same fixture, team, market, scope and direction with a different
        # threshold is an overlapping bet, not an independent proposal.
        family = (item.get("fixture_id"), item.get("team_id"),
                  item.get("market"), item.get("market_scope", "team"),
                  item.get("direction", "over"))
        if family in seen_families:
            continue
        seen_families.add(family)
        selected.append(item)
        counts[item["fixture_id"]] = counts.get(item["fixture_id"], 0) + 1
        if limit is not None and len(selected) >= limit:
            break
    return selected

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



def fouls_under_watchlist(payload, *, min_odd=1.50, max_odd=2.00, limit=12):
    """Read-only, independent fouls UNDER band; keep the original ranking intact.

    The background contains rejected scores too. All such rows are marked
    observational in the report rather than quietly promoted to official picks.
    The best quote must belong to the requested range and be dated before kickoff.
    """
    import math
    from api_market_policy import selection_quotes

    ranked = payload.get("background_candidates") or payload.get("top_positions") or []
    selected = {}
    report_date = payload.get("date")
    for item in ranked:
        if item.get("market") != "fouls" or item.get("direction") != "under":
            continue
        try:
            score = float(item.get("final_assessment_pct"))
            kickoff = datetime.fromisoformat(str(item["kickoff"]).replace("Z", "+00:00"))
            if (not math.isfinite(score) or kickoff.tzinfo is None
                    or kickoff.astimezone(ZoneInfo("Europe/Warsaw")).date().isoformat() != report_date):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        eligible = []
        for quote in selection_quotes(item):
            odd = quote["selected_odd"]
            if not min_odd <= odd <= max_odd:
                continue
            timestamp = quote.get("provider_updated_at")
            if not timestamp:
                continue
            try:
                stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp > kickoff:
                    continue
            except ValueError:
                continue
            eligible.append(quote)
        if not eligible:
            continue
        offered = max(eligible, key=lambda q: q["selected_odd"])
        family = (item.get("fixture_id"), item.get("market_scope", "team"),
                  item.get("team_id") if item.get("market_scope", "team") == "team" else None)
        candidate = {"item": item, "quote": offered, "score": score}
        previous = selected.get(family)
        if previous is None or (score, offered["selected_odd"]) > (previous["score"], previous["quote"]["selected_odd"]):
            selected[family] = candidate

    rows = sorted(selected.values(), key=lambda r: (
        -r["score"], -r["quote"]["selected_odd"],
        str(r["item"].get("fixture_id", "")),
    ))
    return {"total": len(rows), "rows": rows[:limit]}

def grouped_markdown(payload, floor, *, xg_snapshot=None):
    positions = payload.get("top_positions") or []
    groups = group_positions(positions)
    from api_market_policy import quote_text
    from pitchapi_market_validation import review_position
    shortlist = practical_shortlist(positions)
    fouls_watch = fouls_under_watchlist(payload)
    lines = [f"# API Market Scan - {payload['date']} - według meczów", "",
        f"Mecze: {len(groups)}. Typy: {len(positions)}. Próg oceny końcowej: {floor:g}/100. Bez limitu pozycji.",
        "Mecze według godziny rozpoczęcia w Polsce. Pod każdym meczem wszystkie jego typy w kolejności z rankingu API.",
        "API PURE to pokrycie historyczne; ocena końcowa uwzględnia próbę, rozgrywki, rynek i dostępny kontekst. Ocena /100 nie jest skalibrowanym prawdopodobieństwem.",
        "Bez dopasowywania do STS i Superbet. Kursy to wyłącznie notowania od dostawcy API.",
        "Żółte kartki to odrębna statystyka; nie zastępują liczby/punktów kartek z uwzględnieniem czerwonych.",
        "PitchAPI dla rynków bramkowych: poglądowa analiza jakości poprzednich okazji. Nie zmienia typów, ocen /100 ani prawdopodobieństw.", "",
        f"Odczyt notowań: {payload.get('generated_at_utc') or payload.get('publication', {}).get('captured_at_utc')} (UTC).",
        f"Wersja prognozy: `{payload.get('publication', {}).get('id', '-')}`", ""]
    errors = (payload.get("market_overlay") or {}).get("odds_errors") or []
    if errors:
        lines += [f"Uwaga: pobranie notowań nie powiodło się dla {len(errors)} meczów; lista może być niepełna.", ""]
    lines += [f"## LISTA GŁÓWNA — {len(shortlist)} wariantów", "Kurs API od 1,20; ocena co najmniej 67/100; maksymalnie 3 propozycje na mecz; bez powtarzania tej samej statystyki, drużyny i kierunku dla różnych linii. Bez limitu łącznej liczby meczów. Filtr prezentacji, nie zmiana oceny ani rekomendacja obstawiania.", ""]
    for item in shortlist:
        review = review_position(item, xg_snapshot)
        annotation = f" | {review['label']}" if review and review['status'] not in ('no_data', 'insufficient') else ""
        lines.append(f"- {item['home']} – {item['away']}: {item['selection']} | ocena {item['final_assessment_pct']:.1f}/100 | {quote_text(item)}{annotation}")
    if not shortlist:
        lines.append("Brak pozycji spełniających dodatkowe warunki listy praktycznej.")
    lines += ["", "## 🔎 OSOBNA SEKCJA: FAULE UNDER | KURS 1,50–2,00",
        "Niezależna lista obserwacyjna, poza głównym TOP. Obejmuje także kandydatury poniżej progu 67/100, jeżeli znajdują się w danych źródłowych. NIE oznacza KB PLAY, wartości dodatniej ani potwierdzonej oferty STS/Superbet.",
        f"Rynki: faule PONIŻEJ wybranej linii, dokładny zapisany kurs 1,50–2,00. Rodzin po usunięciu nakładających się linii: {fouls_watch['total']}; pokazano: {len(fouls_watch['rows'])}.", ""]
    for found in fouls_watch["rows"]:
        item, quote = found["item"], found["quote"]
        status = "POZA PROGIEM (TEST)" if found["score"] < floor else "OBSERWUJ (API)"
        when = str(quote.get("provider_updated_at") or "czas nieznany")
        lines.append(
            f"- {kickoff_time(item)} {item['home']} – {item['away']}: **{item['selection']}** "
            f"| **{float(quote['selected_odd']):.2f}** ({quote.get('bookmaker') or 'dostawca nieznany'}; notowanie {when}) "
            f"| ocena {found['score']:.1f}/100 | **{status}**"
        )
    if not fouls_watch["rows"]:
        lines.append("BRAK: w zapisanym skanie nie ma pasujących, dokładnie kwotowanych linii fauli UNDER.")
    lines += ["", "Uwaga: różne linie z jednego meczu są powiązane. Kurs to zapis API, nie aktualna oferta bukmachera.", ""]

    lines += ["", "## PEŁNE ARCHIWUM — wszystkie zakwalifikowane warianty według meczów", ""]
    for index, items in enumerate(groups, 1):
        first = items[0]
        lines += [f"## {index}. {first['home']} - {first['away']}",
            f"{kickoff_time(first)} Polska | {first['competition']} | Liczba typów: {len(items)}", "",
            "| Typ | API PURE | Ocena /100 | Kursy i dostępność | Komentarz |",
            "| --- | ---: | ---: | --- | --- |"]
        for item in items:
            review = review_position(item, xg_snapshot)
            commentary = item.get('final_comment') or item.get('market_comment') or ""
            if review and review['status'] not in ('no_data', 'insufficient'):
                commentary = (commentary + " " + review['label']).strip()
            cells = [item['selection'], f"{item['api_pure_pct']:.1f}%", f"{item['final_assessment_pct']:.1f}",
                quote_text(item), commentary]
            lines.append("| " + " | ".join(markdown_cell(cell) for cell in cells) + " |")
        lines.append("")
    if not positions:
        lines += ["Brak kwotowanych wariantów z oceną od ustalonego progu.", ""]
    return "\n".join(lines)
