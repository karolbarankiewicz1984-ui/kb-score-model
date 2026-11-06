"""Readable research PDF from supplied probabilities; never creates forecasts."""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Table, TableStyle

MARKETS = {"goals": "Bramki", "corners": "Rożne", "cards": "Żółte kartki", "fouls": "Faule"}
OUTCOMES = ("1 — gospodarze", "X — remis", "2 — goście")


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("pdf_invalid_probability")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("pdf_invalid_probability")
    return float(value)


def _validate(predictions, queue, events):
    fixtures = {}
    for fixture in queue["fixtures"]:
        key = str(fixture["fixture_id"])
        if key in fixtures:
            raise ValueError("pdf_duplicate_fixture")
        fixtures[key] = fixture
    seen = set()
    for row in predictions["predictions"]:
        key = (str(row["fixture_id"]), row["model_id"])
        if key[0] not in fixtures:
            raise ValueError("pdf_forecast_fixture_missing")
        if key in seen:
            raise ValueError("pdf_duplicate_forecast")
        seen.add(key)
        values = [_probability(row[k]) for k in ("p_home", "p_draw", "p_away")]
        if abs(math.fsum(values) - 1) > 1e-5:
            raise ValueError("pdf_probability_sum_invalid")
    groups = defaultdict(dict)
    for row in events.get("markets", []):
        if str(row["fixture_id"]) not in fixtures:
            raise ValueError("pdf_forecast_fixture_missing")
        if row["market"] not in MARKETS or row["selection"] not in ("over", "under"):
            raise ValueError("pdf_unknown_market")
        line = row["line"]
        if (isinstance(line, bool) or not isinstance(line, (int, float))
                or not math.isfinite(line) or line < 0 or line % 1 != .5):
            raise ValueError("pdf_non_binary_market_line")
        key = (str(row["fixture_id"]), row["model_id"], row["market"], float(line))
        if row["selection"] in groups[key]:
            raise ValueError("pdf_duplicate_event_forecast")
        groups[key][row["selection"]] = _probability(row["probability"])
    for values in groups.values():
        if len(values) == 2 and abs(math.fsum(values.values()) - 1) > 1e-5:
            raise ValueError("pdf_probability_sum_invalid")
    return fixtures


def _text(value):
    return escape(str(value))


def _samples(row):
    values = [row.get(k) for k in ("league_n", "home_n", "away_n")]
    if any(type(v) is not int or v < 0 for v in values):
        return "N: brak pełnej informacji"
    return "N liga / gospodarze / goście: " + " / ".join(map(str, values))


