"""Concise Polish report from actual research artifacts, with cohort validation.

Run from any directory; this script does not fit models or create probabilities.
The complete forecast matrix stays in JSON and the separate full research PDF.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from github_models.research_pdf import MARKETS, _validate
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("summary_timezone_required")
    return result


def _cohort(queue, predictions, markets, comparison):
    fixtures = _validate(predictions, queue, markets)
    if comparison.get("total") != len(fixtures):
        raise ValueError("summary_coverage_cohort_mismatch")
    ids = [str(fid) for row in comparison.get("leagues", []) for fid in row["fixture_ids"]]
    if len(ids) != len(set(ids)) or set(ids) != set(fixtures):
        raise ValueError("summary_coverage_cohort_mismatch")
    cutoff = _utc(predictions["generated_at_utc"])
    if _utc(comparison["as_of_utc"]) != cutoff:
        raise ValueError("summary_coverage_cutoff_mismatch")
    if markets.get("generated_at_utc") and _utc(markets["generated_at_utc"]) != cutoff:
        raise ValueError("summary_market_cutoff_mismatch")
    for row in predictions["predictions"] + markets.get("markets", []):
        fixture = fixtures[str(row["fixture_id"])]
        if _utc(row["frozen_at_utc"]) != cutoff or cutoff >= _utc(fixture["kickoff_utc"]):
            raise ValueError("summary_forecast_not_original_prematch")
        if row.get("kickoff_utc") and _utc(row["kickoff_utc"]) != _utc(fixture["kickoff_utc"]):
            raise ValueError("summary_forecast_kickoff_mismatch")
    if sum(row["total"] for row in comparison["leagues"]) != len(fixtures):
        raise ValueError("summary_coverage_denominator_mismatch")
    return fixtures


def _math(predictions, markets):
    errors = [abs(math.fsum(row[key] for key in ("p_home", "p_draw", "p_away")) - 1)
              for row in predictions["predictions"]]
    groups = defaultdict(dict)
    curves = defaultdict(list)
    for row in markets.get("markets", []):
        key = (str(row["fixture_id"]), row["model_id"], row["market"], float(row["line"]))
        groups[key][row["selection"]] = row["probability"]
        if row["selection"] == "over":
            curves[key[:3]].append((float(row["line"]), row["probability"]))
    if any(set(group) != {"over", "under"} for group in groups.values()):
        raise ValueError("summary_incomplete_market_pair")
    complements = [abs(math.fsum(group.values()) - 1) for group in groups.values()]
    if any(right[1] > left[1] + 1e-6
           for curve in curves.values()
           for left, right in zip(sorted(curve), sorted(curve)[1:])):
        raise ValueError("summary_nonmonotone_market_probabilities")
    return dict(one_x_two=len(errors), event_rows=len(markets.get("markets", [])),
                event_pairs=len(groups), max_1x2_sum_error=max(errors, default=0),
                max_complement_error=max(complements, default=0))


def _value(value):
    return "nie przekazano" if value is None else str(value)


def _details(value):
    if isinstance(value, dict):
        return "; ".join(str(key) + ": " + _details(item) for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_details(item) for item in value)
    return _value(value)


def _observations(predictions):
    grouped = defaultdict(list)
    for row in predictions["predictions"]:
        grouped[str(row["fixture_id"])].append(row)
    candidates = []
    for fid, forecasts in grouped.items():
        directions = [max(range(3), key=lambda i: row[("p_home", "p_draw", "p_away")[i]])
                      for row in forecasts]
        if len({row["model_id"] for row in forecasts}) < 2 or len(set(directions)) != 1:
            continue
        direction = directions[0]
        supplied = [row[("p_home", "p_draw", "p_away")[direction]] for row in forecasts]
        candidates.append((min(supplied), fid, direction, forecasts))
    return sorted(candidates, key=lambda row: (-row[0], row[1]))[:5]


def build(queue, predictions, markets, comparison, verification, output):
    fixtures = _cohort(queue, predictions, markets, comparison)
    math_audit = _math(predictions, markets)
    fonts = Path("/usr/share/fonts/truetype/dejavu")
    for name, filename in (("SummarySans", "DejaVuSans.ttf"), ("SummaryBold", "DejaVuSans-Bold.ttf")):
        if not (fonts / filename).is_file():
            raise ValueError("summary_polish_font_missing")
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    styles = {
        "body": ParagraphStyle("SummaryBody", fontName="SummarySans", fontSize=9, leading=12.4, spaceAfter=6),
        "small": ParagraphStyle("SummarySmall", fontName="SummarySans", fontSize=8, leading=10.7, spaceAfter=4),
        "title": ParagraphStyle("SummaryTitle", fontName="SummaryBold", fontSize=17, leading=22, spaceAfter=11),
        "head": ParagraphStyle("SummaryHead", fontName="SummaryBold", fontSize=11.4, leading=15,
                               spaceBefore=12, spaceAfter=7, keepWithNext=True),
        "sub": ParagraphStyle("SummarySub", fontName="SummaryBold", fontSize=9.4, leading=12.5,
                              spaceBefore=7, spaceAfter=5, keepWithNext=True),
    }
    p = lambda value, style="body": Paragraph(escape(str(value)), styles[style])
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=36, rightMargin=36,
                                 topMargin=34, bottomMargin=37,
                                 title="KB Score — końcowy raport badawczy", author="KB Score")

    def table(rows, widths):
        result = Table([[p(cell, "small") for cell in row] for row in rows], colWidths=widths,
                       repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eef5")),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#99adbf")),
            ("LINEBELOW", (0, 1), (-1, -1), .2, colors.HexColor("#dae2e8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return result

    supplied = predictions["predictions"]
    forecasts_by_model = Counter(row["model_id"] for row in supplied)
    fixture_count = len({str(row["fixture_id"]) for row in supplied})
    story = [p("KB SCORE | RAPORT KOŃCOWY", "title"),
             p("Badawcza identyfikacja lig i drużyn — stan źródeł i prognoz"),
             p("PROGNOZY NIEKALIBROWANE. Nie są potwierdzonymi okazjami bukmacherskimi ani rekomendacjami stawek.", "sub"),
             p("Cutoff UTC: " + predictions["generated_at_utc"], "small"),
             p("Kolejka: " + str(len(fixtures)) + " meczów; rzeczywiście zapisane prognozy 1X2: "
               + str(len(supplied)) + " na " + str(fixture_count) + " meczów; rynki zdarzeń: "
               + str(math_audit["event_rows"]) + " pozycji.")]

    story.append(p("1. Wynik naprawy i porównanie pokrycia", "head"))
    story.append(p("Naprawa obejmuje wspólne rozpoznawanie lig, krajów i drużyn w prognozach, audytach i rozliczeniach. "
                   "Rozgrywki o tych samych nazwach rozdzielają zweryfikowane identyfikatory i kraje; aliasy drużyn są jawne. "
                   "Niejednoznaczne dopasowania i sprzeczne identyfikatory pozostają zablokowane."))
    if verification.get("thresholds_unchanged"):
        story.append(p("Dołączona weryfikacja potwierdza zachowanie dotychczasowych progów jakości.", "small"))
    if verification.get("noNwrites") is True or verification.get("n_counter_writes") == 0:
        story.append(p("Dołączona weryfikacja potwierdza brak zapisu nowych obserwacji do liczników N.", "small"))
    story.append(p("Wszystkie kolumny poniżej odnoszą się do dokładnie tych samych identyfikatorów spotkań i tego samego cutoff. "
                   "Przed/original oznacza stary kod i oryginalny zakres historii, jeżeli został przekazany. "
                   "Przed/ta sama historia izoluje wpływ identyfikacji: stary i nowy kod otrzymują tę samą rozszerzoną historię. "
                   "Gotowość historyczna modelu nie jest dowodem udanego dopasowania ani kalibracji."))
    totals = [["Wariant", "Tożsamość", "Gotowe Elo", "Historia DC"]]
    for key, label in (("before_original_history", "Przed / original"),
                       ("before_same_history", "Przed / ta sama historia"), ("after", "Po naprawie")):
        state = comparison.get("summary", {}).get(key)
        totals.append([label] + ([str(state.get(metric, "—")) for metric in
                                  ("identity_ready", "elo_ready", "dixon_coles_history_ready")]
                                 if state else ["nie przekazano"] * 3))
    story.append(table(totals, [220, 96, 96, 100]))
    story.append(p("Rzeczywiste prognozy według modelu: " + "; ".join(f"{name}: {count}" for name, count in sorted(forecasts_by_model.items()))
                   + ". Liczb gotowości i zapisanych prognoz nie należy utożsamiać.", "small"))
    market_counts = Counter(row["market"] for row in markets.get("markets", []))
    story.append(p("Zapisane pozycje rynków zdarzeń: " + "; ".join(MARKETS[name] + ": " + str(market_counts[name])
                   for name in ("goals", "cards", "fouls", "corners")) + ".", "small"))
    story.append(p("Kwalifikowana historia wyników: " + _value(comparison.get("eligible_history_rows"))
                   + "; rekordy źródłowych statystyk zdarzeń: " + _value(comparison.get("event_history_rows"))
                   + ". Brak kartki, faulu lub rożnego w źródle pozostaje brakiem, a nie zerem.", "small"))
    if comparison.get("started_fixtures"):
        story.append(p("W mianowniku pozostało " + str(comparison["started_fixtures"])
                       + " spotkań, które rozpoczęły się do cutoff. Zostały wyłączone jednakowo w obu wariantach.", "small"))

    story.append(p("2. Jak czytać pięć grup rynków", "head"))
    interpretation = [
        ["1X2", "1: gospodarze, X: remis, 2: goście. Trzy wartości jednego modelu sumują się do 100%. Różne modele mogą się różnić."],
        ["Bramki", "Suma bramek obu drużyn. Over 2,5 oznacza co najmniej 3; Under 2,5 oznacza najwyżej 2."],
        ["Żółte kartki", "Suma kolumn HY/AY. Nie obejmuje automatycznie czerwonych kartek ani zasad punktowych konkretnego bukmachera."],
        ["Faule", "Suma fauli obu drużyn z dostępnych historycznych obserwacji; brak statystyk nie jest zastępowany szacunkiem."],
        ["Rożne", "Suma rzutów rożnych obu drużyn; dla tej samej linii połówkowej Over i Under są dopełnieniami."],
    ]
    story.append(table([["Rynek", "Interpretacja"]] + interpretation, [95, 417]))
    story.append(p("N liga / gospodarze / goście opisuje próbę dla danego rynku. Większa próba nie potwierdza sama w sobie trafności. "
                   "Linie całkowite wymagające zwrotu są poza tym kontraktem. Wyniki dotyczą definicji źródła i regulaminowego zakresu modelu; "
                   "nie są automatycznym rozliczeniem oferty bukmachera. Brak kursów i walidacji poza próbą uniemożliwia potwierdzenie przewagi nad rynkiem."))

    story.append(p("3. Wybrane obserwacje do dalszej analizy", "head"))
    story.append(p("Wybór obejmuje maksymalnie pięć spotkań, dla których co najmniej dwa dostarczone modele wskazują ten sam najbardziej prawdopodobny kierunek. "
                   "Kolejność wynika z najmniejszej dostarczonej oceny tego kierunku wśród modeli; nie jest rankingiem opłacalności. "
                   "Nie obliczono nowej uśrednionej prognozy ani wartości zakładu.", "small"))
    events_by_fixture = defaultdict(list)
    for row in markets.get("markets", []):
        events_by_fixture[str(row["fixture_id"])].append(row)
    observations = _observations(predictions)
    for _, fid, direction, forecasts in observations:
        fixture = fixtures[fid]
        chunk = [p(fixture["home"] + " — " + fixture["away"], "sub"),
                 p(str(fixture.get("league", "")) + " | start UTC: " + fixture["kickoff_utc"], "small"),
                 p("Zgodny kierunek modeli: " + ("1 — gospodarze", "X — remis", "2 — goście")[direction]
                   + ". Uzasadnienie dotyczy wyłącznie zgodności dostarczonych modeli.", "small")]
        for row in forecasts:
            chunk.append(p(row["model_id"] + ": 1 / X / 2 = " + " / ".join(f"{100*row[key]:.1f}%" for key in
                            ("p_home", "p_draw", "p_away")) + "; N treningowe: " + _value(row.get("training_matches")), "small"))
        for market, preferred in (("goals", 2.5), ("cards", 3.5), ("fouls", 22.5), ("corners", 9.5)):
            rows = [row for row in events_by_fixture[fid] if row["market"] == market and row["selection"] == "over"]
            if not rows:
                continue
            row = min(rows, key=lambda item: (abs(float(item["line"]) - preferred), item["line"]))
            chunk.append(p(MARKETS[market] + f": powyżej {row['line']} = {100*row['probability']:.1f}%; N liga / G / W: "
                           + " / ".join(_value(row.get(key)) for key in ("league_n", "home_n", "away_n")), "small"))
        story.append(KeepTogether(chunk))
    if not observations:
        story.append(p("Brak spotkań spełniających powyższy warunek. Nie dodano zastępczych propozycji."))

    story.append(p("4. Pokrycie osobno dla każdej ligi", "head"))
    story.append(p("M: liczba spotkań w kolejce; przed: stary kod i oryginalna historia; ta sama: stary kod z rozszerzoną historią; "
                   "Elo po oraz DC po: gotowość historyczna po naprawie. Pełny identyfikator ligi i kraj oddzielają rozgrywki o wspólnych nazwach. "
                   "Zero jest jawnym brakiem kwalifikacji, a nie prognozą.", "small"))
    league_rows = [["Liga", "Kraj", "ID PitchAPI", "M", "Przed", "Ta sama", "Elo po", "DC po"]]
    for row in sorted(comparison["leagues"], key=lambda item: (-item["after"]["identity_ready"],
                      ", ".join(item.get("canonical_leagues") or item["raw_labels"]), item["league_id"])):
        name = ", ".join(row.get("canonical_leagues") or row.get("raw_labels") or ["niezweryfikowana"])
        old = row.get("before_original_history")
        league_rows.append([name, ", ".join(row.get("countries", [])) or "—", row["league_id"], row["total"],
            old["elo_ready"] if old else "—", row["before_same_history"]["elo_ready"],
            row["after"]["elo_ready"], row["after"]["dixon_coles_history_ready"]])
    story.append(table(league_rows, [171, 30, 58, 27, 42, 48, 38, 38]))

    story.append(p("5. Sprawdzenie matematyki i testy", "head"))
    math_rows = [["Sprawdzenie rzeczywistych plików", "Wynik"],
        ["Rozkłady 1X2 / wiersze rynków zdarzeń", str(math_audit["one_x_two"]) + " / " + str(math_audit["event_rows"])],
        ["Pary Over / Under", str(math_audit["event_pairs"])],
        ["Największy błąd sumy 1X2", f"{math_audit['max_1x2_sum_error']:.3g}"],
        ["Największy błąd dopełnienia Over / Under", f"{math_audit['max_complement_error']:.3g}"],
        ["Zakres [0,1], skończoność i monotoniczność linii", "PASS — sprawdzono wszystkie dostarczone prognozy"],
    ]
    story.append(table(math_rows, [330, 182]))
    reference_error = verification.get("math", {}).get("max_poisson_reference_error")
    if reference_error is not None:
        story.append(p("Największy podany błąd względem niezależnej referencji Poissona: " + str(reference_error)
                       + ". Wartość pochodzi z dołączonej weryfikacji źródłowych prognoz.", "small"))
    tests = verification.get("tests", verification.get("test_results"))
    story.append(p("Zapis testów: " + _details(tests), "small"))
    ci = verification.get("ci", verification.get("github_actions"))
    if isinstance(ci, list):
        for item in ci:
            story.append(p("GitHub Actions: " + _details(item), "small"))
    else:
        story.append(p("GitHub Actions: " + _details(ci), "small"))
    story.append(p("Poprawny rachunek prawdopodobieństw nie dowodzi kalibracji, trafności ani wspólnej spójności niezależnych modeli."))

    story.append(p("6. Ograniczenia i ślad projektu", "head"))
    story.append(p("Cutoff oznacza dostępność danych wejściowych. Czas obliczeń i publikacji artefaktu może być późniejszy; "
                   "sam ten raport nie potwierdza formalnej publikacji forward przed pierwszym gwizdkiem.", "small"))
    limits = verification.get("limitations", [])
    if isinstance(limits, str):
        limits = [limits]
    for item in limits:
        story.append(p("• " + str(item), "small"))
    if not limits:
        story.append(p("Nie przekazano osobnego rejestru ograniczeń. Same dostarczone pliki nie potwierdzają kalibracji, pełnego światowego kalendarza ani dostępności wszystkich statystyk.", "small"))
    story.append(p("Bazowa rewizja porównania: " + _value(comparison.get("baseline_commit")), "small"))
    story.append(p("Pełne prognozy, odrzucenia, prawdopodobieństwa i hashe wejść pozostają w dołączonych plikach JSON oraz pełnym aneksie prognoz. "
                   "Ten dokument jest skrótem i nie zastępuje źródłowych zamrożeń.", "small"))

    def footer(canvas, doc):
        canvas.setFont("SummarySans", 8)
        canvas.setFillColor(colors.HexColor("#506579"))
        canvas.drawString(36, 20, "KB Score | raport badawczy | prognozy niekalibrowane")
        canvas.drawRightString(A4[0] - 36, 20, "Strona " + str(doc.page))

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    if not out.is_file() or out.stat().st_size < 1000:
        raise ValueError("summary_pdf_not_created")
    return math_audit


def main():
    parser = argparse.ArgumentParser()
    for name in ("queue", "predictions", "markets", "comparison", "verification", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    result = build(load(args.queue), load(args.predictions), load(args.markets),
                   load(args.comparison), load(args.verification), args.output)
    print(json.dumps(dict(output=str(Path(args.output)), **result), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
