#!/usr/bin/env python3
"""Render the compact user-facing API Market Scan PDF.

Presentation only. All technical v3 layers stay in JSON on GitHub.
Never writes to KB Score CORE, KB N or DEV N.
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
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("MarketSans", regular))
            pdfmetrics.registerFont(TTFont("MarketSans-Bold", bold))
            return "MarketSans", "MarketSans-Bold"
    raise RuntimeError("No Unicode TTF font found")


def pct(value):
    return "-" if value is None else f"{float(value):.1f}%"


def delta_text(value):
    value = float(value or 0)
    sign = "+" if value > 0 else ""
    return f" ({sign}{value:.1f} pp)"


def arrow(value):
    value = float(value or 0)
    if value > 0.4:
        return "↑"
    if value < -0.4:
        return "↓"
    return "→"


def safe(text):
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fallback_signal(value):
    return {
        "STRONG_CONFIRMATION": "mocne potwierdzenie",
        "CONFIRMATION": "potwierdzenie",
        "NEUTRAL": "neutralny",
        "WARNING": "ostrzeżenie",
        "STRONG_WARNING": "mocne ostrzeżenie",
        "THIN_MARKET": "zbyt mało danych rynkowych",
        "NO_MARKET_LINE": "brak dokładnej linii rynkowej",
    }.get(value, str(value or "-"))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("MarketSans", 7.2)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(14 * mm, 8 * mm, "API Market Scan v3 | osobny od KB Score 2.1 CORE | KB N +0 | DEV N +0")
    canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, f"strona {doc.page}")
    canvas.restoreState()


def build_pdf(payload):
    regular, bold = register_fonts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=13 * mm, bottomMargin=16 * mm,
        title=f"API Market Scan {TARGET}", author="API Market Scan v3",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("MarketTitle", parent=styles["Title"], fontName=bold, fontSize=17, leading=20, alignment=TA_LEFT, textColor=colors.HexColor("#111827"), spaceAfter=3 * mm)
    subtitle = ParagraphStyle("MarketSubtitle", parent=styles["BodyText"], fontName=regular, fontSize=8.2, leading=10.4, textColor=colors.HexColor("#4B5563"), spaceAfter=3 * mm)
    heading = ParagraphStyle("PositionHeading", parent=styles["Heading3"], fontName=bold, fontSize=10.2, leading=12.3, textColor=colors.HexColor("#111827"), spaceAfter=1.3 * mm)
    match_style = ParagraphStyle("Match", parent=styles["BodyText"], fontName=regular, fontSize=8.1, leading=9.8, textColor=colors.HexColor("#6B7280"), spaceAfter=1.2 * mm)
    metric_style = ParagraphStyle("Metric", parent=styles["BodyText"], fontName=regular, fontSize=8.9, leading=11, textColor=colors.HexColor("#111827"), spaceAfter=1 * mm)
    comment_style = ParagraphStyle("Comment", parent=styles["BodyText"], fontName=regular, fontSize=8.2, leading=10.4, textColor=colors.HexColor("#374151"), spaceAfter=0)

    positions = payload.get("top_positions") or []
    story = [
        Paragraph(f"API MARKET SCAN - {safe(TARGET)}", title),
        Paragraph(
            f"Nierozpoczęte mecze: <b>{payload.get('fixtures_scanned', 0)}</b> &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"historia: <b>{payload.get('history_matches_loaded', 0)}</b> meczów &nbsp;&nbsp; | &nbsp;&nbsp; pozycje: <b>{len(positions)}</b><br/>"
            "API PURE = czysta historia. Ocena końcowa = wynik po sprawdzeniu wiarygodności próby, rodzaju rozgrywek, rynku i dostępnego bieżącego kontekstu.",
            subtitle,
        ),
    ]

    if not positions:
        story += [Paragraph("Brak pozycji spełniających dzisiejsze progi.", heading), Paragraph("System nie uzupełnia raportu słabszymi kandydatami.", comment_style)]
    else:
        for idx, item in enumerate(positions, 1):
            pure = item.get("api_pure_pct")
            final = item.get("final_assessment_pct", item.get("market_adjusted_pct", pure))
            delta = float(final or pure or 0) - float(pure or 0)
            status = item.get("final_status") or fallback_signal(item.get("market_signal"))
            comment = item.get("final_comment") or item.get("market_comment") or ""
            color = "#166534" if delta > 0.4 else "#B91C1C" if delta < -0.4 else "#374151"
            block = [
                Paragraph(f"{idx}. {safe(item.get('selection'))}", heading),
                Paragraph(f"{safe(item.get('home'))} - {safe(item.get('away'))} ({safe(item.get('competition'))})", match_style),
                Paragraph(f"<b>API PURE:</b> {pct(pure)} &nbsp;&nbsp;&nbsp; <b>Ocena końcowa:</b> <font color='{color}'><b>{pct(final)} {arrow(delta)}</b>{delta_text(delta)}</font>", metric_style),
                Paragraph(f"<b>Status:</b> {safe(status)}", metric_style),
                Paragraph(f"<b>Komentarz:</b> {safe(comment)}", comment_style),
            ]
            box = Table([[block]], colWidths=[A4[0] - 28 * mm], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D1D5DB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([box, Spacer(1, 2.2 * mm)])

    story.extend([
        Spacer(1, 1 * mm),
        Paragraph("Pełne dane techniczne - L5/L10/L15, reliability, podział domestic/Europa, notowania, snapshoty rynku i bieżący kontekst - są archiwizowane w JSON-ie na GitHubie.", subtitle),
        Spacer(1, 1.5 * mm),
        Paragraph("Jak czytać ten raport - w skrócie", heading),
        Paragraph(
            "<b>API PURE</b> - surowy wynik z historii i statystyk, bez późniejszych korekt. "
            "<b>Ocena końcowa</b> - konserwatywna ocena po sprawdzeniu wiarygodności próby, rodzaju rozgrywek, rynku i dostępnego bieżącego kontekstu. "
            "<b>↑ / ↓ / →</b> - ocena końcowa jest odpowiednio wyższa, niższa albo podobna do API PURE. "
            "<b>STRONG</b> oznacza najmocniejsze pozycje; <b>ACCEPT</b> - pozycje spełniające warunki publikacji. "
            "<b>Komentarz</b> prostym językiem mówi, co najbardziej wpłynęło na ocenę. "
            "Pełna warstwa techniczna pozostaje w GitHubie. Raport jest osobny od KB Score 2.1 CORE i nie zmienia jego ustawień ani N.",
            comment_style,
        ),
    ])
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source JSON: {SOURCE}")
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if payload.get("schema") not in {"api-market-scan-v2", "api-market-scan-v3"}:
        raise SystemExit(f"Unexpected schema: {payload.get('schema')}")
    build_pdf(payload)
    print(json.dumps({"date": TARGET, "pdf": str(OUTPUT), "positions": len(payload.get("top_positions") or [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
