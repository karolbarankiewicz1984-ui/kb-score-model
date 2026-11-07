"""Unified A/B/C settlement audit PDF, with real sample sizes and limitations."""
import argparse
import json
from pathlib import Path
from github_models.abc_pdf_style import fonts, p, render, styles, table

MARKETS = ("1X2", "goals", "fouls", "cards", "corners")
LABELS = {"1X2":"Wynik 1X2", "goals":"Bramki", "fouls":"Faule",
          "cards":"Żółte kartki", "corners":"Rożne"}

def rate(row):
    return "brak próby" if not row or row.get("hit_rate") is None else "%.1f%%" % (100 * row["hit_rate"])

def score(value):
    return "brak" if value is None else "%.4f" % value

def build(data, output):
    fonts()
    st = styles()
    rows = {(row["variant"], row["market"]): row for row in data["summary"]}
    story = [
        p("MULTIMODEL GitHub V2 | Audyt A/B/C", st["title"]),
        p("Stan danych: " + str(data.get("as_of_utc") or "brak UTC"), st["sub"]),
        p("Rozliczamy wyłącznie potwierdzone wyniki. Nierozliczone zdarzenia "
          "NIE SĄ błędnymi prognozami. Wyniki mają charakter badawczy.", st["body"]),
        p("Zakres i integralność archiwów", st["head"]),
        p("Archiwa: " + str(data.get("archives_processed", "brak")) +
          " | Oryginalne wpisy: " + str(data.get("forecast_records", "brak")) +
          " | Unikalne propozycje: " + str(data.get("unique_candidate_records", "brak")) +
          " | Powtórzone migawki pominięte: " +
          str(data.get("duplicate_snapshots_suppressed", "brak")), st["body"]),
        p("Rewizje P: " + str(data.get("probability_revisions_observed", "brak")) +
          " | Sprzeczne rezultaty: " + str(data.get("conflicting_archive_outcomes", "brak")),
          st["small"]),
        p("A/B/C | wyniki rozliczenia", st["head"])
    ]
    summary = [["Filtr", "Rozlicz.", "Trafione", "Mecze", "Skut.", "Brier", "Log loss", "Nierozl."]]
    for variant in ("A", "B", "C"):
        r = rows.get((variant, "all"), {})
        summary.append([variant, str(r.get("settled", 0)), str(r.get("hits", 0)),
                        str(r.get("unique_fixtures", 0)), rate(r),
                        score(r.get("brier")), score(r.get("log_loss")),
                        str(r.get("unresolved", 0))])
    story.append(table(summary, [42, 69, 59, 58, 67, 64, 78, 86], st))
    story.append(p("Warianty nakładają się. Kilka propozycji z tego samego meczu "
                   "nie jest kilkoma niezależnymi spotkaniami. "
                   "Wyższa skuteczność wariantu C na małej próbie "
                   "nie oznacza potwierdzonej przewagi.", st["small"]))

    story.append(p("Porównanie według rynku", st["head"]))
    market_rows = [["Rynek", "A: trafne / rozlicz.", "B: trafne / rozlicz.", "C: trafne / rozlicz."]]
    for market in MARKETS:
        cols = []
        for variant in ("A", "B", "C"):
            r = rows.get((variant, market), {})
            n = r.get("settled", 0)
            cols.append((str(r.get("hits", 0)) + "/" + str(n) + " (" + rate(r) + ")")
                        if n else "brak rozliczeń")
        market_rows.append([LABELS[market]] + cols)
    story.append(table(market_rows, [118, 135, 135, 135], st))

    reasons = data.get("unresolved_reasons", {})
    story.append(p("Brakujące wyniki i przeszkody", st["head"]))
    if reasons:
        labels = [["Powód nierozliczenia", "Liczba"]]
        labels.extend([[str(reason), str(count)] for reason, count
                       in sorted(reasons.items(), key=lambda x: (-x[1], x[0]))[:10]])
        story.append(table(labels, [409, 114], st))
    else:
        story.append(p("Nie podano szczegółowych przyczyn nierozliczenia.", st["body"]))

    story.extend([
        p("Wnioski i dalszy pomiar", st["head"]),
        p("To zestawienie z zamrożonych prognoz i rzeczywistych wyników, "
          "nie ranking bukmacherski. Brier i log loss to miary trafności "
          "prawdopodobieństw (im niższe, tym lepiej); nie potwierdzają same "
          "w sobie kalibracji ani rentowności.", st["body"]),
        p("Brak potwierdzonych kursów exact-market i ROI. "
          "Do analizy opłacalności przyjmować tylko rzeczywiste kursy >= 1,20 "
          "zanotowane przed meczem. Nie dopisywać fikcyjnych notowań.", st["body"]),
        p("Bez automatycznej zmiany progów A=70%, B=75%, C=80%. "
          "Pierwszy przegląd decyzyjny po 100-150 unikalnych, poprawnie "
          "rozliczonych meczach. Pozostałe modele bez zmian.", st["small"]),
    ])
    render(story, output, "MULTIMODEL GitHub V2 | Audyt A/B/C")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    build(json.loads(Path(a.input).read_text(encoding="utf-8")), a.output)

if __name__ == "__main__":
    main()
