#!/usr/bin/env python3
"""Render all published API positions grouped by match, without changing scores."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from api_market_policy import load_policy, quote_text, target_date
from api_market_presentation import group_positions, kickoff_time, practical_shortlist
from pitchapi_prematch_context import lookup_context
from pitchapi_market_validation import review_position
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

WARSAW = ZoneInfo("Europe/Warsaw")


def register_fonts():
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("MarketSans", regular))
            pdfmetrics.registerFont(TTFont("MarketSans-Bold", bold))
            pdfmetrics.registerFontFamily("MarketSans", normal="MarketSans", bold="MarketSans-Bold")
            return "MarketSans", "MarketSans-Bold"
    raise RuntimeError("No Unicode TTF font found")


def safe(text):
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("MarketSans", 7.2)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(14 * mm, 8 * mm, "API Market Scan | według meczów | osobno od KB Score | KB N +0 | DEV N +0")
    canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, f"strona {doc.page}")
    canvas.restoreState()


def build_pdf(payload, output=None, *, regrouped=False):
    regular, bold = register_fonts()
    target = target_date(payload.get("date"))
    output = Path(output) if output else Path("reports/api_market_scan") / f"API_MARKET_SCAN_{target}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=13 * mm, bottomMargin=16 * mm,
        title=f"API Market Scan {target} - według meczów", author="API Market Scan")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("MarketTitle", parent=styles["Title"], fontName=bold, fontSize=17,
        leading=20, alignment=TA_LEFT, textColor=colors.HexColor("#111827"), spaceAfter=3 * mm)
    subtitle = ParagraphStyle("MarketSubtitle", parent=styles["BodyText"], fontName=regular,
        fontSize=8.2, leading=11, textColor=colors.HexColor("#4B5563"), spaceAfter=3 * mm)
    match_style = ParagraphStyle("MatchHeading", parent=styles["BodyText"], fontName=bold,
        fontSize=10, leading=13, textColor=colors.white)
    column_style = ParagraphStyle("ColumnHeading", parent=styles["BodyText"], fontName=bold,
        fontSize=7.8, leading=10, textColor=colors.HexColor("#243650"))
    cell_style = ParagraphStyle("Cell", parent=styles["BodyText"], fontName=regular,
        fontSize=7.8, leading=10.3, textColor=colors.HexColor("#111827"))
    note_style = ParagraphStyle("Note", parent=cell_style, fontSize=7.2, leading=9.2,
        textColor=colors.HexColor("#4B5563"))
    score_style = ParagraphStyle("Score", parent=cell_style, fontName=bold, fontSize=9, leading=12)

    positions = payload.get("top_positions") or []
    groups = group_positions(positions)
    policy = (payload.get("publication") or {}).get("policy") or load_policy()
    floor = policy["publish_min_final_pct"]
    captured = payload.get("generated_at_utc") or (payload.get("publication") or {}).get("captured_at_utc")
    quote_time = datetime.fromisoformat(captured.replace("Z", "+00:00")).astimezone(WARSAW).strftime("%d.%m.%Y, %H:%M") if captured else "-"
    story = [Paragraph(f"API MARKET SCAN - {safe(target)}", title),
        Paragraph("LISTA GŁÓWNA + PEŁNE ARCHIWUM", subtitle),
        Paragraph(f"<b>{len(groups)} meczów • {len(positions)} typów • próg {floor:g}/100</b><br/>"
            f"Odczyt notowań: <b>{quote_time}</b>, czas polski.<br/>"
            "Mecze według godziny rozpoczęcia. Pod każdym meczem komplet typów w kolejności z rankingu API. Bez limitu pozycji.<br/>"
            "<b>Bez dopasowywania do STS i Superbet.</b> Notowania pochodzą z API.", subtitle)]
    if regrouped:
        story.append(Paragraph("<b>Przegrupowanie wcześniejszego raportu.</b> Zachowano wszystkie jego typy, oceny i notowania z podanej wyżej godziny. Część meczów może być już rozpoczęta lub zakończona.", subtitle))
    errors = (payload.get("market_overlay") or {}).get("odds_errors") or []
    if errors:
        story.append(Paragraph(f"Uwaga: nie udało się pobrać notowań dla {len(errors)} meczów. Lista może być niepełna.", subtitle))

    # Read-only pre-match PitchAPI signal. File may be absent; neither scores nor
    # recommended markets change. Never fetch live information from PDF renderer.
    context_path = Path("data/pitchapi/prematch") / f"{target}.json"
    pitch_context = None
    if context_path.is_file():
        try:
            candidate_context = json.loads(context_path.read_text(encoding="utf-8"))
            if (candidate_context.get("schema") == "pitchapi-prematch-context-v1"
                    and candidate_context.get("target_date") == target):
                pitch_context = candidate_context
        except (ValueError, OSError):
            pitch_context = None
    if pitch_context:
        story.append(Paragraph(
            f"<b>PitchAPI (dodatkowy kontekst):</b> historyczne xG z meczów rozegranych przed analizą; "
            f"{pitch_context.get('fixtures_with_both_sides_sufficient', 0)} spotkań z wystarczającą próbą obu drużyn. "
            "To nie jest prognoza bramek ani automatyczna korekta oceny /100.", subtitle))

    shortlist = practical_shortlist(positions)
    story.append(Paragraph("<b>LISTA GŁÓWNA — PRAKTYCZNE WARIANTY</b>", subtitle))
    story.append(Paragraph("Kurs API od 1,20; ocena od 67/100; do 3 pozycji na mecz, bez powtarzania tej samej statystyki i kierunku przy innych liniach. Bez limitu liczby meczów. Filtr wyłącznie prezentacyjny; nie zmienia ocen ani pełnego rankingu.", subtitle))
    if not shortlist:
        story.append(Paragraph("Brak pozycji spełniających warunki dodatkowej listy.", subtitle))
    for item in shortlist:
        signal = review_position(item, pitch_context)
        comment = ""
        if signal and signal["status"] not in ("no_data", "insufficient"):
            tag = {"favors": "historia okazji sprzyja", "cautions": "UWAGA - historia okazji ostrzega",
                   "mixed": "historia okazji niejednoznaczna"}[signal["status"]]
            comment = f" | PitchAPI: {tag} (wskaznik {signal['opportunity_index']:.2f}; pogladowo)"
        story.append(Paragraph(f"<b>{safe(item['home'])} — {safe(item['away'])}</b>: {safe(item['selection'])} | ocena {float(item['final_assessment_pct']):.1f}/100 | {safe(quote_text(item))}{safe(comment)}", note_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("<b>PEŁNE ARCHIWUM — WSZYSTKIE TYPY WEDŁUG MECZÓW</b>", subtitle))
    for match_index, items in enumerate(groups, 1):
        first = items[0]
        historic_xg = (lookup_context(pitch_context, first["home"], first["away"],
                                       first.get("competition"), first.get("kickoff_utc"))
                       if pitch_context else None)
        xg_notice = ""
        if historic_xg:
            h, a = historic_xg["home_recent"], historic_xg["away_recent"]
            if historic_xg["both_sides_sufficient"]:
                xg_notice = (
                    f"<br/><font size='8'>PitchAPI poprzednie mecze: "
                    f"G xG {h['mean_xg_for']:.2f}/xGA {h['mean_xg_against']:.2f} "
                    f"(n={h['complete_samples']}) | "
                    f"W xG {a['mean_xg_for']:.2f}/xGA {a['mean_xg_against']:.2f} "
                    f"(n={a['complete_samples']}) - tylko kontekst</font>")
            else:
                xg_notice = (
                    f"<br/><font size='8'>PitchAPI: niewystarczajaca historia xG "
                    f"(G {h['complete_samples']}, W {a['complete_samples']}) - bez oceny.</font>")
        header = (f"{match_index}. {safe(first['home'])} — {safe(first['away'])}<br/>"
            f"<font size='8'>{kickoff_time(first)} Polska • {safe(first['competition'])} • typy: {len(items)}</font>"
            f"{xg_notice}")
        rows = [[Paragraph(header, match_style), "", "", ""],
            [Paragraph(label, column_style) for label in ("Typ i komentarz", "API PURE", "Ocena /100", "Kursy w API / źródła")]]
        for type_index, item in enumerate(items, 1):
            pure = item.get("api_pure_pct")
            final = item.get("final_assessment_pct", item.get("market_adjusted_pct", pure))
            comment = item.get("final_comment") or item.get("market_comment") or ""
            details = [Paragraph(f"<b>{match_index}.{type_index} {safe(item['selection'])}</b>", cell_style)]
            if comment:
                details += [Spacer(1, 1.2 * mm), Paragraph(safe(comment), note_style)]
            signal = review_position(item, pitch_context)
            if signal and signal["status"] not in ("no_data", "insufficient"):
                label = {"favors": "Historia sytuacji bramkowych sprzyja",
                         "cautions": "OSTROZNIE: historia sytuacji bramkowych ostrzega",
                         "mixed": "Historia sytuacji bramkowych niejednoznaczna"}[signal["status"]]
                details += [Spacer(1, 1.2 * mm), Paragraph(
                    f"PitchAPI: {label} | wskaznik okazji {signal['opportunity_index']:.2f} "
                    "(sygnal pogladowy, bez zmiany oceny)", note_style)]
            quote = safe(quote_text(item).removeprefix("Kursy w API: ")).replace(". Źródła notowań: ", "<br/>")
            label = "Sprawdź dokładną linię i zasady rozliczenia." if item.get("market") not in {"team_goals", "corners"} else "Notowanie dostawcy API."
            rows.append([details,
                Paragraph("-" if pure is None else f"{float(pure):.1f}%", cell_style),
                Paragraph("-" if final is None else f"{float(final):.1f}", score_style),
                [Paragraph(quote, cell_style), Spacer(1, 1.2 * mm), Paragraph(label, note_style)]])
        table = LongTable(rows, colWidths=[88 * mm, 18 * mm, 21 * mm, 55 * mm],
            hAlign="LEFT", repeatRows=2, splitByRow=1)
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243650")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E8EDF4")),
            ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#D5DCE5")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DCE5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([table, Spacer(1, 4 * mm)])

    if not positions:
        story.append(Paragraph("Brak kwotowanych wariantów z oceną od ustalonego progu.", subtitle))
    story.append(Paragraph(
        "<b>Jak czytać:</b> API PURE oznacza pokrycie historyczne. Ocena końcowa /100 uwzględnia wiarygodność próby, rozgrywki, rynek i dostępny kontekst; nie jest skalibrowanym prawdopodobieństwem. "
        "W obrębie meczu zachowano kolejność rankingu API, bez preferencji bukmachera. "
        "Żółte kartki nie zastępują liczby/punktów kartek z uwzględnieniem czerwonych. "
        "Pełne dane i wersje prognoz są zapisane w repozytorium. API pozostaje osobne od KB Score i nie zmienia jego danych ani N.", subtitle))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", nargs="?", help="YYYY-MM-DD; default: today in Poland")
    parser.add_argument("--source", type=Path, help="Read an existing prediction without recalculating it")
    parser.add_argument("--output", type=Path, help="Write a separate report")
    parser.add_argument("--regrouped", action="store_true", help="Label a regrouped earlier publication")
    args = parser.parse_args()
    target = target_date(args.date)
    source = args.source or Path("data/api_football/market_scan") / f"{target}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") not in {"api-market-scan-v2", "api-market-scan-v3"} or payload.get("date") != target:
        raise SystemExit("Unexpected source schema or date")
    output = build_pdf(payload, args.output, regrouped=args.regrouped)
    print(json.dumps({"date": target, "pdf": str(output), "positions": len(payload.get("top_positions") or []),
        "matches": len(group_positions(payload.get("top_positions") or []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