def build(predictions, queue, settlement, output, event_markets=None, coverage=None):
    """Render supplied research values; optional same-input coverage is not inferred.

    coverage.per_league rows: league, total, before_mapped, after_mapped.
    """
    events = event_markets or {}
    fixtures = _validate(predictions, queue, events)
    for name, filename in (("ResearchSans", "DejaVuSans.ttf"),
                           ("ResearchSansBold", "DejaVuSans-Bold.ttf")):
        path = Path("/usr/share/fonts/truetype/dejavu") / filename
        if not path.is_file():
            raise RuntimeError("DejaVuSans font required for Polish text")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyResearch", fontName="ResearchSans", fontSize=9, leading=13, spaceAfter=6))
    styles.add(ParagraphStyle(name="SmallResearch", fontName="ResearchSans", fontSize=8, leading=11, spaceAfter=4))
    styles.add(ParagraphStyle(name="TitleResearch", fontName="ResearchSansBold", fontSize=18, leading=24, spaceAfter=12))
    styles.add(ParagraphStyle(name="HeadResearch", fontName="ResearchSansBold", fontSize=12, leading=16, spaceBefore=14,
                              spaceAfter=8, keepWithNext=True))
    styles.add(ParagraphStyle(name="FixtureResearch", fontName="ResearchSansBold", fontSize=10, leading=14,
                              spaceBefore=9, spaceAfter=5, keepWithNext=True))
    body, small = styles["BodyResearch"], styles["SmallResearch"]
    para = lambda text, style=body: Paragraph(text, style)
    head = lambda text: para(text, styles["HeadResearch"])
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=35,
                            bottomMargin=37, title="KB Score — raport badawczy", author="KB Score")

    def table(rows, widths):
        obj = Table([[para(_text(cell), small) for cell in row] for row in rows],
                    colWidths=widths, repeatRows=1, hAlign="LEFT")
        obj.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3edf4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#9aacba")),
            ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#d8e1e7")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return obj

    markets = events.get("markets", [])
    by_fixture, by_events = defaultdict(list), defaultdict(list)
    for row in predictions["predictions"]:
        by_fixture[str(row["fixture_id"])].append(row)
    for row in markets:
        by_events[str(row["fixture_id"])].append(row)
    items = [para("KB SCORE | RAPORT BADAWCZY", styles["TitleResearch"]),
             para("Prognozy niekalibrowane. Nie są potwierdzonymi okazjami bukmacherskimi ani rekomendacjami stawek."),
             para("Cutoff prognoz UTC: " + _text(predictions.get("generated_at_utc", "brak"))),
             para("Daty kolejki: " + _text(", ".join(queue.get("dates", [])) or "nie podano"), small),
             para(f"Kolejka: {len(fixtures)} meczów | 1X2: {len(by_fixture)} meczów, "
                  f"{len(predictions['predictions'])} prognoz modeli | rynki dodatkowe: {len(markets)} pozycji.")]
    if queue.get("missing_dates") or queue.get("invalid_dates"):
        items.append(para("Niepełne źródła. Brakujące daty: " + _text(", ".join(queue.get("missing_dates", [])) or "brak")
                          + "; odrzucone daty: " + _text(", ".join(queue.get("invalid_dates", [])) or "brak") + "."))
    items.extend([head("1. Jak czytać prognozy"),
        para("1 oznacza wygraną gospodarzy, X remis, 2 wygraną gości po regulaminowym czasie gry. "
             "Trzy prawdopodobieństwa jednego modelu sumują się do 100%; zaokrąglenie tabeli może zmienić sumę o 0,1 p.p."),
        para("Bramki, rożne, żółte kartki i faule dotyczą sumy obu drużyn. Powyżej 2,5 oznacza co najmniej 3 zdarzenia; "
             "poniżej 2,5 — najwyżej 2. Dla tej samej linii połówkowej prawdopodobieństwa obu stron sumują się do 100%. "
             "Kartki oznaczają wyłącznie żółte kartki z kolumn HY/AY; regulamin bukmachera może się różnić."),
        para("N liga / gospodarze / goście to liczba dostępnych meczów historycznych wykorzystanych dla danego rynku. "
             "Większa próba ogranicza przypadkowość, lecz sama nie potwierdza kalibracji. Model Poissona opiera się na "
             "historycznych sumach zdarzeń z ograniczeniem wpływu małych prób; nie opisuje całej niepewności meczu."),
        para("Elo korzysta z wyników historycznych; Dixon-Coles opisuje wyniki bramkowe. Rozbieżność między modelami "
             "jest sygnałem niepewności. Poprawna suma prawdopodobieństw nie dowodzi trafności ani kalibracji. "
             "Brak kursów i walidacji poza próbą uniemożliwia potwierdzenie przewagi nad rynkiem."),
        para("Raport opisuje dane dostępne w podanym cutoff. Dat historycznych nie należy czytać jako aktualnej oferty. "
             "Brak danych lub blokada pozostają jawne; raport nie dopisuje brakujących prognoz.")])
    items.append(head("2. Pokrycie i jakość źródeł"))
    coverage_rows = (coverage or {}).get("per_league", [])
    if isinstance(coverage_rows, dict):
        coverage_rows = [dict(value, league=key) for key, value in coverage_rows.items()]
    if coverage_rows:
        items.append(para("Porównanie identyfikacji na tej samej puli spotkań. Dopasowanie nazw nie oznacza "
                          "gotowości modelu ani przejścia progów jakości."))
        rows = [["Liga", "Mecze", "Dopasowane przed", "Dopasowane po"]]
        rows.extend([[r["league"], r["total"], r["before_mapped"], r["after_mapped"]] for r in coverage_rows])
        items.append(table(rows, [255, 65, 102, 102]))
    else:
        items.append(para("Nie przekazano porównania pokrycia przed/po. Liczby prognoz opisują tylko dostarczoną "
                          "kolejkę, bez domniemania kompletnego kalendarza."))
    items.append(para("Źródła: zachowane migawki PitchAPI oraz obserwowana historia football-data.co.uk. "
                      "Odrzucone nazwy, konflikty identyfikatorów, brak historii i modele niegotowe pozostają blokadami."))

    items.append(head("3. Wybrane obserwacje do dalszej analizy"))
    ranked = []
    for fid, forecasts in by_fixture.items():
        values = [[r[k] for k in ("p_home", "p_draw", "p_away")] for r in forecasts]
        choices = [tuple(i for i, p in enumerate(v) if abs(p - max(v)) <= 1e-12) for v in values]
        agreed = len(set(choices)) == 1 and len(choices[0]) == 1
        ranked.append((not (agreed and len(forecasts) > 1),
                       fixtures[fid].get("kickoff_utc", ""), fid, choices))
    for _, _, fid, choices in sorted(ranked)[:5]:
        f, forecasts = fixtures[fid], by_fixture[fid]
        chunk = [para(_text(f["home"]) + " — " + _text(f["away"]), styles["FixtureResearch"])]
        if len(set(choices)) == 1 and len(choices[0]) == 1:
            choice = choices[0][0]
            vals = [r[("p_home", "p_draw", "p_away")[choice]] * 100 for r in forecasts]
            label = "Zgodność kierunku " if len(forecasts) > 1 else "Jedyny dostępny model wskazuje "
            chunk.append(para(label + _text(OUTCOMES[choice]) + "; P(model): "
                              + (f"{min(vals):.1f}–{max(vals):.1f}%" if len(vals) > 1 else f"{vals[0]:.1f}%")
                              + ". To opis modeli, bez oceny opłacalności.", small))
        else:
            chunk.append(para("Brak jednego zgodnego kierunku: modele różnią się lub najwyższe wartości są równe. To przemawia za ostrożną "
                              "interpretacją; żadnego kierunku nie uznano za potwierdzoną przewagę.", small))
        counts = [r["training_matches"] for r in forecasts if type(r.get("training_matches")) is int]
        if counts:
            chunk.append(para("Podana próba treningowa 1X2: " + _text(" / ".join(map(str, counts))) + " meczów.", small))
        for market in MARKETS:
            available = [r for r in by_events.get(fid, []) if r["market"] == market and r["selection"] == "over"]
            if available:
                row = sorted(available, key=lambda r: (r["line"], r["model_id"]))[len(available) // 2]
                chunk.append(para(_text(MARKETS[market]) + " powyżej " + _text(row["line"]) + ": "
                                  + f"{row['probability'] * 100:.1f}%" + "; " + _text(_samples(row)) + ".", small))
                break
        items.append(KeepTogether(chunk))
    if not ranked:
        items.append(para("Brak dopuszczonych prognoz 1X2 do omówienia. Nie utworzono zastępczych propozycji."))
    else:
        items.append(para("Wybrano maksymalnie pięć spotkań, najpierw zgodny kierunek modeli, potem kolejność startu. "
                          "To nie jest ranking wartości zakładów.", small))

    items.append(head("4. Wszystkie prognozy 1X2"))
    for fid in sorted(by_fixture, key=lambda k: (fixtures[k].get("kickoff_utc", ""), k)):
        f = fixtures[fid]
        items.append(para(_text(f["home"]) + " — " + _text(f["away"]) + " | " + _text(f.get("league", "")),
                          styles["FixtureResearch"]))
        items.append(para("Start UTC: " + _text(f.get("kickoff_utc", "brak")), small))
        rows = [["Model (niekalibrowany)", "1", "X", "2"]]
        for row in by_fixture[fid]:
            rows.append([row["model_id"]] + [f"{row[k] * 100:.1f}%" for k in ("p_home", "p_draw", "p_away")])
        items.append(table(rows, [270, 85, 85, 84]))
    if not by_fixture:
        items.append(para("Brak dopuszczonych prognoz. Nie uzupełniono ich szacunkami."))

    items.append(head("5. Bramki, rożne, żółte kartki i faule"))
    for fid in sorted(by_events, key=lambda k: (fixtures[k].get("kickoff_utc", ""), k)):
        f = fixtures[fid]
        items.append(para(_text(f["home"]) + " — " + _text(f["away"]) + " | " + _text(f.get("league", "")),
                          styles["FixtureResearch"]))
        grouped = defaultdict(dict)
        for row in by_events[fid]:
            grouped[(row["market"], row["model_id"], row["line"])][row["selection"]] = row
        rows = [["Rynek / linia", "Powyżej", "Poniżej", "N: liga / dom / wyj."]]
        for (market, model, line), sides in sorted(grouped.items(), key=lambda item:
                (list(MARKETS).index(item[0][0]), item[0][2], item[0][1])):
            source = next(iter(sides.values()))
            n = [source.get(k) for k in ("league_n", "home_n", "away_n")]
            sample = " / ".join(map(str, n)) if all(type(v) is int and v >= 0 for v in n) else "brak informacji"
            rows.append([MARKETS[market] + " " + str(line),
                         f"{sides['over']['probability'] * 100:.1f}%" if "over" in sides else "brak",
                         f"{sides['under']['probability'] * 100:.1f}%" if "under" in sides else "brak", sample])
        items.append(table(rows, [175, 78, 78, 193]))
        items.append(para("Model: " + _text(", ".join(sorted({r["model_id"] for r in by_events[fid]})))
                          + ". Wszystkie prawdopodobieństwa niekalibrowane.", small))
    if not markets:
        items.append(para("Brak prognoz rynków dodatkowych spełniających progi danych. Braków nie zastępujemy szacunkami."))

    items.append(head("6. Rozliczenia i pozostałe blokady"))
    reports = settlement.get("reports", [])
    settled_rows = [r for report in reports for r in report.get("result", {}).get("settlements", [])]
    if not reports:
        settled_rows = settlement.get("settlements", [])
    statuses = Counter(r.get("status") for r in settled_rows)
    items.append(para(f"Przetworzone archiwa: {len(reports)} | rozliczone: {statuses.get('settled', 0)} | "
                      f"oczekujące: {statuses.get('pending', 0)} | niejednoznaczne: {statuses.get('ambiguous', 0)}."))
    settled = [r for r in settled_rows if r.get("status") == "settled"]
    valid_scores = all(all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
                      and math.isfinite(r[k]) and r[k] >= 0 for k in ("brier", "log_loss")) for r in settled)
    if settled and valid_scores:
        items.append(para("Brier (średnia): " + f"{math.fsum(r['brier'] for r in settled) / len(settled):.4f}"
                          + " | log loss (średnia): " + f"{math.fsum(r['log_loss'] for r in settled) / len(settled):.4f}" + "."))
        items.append(para("Niższe wartości oznaczają lepszy wynik probabilistyczny. To nie jest dowód kalibracji. "
                          "Różne archiwa mogą powtarzać mecz; liczby dotyczą prognoz, nie unikalnych spotkań.", small))
    else:
        items.append(para("Brak kompletnych, zweryfikowanych rozliczeń do obliczenia Brier i log loss."))
    reasons = Counter()
    for source in (predictions.get("blockers", []), events.get("blockers", [])):
        for row in source:
            reasons[str(row.get("reason", "unknown")).split(":", 1)[0]] += 1
    if not reasons:
        for key, value in predictions.get("blocker_summary", {}).items():
            reasons[key.split(": ", 1)[-1].split(":", 1)[0]] += value
    for reason, count in reasons.most_common(12):
        items.append(para(_text(reason) + ": " + _text(count), small))
    if not reasons:
        items.append(para("W przekazanych wynikach nie zapisano blokad; nie potwierdza to kompletności źródeł.", small))
    items.append(para("Status: badanie. MULTIMODEL produkcyjny, historyczne freeze i liczniki N pozostają poza tym raportem.", small))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("ResearchSans", 8)
        canvas.setFillColor(colors.HexColor("#526575"))
        canvas.drawString(36, 21, "KB Score | badanie | prognozy niekalibrowane")
        canvas.drawRightString(A4[0] - 36, 21, "Strona " + str(document.page))
        canvas.restoreState()

    doc.build(items, onFirstPage=footer, onLaterPages=footer)
    if not out.is_file() or out.stat().st_size < 1000:
        raise RuntimeError("pdf_not_generated")
    print("Generated research PDF:", out, out.stat().st_size, "bytes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-markets")
    parser.add_argument("--coverage")
    for name in ("predictions", "queue", "settlement", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    build(read(args.predictions), read(args.queue), read(args.settlement), args.output,
          read(args.event_markets) if args.event_markets else None,
          read(args.coverage) if args.coverage else None)


if __name__ == "__main__":
    main()
