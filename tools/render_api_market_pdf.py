#!/usr/bin/env python3
"""Render a compact daily API Market Scan v2 PDF from the committed JSON report.

Presentation layer only: it never recalculates API PURE or MARKET ADJUSTED and
never writes to KB Score CORE, KB N or DEV N.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

WARSAW = ZoneInfo("Europe/Warsaw")
TARGET = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else datetime.now(WARSAW).date().isoformat()
SOURCE = Path("data/api_football/market_scan") / f"{TARGET}.json"
OUT_DIR = Path("reports/api_market_scan")
OUTPUT = OUT_DIR / f"API_MARKET_SCAN_{TARGET}.pdf"


def register_fonts():
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("MarketSans", regular))
            pdfmetrics.registerFont(TTFont("MarketSans-Bold", bold))
            return "MarketSans", "MarketSans-Bold"
    raise RuntimeError("No Unicode TTF font found (DejaVu/Liberation required).")


def pct(value):
    return "-" if value is None else f"{float(value):.1f}%"


def delta_text(value):
    if value is None:
        return ""
    value = float(value)
    sign = "+" if value > 0 else ""
    return f" ({sign}{value:.1f} pp)"


def arrow(value):
    value = float(value or 0)
    if value > 0.4:
        return "↑"
    if value < -0.4:
        return "↓"
    return "→"


def signal_text(value):
    labels = {
        "STRONG_CONFIRMATION": "mocne potwierdzenie",
        "CONFIRMATION": "potwierdzenie",
        "NEUTRAL": "neutralny",
        "WARNING": "ostrzeżenie",
        "STRONG_WARNING": "mocne ostrzeżenie",
        "THIN_MARKET": "zbyt mało danych rynkowych",
        "NO_MARKET_LINE": "brak dokładnej linii rynkowej",
    }
    return labels.get(value, str(value or "-"))


def safe(text):
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("MarketSans", 7.2)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(14 * mm, 8 * mm, "API Market Scan v2 | osobny od KB Score 2.1 CORE | KB N +0 | DEV N +0")
    canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, f"strona {doc.page}")
    canvas.restoreState()


def build_pdf(payload):
    regular, bold = register_fonts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=16 * mm,
        title=f"API Market Scan {TARGET}",
        author="API Market Scan v2",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "MarketTitle", parent=styles["Title"], fontName=bold, fontSize=17, leading=20,
        alignment=TA_LEFT, textColor=colors.HexColor("#111827"), spaceAfter=3 * mm,
    )
    subtitle = ParagraphStyle(
        "MarketSubtitle", parent=styles["BodyText"], fontName=regular, fontSize=8.2, leading=10.4,
        textColor=colors.HexColor("#4B5563"), spaceAfter=3 * mm,
    )
    heading = ParagraphStyle(
        "PositionHeading", parent=styles["Heading3"], fontName=bold, fontSize=10.2, leading=12.3,
        textColor=colors.HexColor("#111827"), spaceAfter=1.3 * mm,
    )
    match_style = ParagraphStyle(
        "Match", parent=styles["BodyText"], fontName=regular, fontSize=8.1, leading=9.8,
        textColor=colors.HexColor("#6B7280"), spaceAfter=1.2 * mm,
    )
    metric_style = ParagraphStyle(
        "Metric", parent=styles["BodyText"], fontName=regular, fontSize=8.9, leading=11,
        textColor=colors.HexColor("#111827"), spaceAfter=1 * mm,
    )
    comment_style = ParagraphStyle(
        "Comment", parent=styles["BodyText"], fontName=regular, fontSize=8.2, leading=10.4,
        textColor=colors.HexColor("#374151"), spaceAfter=0,
    )

    positions = payload.get("top_positions") or []
    fixtures = payload.get("fixtures_scanned", 0)
    history = payload.get("history_matches_loaded", 0)

    story = [
        Paragraph(f"API MARKET SCAN - {safe(TARGET)}", title),
        Paragraph(
            f"Nierozpoczęte mecze: <b>{fixtures}</b> &nbsp;&nbsp; | &nbsp;&nbsp; historia: <b>{history}</b> meczów "
            f"&nbsp;&nbsp; | &nbsp;&nbsp; pozycje: <b>{len(positions)}</b><br/>"
            "API PURE = czysta statystyka historyczna. Po analizie rynku = osobna, bieżąca korekta rynku.",
            subtitle,
        ),
    ]

    if not positions:
        story.append(Paragraph("Brak pozycji spełniających dzisiejsze progi.", heading))
        story.append(Paragraph("System nie uzupełnia raportu słabszymi kandydatami.", comment_style))
    else:
        for idx, item in enumerate(positions, 1):
            pure = item.get("api_pure_pct")
            adjusted = item.get("market_adjusted_pct", pure)
            delta = item.get("market_delta_pp", 0)
            selection = safe(item.get("selection") or "")
            home = safe(item.get("home") or "")
            away = safe(item.get("away") or "")
            competition = safe(item.get("competition") or "")
            signal = safe(signal_text(item.get("market_signal")))
            comment = safe(item.get("market_comment") or "")

            if float(delta or 0) > 0.4:
                adjusted_color = "#166534"
            elif float(delta or 0) < -0.4:
                adjusted_color = "#B91C1C"
            else:
                adjusted_color = "#374151"

            block = [
                Paragraph(f"{idx}. {selection}", heading),
                Paragraph(f"{home} - {away} ({competition})", match_style),
                Paragraph(
                    f"<b>API PURE:</b> {pct(pure)} &nbsp;&nbsp;&nbsp; "
                    f"<b>Po analizie rynku:</b> <font color='{adjusted_color}'><b>{pct(adjusted)} {arrow(delta)}</b>{delta_text(delta)}</font>",
                    metric_style,
                ),
                Paragraph(f"<b>Sygnał rynku:</b> {signal}", metric_style),
                Paragraph(f"<b>Komentarz:</b> {comment}", comment_style),
            ]
            box = Table([[block]], colWidths=[A4[0] - 28 * mm], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D1D5DB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([box, Spacer(1, 2.2 * mm)])

    story.extend([
        Spacer(1, 1 * mm),
        Paragraph(
            "Pełne L5/L10/L15, odmarżowione prawdopodobieństwa, liczba bukmacherów, snapshoty rynku i surowe notowania są archiwizowane w JSON-ie na GitHubie.",
            subtitle,
        ),
        Spacer(1, 1.5 * mm),
        Paragraph("Jak czytać ten raport - w skrócie", heading),
        Paragraph(
            "<b>API PURE</b> - co wynika wyłącznie z naszej historii i statystyk API, bez kursów. "
            "<b>Po analizie rynku</b> - ta sama pozycja po sprawdzeniu aktualnych notowań bukmacherów. "
            "<b>↑ / ↓ / →</b> - rynek odpowiednio podnosi, obniża albo praktycznie nie zmienia oceny. "
            "<b>Sygnał rynku</b> - krótka ocena, czy rynek potwierdza statystykę, jest neutralny czy ostrzega. "
            "<b>Komentarz</b> - prostym językiem wyjaśnia, dlaczego ocena się zmieniła lub pozostała bez zmian. "
            "Ten raport jest osobny od KB Score 2.1 CORE i nie zmienia jego ustawień ani N.",
            comment_style,
        ),
    ])

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source JSON: {SOURCE}")
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if payload.get("schema") != "api-market-scan-v2":
        raise SystemExit(f"Unexpected schema: {payload.get('schema')}")
    build_pdf(payload)
    print(json.dumps({"date": TARGET, "pdf": str(OUTPUT), "positions": len(payload.get("top_positions") or [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
