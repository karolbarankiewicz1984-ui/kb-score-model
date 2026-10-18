"""Compact Polish PDF reports for KB21 research comparisons.

Paired forecasts are generated only from saved pre-kickoff records.
The PDF is a presentation of immutable JSON, never a model or source
of results. Daily PDF and next-day comparison PDF never claim PLAY.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/local/share/fonts/DejaVuSans.ttf",
)
COLOR_MAIN = colors.HexColor("#152238")
COLOR_SUB = colors.HexColor("#526174")
COLOR_LINE = colors.HexColor("#D9E0E8")
COLOR_PALE = colors.HexColor("#F3F6FA")


def _register():
    for path in FONT_PATHS:
        if Path(path).is_file():
            if "KBDeja" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("KBDeja", path))
            return "KBDeja"
    raise RuntimeError("Missing DejaVu Sans Unicode font; refusing broken Polish PDF")


def _styles():
    f = _register()
    return {
        "title": ParagraphStyle("KBTitle", fontName=f, fontSize=14.5,
                                leading=19, textColor=COLOR_MAIN, spaceAfter=10),
        "subtitle": ParagraphStyle("KBSub", fontName=f, fontSize=8.3,
                                   leading=11.3, textColor=COLOR_SUB, spaceAfter=9),
        "head": ParagraphStyle("KBHead", fontName=f, fontSize=8.1,
                               leading=11, textColor=colors.white),
        "cell": ParagraphStyle("KBCell", fontName=f, fontSize=7.3,
                               leading=10.0, textColor=COLOR_MAIN, wordWrap="CJK"),
        "minor": ParagraphStyle("KBMinor", fontName=f, fontSize=7.2,
                                leading=10, textColor=COLOR_SUB),
        "metric": ParagraphStyle("KBMetric", fontName=f, fontSize=8.5,
                                 leading=13, textColor=COLOR_MAIN),
    }


def _p(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _safe_proba(data):
    required = ("home", "draw", "away", "over_2_5")
    if not isinstance(data, dict) or set(data) != set(required):
        raise ValueError("Incomplete probabilities in saved paired record")
    out = {}
    for k in required:
        v = data[k]
        if type(v) not in (int, float) or not 0 <= v <= 1:
            raise ValueError("Invalid probability")
        out[k] = v
    if abs(sum(out[k] for k in ("home", "draw", "away")) - 1) > .0002:
        raise ValueError("Inconsistent 1X2 probabilities")
    return out


def _fmt(p):
    return f"1 {100*p['home']:.1f}% | X {100*p['draw']:.1f}% | 2 {100*p['away']:.1f}%\nOver 2,5: {100*p['over_2_5']:.1f}%"


def _table(data, widths, font, *, first_header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if first_header else 0,
              hAlign="LEFT", splitByRow=1)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), .35, COLOR_LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_PALE]),
    ]
    if first_header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), COLOR_MAIN)]
    t.setStyle(TableStyle(cmds))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(COLOR_LINE)
    canvas.line(32, 26, landscape(A4)[0]-32, 26)
    canvas.setFont("KBDeja", 7)
    canvas.setFillColor(COLOR_SUB)
    canvas.drawString(32, 15, "KB Score 2.1 | BADANIE: bez kursów, typów i zmian historycznego modelu")
    canvas.drawRightString(landscape(A4)[0]-32, 15, f"Strona {doc.page}")
    canvas.restoreState()


def _make(destination, story):
    dst = Path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dst), pagesize=landscape(A4),
        leftMargin=32, rightMargin=32, topMargin=32, bottomMargin=40,
        title="KB Score 2.1 - porównanie modeli badawczych",
        author="KB Score 2.1 research workflow",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    if dst.stat().st_size < 1700 or dst.read_bytes()[:5] != b"%PDF-":
        raise ValueError("PDF generation did not produce valid output")
    return dst


def paired_pdf(source, destination):
    if (not isinstance(source, dict)
            or source.get("schema") != "kb21-paired-xg-vs-goals-shadow-v1"
            or source.get("calibrated") is not False
            or source.get("register_writes") is not False
            or source.get("kb21_n_effect") != 0
            or source.get("safe_to_publish_play") is not False
            or source.get("original_kb21_p_model") is not None
            or not isinstance(source.get("pairs"), list)
            or source.get("paired_count") != len(source["pairs"])):
        raise ValueError("Unverified pregame research data; PDF refused")
    styles = _styles()
    day = source.get("date", "brak daty")
    elements = [
        _p(f"KB Score 2.1 | porównanie modeli | {day}", styles["title"]),
        _p("Wcześniej zapisane prognozy 1/X/2 i over 2,5. Obie wersje "
           "są eksperymentalne, nieskalibrowane i bez kursów. "
           "To NIE są typy bukmacherskie.", styles["subtitle"]),
        _p(f"Porównywalnych, zamrożonych przed startem spotkań: {source['paired_count']}. "
           "Baza = faktyczne gole. Nowy wariant = historyczne xG PitchAPI.", styles["metric"]),
        Spacer(1, 10),
    ]
    cols = [243, 207, 207, 119]
    header = [_p(x, styles["head"]) for x in
              ("Mecz / data rozpoczęcia UTC", "Model G: ostatnie gole",
               "Model X: wcześniejsze xG", "Próba xG")]
    table = [header]
    for record in source["pairs"]:
        if any(record.get(key) is not None for key in
               ("original_kb21_p_model", "odds", "selection", "match_result")):
            raise ValueError("Refusing contaminated paired PDF record")
        g = _safe_proba(record.get("goals_baseline_probabilities"))
        x = _safe_proba(record.get("xg_shadow_probabilities"))
        sizes = record.get("xg_sample_sizes") or {}
        if not all(type(sizes.get(k)) is int and 3 <= sizes[k] <= 5
                   for k in ("home", "away")):
            raise ValueError("Unverified xG sample in paired PDF")
        label = f"{record.get('event','—')}\n{record.get('kickoff_utc','—')[:16]} UTC"
        table.append([
            _p(label, styles["cell"]),
            _p(_fmt(g), styles["cell"]),
            _p(_fmt(x), styles["cell"]),
            _p(f"G: {sizes['home']}\nW: {sizes['away']}", styles["cell"]),
        ])
    if source["pairs"]:
        elements.append(_table(table, cols, styles["cell"]))
    else:
        elements.append(_p("Brak autentycznych par prognoz w tym dniu. "
                           "Nie wstawiono fikcyjnych procentów.", styles["metric"]))
    elements += [
        Spacer(1, 14),
        _p("Nie wskazujemy faworyta na podstawie różnicy procentów. "
           "O jakości decyduje dopiero audyt tych samych meczów po FT "
           "(Brier 1/X/2 i over 2,5). Wartości są orientacyjne, "
           "nie stanowią oryginalnego P(model) ani decyzji PLAY.", styles["minor"]),
    ]
    return _make(destination, elements)


def audit_pdf(source, destination):
    if (not isinstance(source, dict)
            or source.get("schema") != "kb21-xg-vs-goals-prospective-comparison-v1"
            or source.get("register_writes") is not False
            or source.get("original_kb21_n_effect") != 0
            or source.get("safe_to_publish_play") is not False
            or not isinstance(source.get("rows"), list)
            or not isinstance(source.get("summary"), dict)):
        raise ValueError("Unverified paired-audit data; PDF refused")
    st = _styles()
    s = source["summary"]
    def fmt(v):
        return f"{v:.4f}" if type(v) in (int, float) else "brak danych"
    story = [
        _p(f"KB Score 2.1 | audyt gole kontra xG | {source.get('date','—')}", st["title"]),
        _p("Porównanie WYŁĄCZNIE wspólnych spotkań zakończonych FT, "
           "dla których obie prognozy zapisano przed meczem. "
           "Brier: niżej oznacza lepiej. Nie jest to rozliczenie zakładów.", st["subtitle"]),
        _p(f"Zamrożone pary: {source.get('paired_pregame_forecasts',0)} | "
           f"Rozliczone FT: {source.get('distinct_settled_FT_matches',0)} | "
           f"Nierozstrzygnięte: {source.get('unresolved',0)}", st["metric"]),
        _p(f"Brier 1/X/2: gole {fmt(s.get('mean_1x2_brier_goals'))} | "
           f"xG {fmt(s.get('mean_1x2_brier_xg'))} | "
           f"różnica {fmt(s.get('brier_1x2_xg_minus_goals'))}", st["metric"]),
        _p(f"Brier over 2,5: gole {fmt(s.get('mean_over25_brier_goals'))} | "
           f"xG {fmt(s.get('mean_over25_brier_xg'))} | "
           f"różnica {fmt(s.get('brier_over25_xg_minus_goals'))}", st["metric"]),
        Spacer(1, 10),
    ]
    headers = [_p(x,st["head"]) for x in (
        "Mecz", "Wynik FT", "Brier 1/X/2: gole", "Brier 1/X/2: xG", "Status")]
    data = [headers]
    for x in source["rows"]:
        ftime = x.get("full_time_goals")
        score = f"{ftime[0]}:{ftime[1]}" if isinstance(ftime,list) and len(ftime)==2 else "—"
        data.append([
            _p(x.get("fixture","—"),st["cell"]),
            _p(score,st["cell"]),
            _p(fmt(x.get("goals_baseline_brier_1x2")),st["cell"]),
            _p(fmt(x.get("xg_shadow_brier_1x2")),st["cell"]),
            _p(x.get("status","—"),st["cell"]),
        ])
    if source["rows"]:
        story.append(_table(data,[283,70,123,123,177],st["cell"]))
    else:
        story.append(_p("Brak zakończonych par do oceny. Nie można ogłosić zwycięzcy.",st["metric"]))
    story += [Spacer(1,14),
              _p("Różnica xG minus gole mniejsza od zera oznacza niższy błąd "
                 "na tej próbie, ale mała próba nie dowodzi przewagi. "
                 "Brak kursów, EV, ROI, punktacji oryginalnego KB Score i PLAY.",st["minor"])]
    return _make(destination,story)


def main():
    parser=argparse.ArgumentParser(description="Generate compact Polish KB21 research PDF")
    parser.add_argument("--kind",required=True,choices=["paired","audit"])
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    source=json.loads(Path(args.input).read_text(encoding="utf-8"))
    path=(paired_pdf if args.kind=="paired" else audit_pdf)(source,args.output)
    print("Generated KB21 research PDF:",path,"bytes:",path.stat().st_size)


if __name__=="__main__":
    main()
