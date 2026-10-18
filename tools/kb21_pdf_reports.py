"""Compact Polish KB Score research PDFs for pregame model A/B and FT audit.

Presentation only: reads immutable existing predictions/outcomes. Does not
calculate forecasts, alter scores, use provider APIs or recommend bets.
Requires reportlab, already installed in the daily KB21 workflow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

FORECAST_SCHEMA = "kb21-paired-xg-vs-goals-shadow-v1"
AUDIT_SCHEMA = "kb21-xg-vs-goals-prospective-comparison-v1"


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for path in candidates:
        if Path(path).is_file():
            if "KB21PairedPDF" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("KB21PairedPDF", path))
            return "KB21PairedPDF"
    return "Helvetica"


def _styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    f = _font()
    return {
        "headline": ParagraphStyle(
            "PairedHeadline", fontName=f, fontSize=15, leading=21,
            textColor=colors.HexColor("#21384D"), spaceAfter=9),
        "sub": ParagraphStyle(
            "PairedSub", fontName=f, fontSize=9, leading=14,
            textColor=colors.HexColor("#455469"), spaceAfter=10),
        "normal": ParagraphStyle(
            "PairedBody", fontName=f, fontSize=8, leading=12, spaceAfter=6),
        "cell": ParagraphStyle(
            "PairedCell", fontName=f, fontSize=7.2, leading=10),
        "cellsmall": ParagraphStyle(
            "PairedCellSmall", fontName=f, fontSize=7.1, leading=9.6),
        "warning": ParagraphStyle(
            "PairedWarning", fontName=f, fontSize=8.1, leading=12.2,
            textColor=colors.HexColor("#8B4036"), spaceAfter=9),
    }


def _paragraph(v, style):
    from reportlab.platypus import Paragraph
    return Paragraph(escape(str(v)).replace("\n", "<br/>"), style)


def _pdf(path, title, summary, warning, header, rows, footer):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    styles = _styles()
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    story = [
        _paragraph(title, styles["headline"]),
        _paragraph(summary, styles["sub"]),
        _paragraph(warning, styles["warning"]),
        Spacer(1, 4),
    ]
    width = landscape(A4)[0] - 64
    proportions = ([.33, .235, .235, .2] if len(header) == 4
                   else [.29, .10, .18, .18, .25])
    colwidths = [width * p for p in proportions]
    data = [[_paragraph(x, styles["cell"]) for x in header]]
    for row in rows:
        data.append([_paragraph(x, styles["cellsmall"]) for x in row])
    if not rows:
        data.append([_paragraph(
            "Brak kwalifikujących się danych (nie oznacza wartości 0).",
            styles["cell"])]+[""]*(len(header)-1))
    t = Table(data, colWidths=colwidths, hAlign="LEFT",
              repeatRows=1, splitByRow=1,
              spaceAfter=9, rowHeights=None)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF2")),
        ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#8595A4")),
        ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#D8DDE3")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(_paragraph(footer, styles["normal"]))

    def page_info(canvas, doc):
        canvas.saveState()
        canvas.setFont(styles["normal"].fontName, 7.5)
        canvas.setFillColor(colors.HexColor("#647585"))
        canvas.drawString(32, 19, "KB Score 2.1 · badanie prospektywne · NIE TYP")
        canvas.drawRightString(landscape(A4)[0]-32, 19,
                               f"Strona {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(dest), pagesize=landscape(A4),
        leftMargin=32, rightMargin=32, topMargin=32, bottomMargin=35,
        title=title, author="KB Score 2.1 / badanie modeli")
    doc.build(story, onFirstPage=page_info, onLaterPages=page_info)
    if (not dest.is_file() or dest.stat().st_size < 1500
            or not dest.read_bytes().startswith(b"%PDF-")):
        raise ValueError("Invalid PDF generated: " + str(dest))
    return dest


def _percent(value):
    if type(value) not in (float, int) or not 0 <= value <= 1:
        raise ValueError("Invalid model probability")
    return f"{100 * value:.1f}%"


def _probs(row):
    if not isinstance(row, dict) or set(row) != {"home","draw","away","over_2_5"}:
        raise ValueError("Incomplete model 1X2/O2.5 probabilities")
    return " / ".join(_percent(row[x]) for x in ("home","draw","away"))


def forecast_pdf(doc, path):
    if (not isinstance(doc, dict) or doc.get("schema") != FORECAST_SCHEMA
            or doc.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
            or doc.get("safe_to_publish_play") is not False
            or doc.get("register_writes") is not False
            or doc.get("kb21_n_effect") != 0
            or doc.get("original_kb21_p_model") is not None
            or doc.get("calibrated") is not False
            or not isinstance(doc.get("pairs"), list)
            or doc.get("paired_count") != len(doc["pairs"])):
        raise ValueError("Only frozen independent premarket pairs can become a PDF")
    rows = []
    ids = set()
    for pair in doc["pairs"]:
        fid = pair.get("fixture_id")
        from tools.kb21_single_source_calendar import _iso_datetime
        if (type(fid) is not int or fid <= 0 or fid in ids
                or pair.get("safe_to_publish_play") is not False
                or pair.get("original_kb21_p_model") is not None
                or any(pair.get(k) is not None for k in ("odds","selection","ev","match_result"))
                or _iso_datetime(pair.get("pair_freeze_utc")) is None
                or _iso_datetime(pair.get("kickoff_utc")) is None
                or _iso_datetime(pair["pair_freeze_utc"]) >= _iso_datetime(pair["kickoff_utc"])):
            raise ValueError("Invalid or late pregame PDF row")
        ids.add(fid)
        g, x = pair.get("goals_baseline_probabilities"), pair.get("xg_shadow_probabilities")
        rows.append((
            f"{pair['event']}\n{pair['league']} · ID {fid}\nStart UTC: {pair['kickoff_utc'][11:16]}",
            _probs(g),
            _probs(x),
            f"GOLE: {_percent(g['over_2_5'])}\nxG: {_percent(x['over_2_5'])}",
        ))
    return _pdf(
        path,
        f"KB Score 2.1 | Porównanie modeli | {doc['date']}",
        f"Zapisanych PRZED MECZEM: {len(rows)} par · model goli i historycznych xG · "
        "kolejność: 1 / X / 2.",
        "TO NIE SĄ TYPY BUKMACHERSKIE. Obie prognozy są eksperymentalne, "
        "bez walidacji, kursów i historycznego P(model).",
        ("Mecz i źródło", "Model goli 1 / X / 2", "Model xG 1 / X / 2",
         "Powyżej 2,5 gola"),
        rows,
        "xG oznacza średnie z rzeczywistych WCZEŚNIEJSZYCH meczów, nie przewidywane "
        "xG nadchodzącego spotkania. Porównanie skuteczności nastąpi na tej samej "
        "próbie po potwierdzeniu pełnego czasu gry.",
    )


def _score(value):
    return "—" if value is None else f"{value:.4f}"


def audit_pdf(doc, path):
    if (not isinstance(doc, dict) or doc.get("schema") != AUDIT_SCHEMA
            or doc.get("publication") != "RESEARCH_ONLY_NOT_PLAY"
            or doc.get("register_writes") is not False
            or doc.get("safe_to_publish_play") is not False
            or doc.get("original_kb21_n_effect") != 0
            or not isinstance(doc.get("rows"), list)
            or not isinstance(doc.get("summary"), dict)
            or doc.get("paired_pregame_forecasts") != len(doc["rows"])):
        raise ValueError("Only genuine independent FT audit can become PDF")
    s = doc["summary"]
    header = (
        "Mecz / status", "Wynik FT", "Brier 1X2: gole / xG",
        "Brier O2,5: gole / xG", "Trafność 1X2: gole / xG"
    )
    rows = []
    for row in doc["rows"]:
        score = row["full_time_goals"]
        if score is not None and (not isinstance(score, list) or len(score)!=2
                                   or any(type(v) is not int or v < 0 for v in score)):
            raise ValueError("Invalid verified FT score")
        rows.append((
            f"{row['fixture']}\n{row['status']}",
            f"{score[0]}:{score[1]}" if score else "—",
            f"{_score(row['goals_baseline_brier_1x2'])} / {_score(row['xg_shadow_brier_1x2'])}",
            f"{_score(row['goals_baseline_brier_over25'])} / {_score(row['xg_shadow_brier_over25'])}",
            ("— / —" if score is None else
             ("TAK" if row["goals_baseline_top_correct"] else "NIE") + " / " +
             ("TAK" if row["xg_shadow_top_correct"] else "NIE")),
        ))
    n = doc.get("distinct_settled_FT_matches")
    if type(n) is not int or not 0 <= n <= len(rows):
        raise ValueError("Invalid distinct settled count")
    summary = (
        f"Rozliczonych meczów FT: {n}/{len(rows)}. "
        f"Średni Brier 1X2: gole {_score(s.get('mean_1x2_brier_goals'))}, "
        f"xG {_score(s.get('mean_1x2_brier_xg'))}. "
        f"Średni Brier O2,5: gole {_score(s.get('mean_over25_brier_goals'))}, "
        f"xG {_score(s.get('mean_over25_brier_xg'))}.")
    return _pdf(
        path,
        f"KB Score 2.1 | Audyt modeli | {doc['date']}",
        summary,
        "Niższy Brier to mniejszy błąd prognozy. Mała próba nie dowodzi przewagi. "
        "Brak rozstrzygnięcia nie jest przegraną. To audyt badawczy, NIE typ.",
        header, rows,
        "Tylko wyniki FT powiązane z zapisanymi przedmeczowymi parami. "
        "Brak pomiaru ROI, value lub faktycznych kursów. "
        "Oryginalny rejestr i punktacja KB Score pozostają bez zmian.",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("forecast","audit"))
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root, output = Path(args.source_dir), Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = ("KB21_XG_V_GOALS_SHADOW_" if args.mode == "forecast"
              else "KB21_XG_V_GOALS_AUDIT_")
    generated = []
    for path in sorted(root.glob(prefix+"*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        dest = output / (path.stem + ".pdf")
        (forecast_pdf if args.mode == "forecast" else audit_pdf)(doc, dest)
        generated.append(dest)
    if not generated:
        raise ValueError("No matching " + args.mode + " source JSON files")
    print("KB21 PDFs:", ", ".join(str(p) for p in generated))


if __name__ == "__main__":
    main()
