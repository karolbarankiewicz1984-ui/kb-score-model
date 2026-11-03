#!/usr/bin/env python3
"""Convert one dated API Market Scan Markdown snapshot into a mobile-readable PDF."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import re
import unicodedata
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

ROOT = Path(__file__).resolve().parents[1]

def normalized_club(value):
    value = str(value or "").casefold().replace("ł", "l").replace("ø", "o").replace("ß", "ss")
    value = "".join(x for x in unicodedata.normalize("NFKD", value)
                    if not unicodedata.combining(x))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def historic_xg_context(match_heading, snapshot):
    """Unique matchup only. Cannot alter selection or score."""
    if not snapshot or snapshot.get("schema") != "pitchapi-prematch-context-v1":
        return None
    # The experiment report heading is: home – away (kickoff).
    matchup = re.match(r"^(.+?)\s+[–-]\s+(.+?)\s+\(", match_heading)
    if not matchup:
        return None
    home, away = normalized_club(matchup.group(1)), normalized_club(matchup.group(2))
    candidates = [f for f in snapshot.get("fixtures", []) if
                  normalized_club(f.get("home")) == home and
                  normalized_club(f.get("away")) == away]
    if len(candidates) != 1 or not candidates[0].get("both_sides_sufficient"):
        return None
    return candidates[0]

def font_setup():
    base = Path("/usr/share/fonts/truetype/dejavu")
    pdfmetrics.registerFont(TTFont("Scan", str(base / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("ScanBold", str(base / "DejaVuSans-Bold.ttf")))

def build(day: str):
    source = ROOT / "reports/api_market_scan/v2" / f"API_MARKET_SCAN_PLAYABLE_{day}.md"
    if not source.is_file():
        raise FileNotFoundError(f"Missing current scan Markdown: {source}")
    font_setup()
    out = ROOT / "reports/api_market_scan/pdf" / f"API_MARKET_SCAN_{day}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    styles = {
        "title": ParagraphStyle("title", fontName="ScanBold", fontSize=14, leading=20, spaceAfter=8),
        "body": ParagraphStyle("body", fontName="Scan", fontSize=8, leading=12, spaceAfter=5),
        "match": ParagraphStyle("match", fontName="ScanBold", fontSize=9, leading=13, spaceBefore=10, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName="Scan", fontSize=6.5, leading=9),
        "head": ParagraphStyle("head", fontName="ScanBold", fontSize=6.5, leading=9, textColor=colors.white),
    }
    def p(value, kind="body"):
        return Paragraph(escape(str(value)), styles[kind])
    # Independent PitchAPI context copied from protected main into this experiment
    # workflow; optional, and never changes odds, selections or KB N.
    pitch_path = ROOT / "data/pitchapi/prematch" / f"{day}.json"
    pitch_context = None
    if pitch_path.is_file():
        try:
            snapshot = json.loads(pitch_path.read_text(encoding="utf-8"))
            if snapshot.get("target_date") == day:
                pitch_context = snapshot
        except (OSError, ValueError):
            pitch_context = None
    lines = source.read_text(encoding="utf-8").splitlines()
    story = [p(f"API Market Scan — {day}", "title")]
    groups = 0
    positions = 0
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("# "):
            idx += 1
            continue
        if line.startswith("## "):
            match = line[3:]
            idx += 1
            while idx < len(lines) and not lines[idx].startswith("| Typ |"):
                if lines[idx].startswith("## "):
                    break
                idx += 1
            if idx >= len(lines) or not lines[idx].startswith("| Typ |"):
                continue
            idx += 2
            data = []
            while idx < len(lines) and lines[idx].startswith("|"):
                cells = [v.strip() for v in lines[idx].strip().strip("|").split("|")]
                if len(cells) == 5:
                    data.append(cells)
                idx += 1
            if data:
                groups += 1
                positions += len(data)
                story.append(p(match, "match"))
                xg = historic_xg_context(match, pitch_context)
                if xg is not None:
                    home, away = xg["home_recent"], xg["away_recent"]
                    story.append(p(
                        "PitchAPI, ostatnie mecze w rozgrywkach (tylko kontekst): "
                        f"gospodarze xG {home['mean_xg_for']:.2f} / xGA {home['mean_xg_against']:.2f} "
                        f"(n={home['complete_samples']}); "
                        f"goście xG {away['mean_xg_for']:.2f} / xGA {away['mean_xg_against']:.2f} "
                        f"(n={away['complete_samples']}). Oceny i typy bez zmian."))
                rows = [[p(v, "head") for v in ("Typ", "Ocena /100", "Najlepszy kurs", "STS", "Superbet")]]
                rows += [[p(v, "cell") for v in item] for item in data]
                table = Table(rows, colWidths=[65*mm, 21*mm, 37*mm, 23*mm, 23*mm], repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#214767")),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EDF2F6")]),
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#CED7DF")),
                    ("LEFTPADDING", (0,0), (-1,-1), 4),
                    ("RIGHTPADDING", (0,0), (-1,-1), 4),
                    ("TOPPADDING", (0,0), (-1,-1), 5),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ]))
                story.append(table)
            continue
        if line and not line.startswith("|") and not line.startswith("---"):
            story.append(p(line))
        idx += 1
    if not groups:
        story.append(p("Brak potwierdzonych propozycji spełniających warunki publikacji."))
    story.append(Spacer(1, 5*mm))
    story.append(p("Źródło: aktualny snapshot API Market Scan dla wskazanej daty. Kursy mogą ulec zmianie. Brak notowania STS/Superbet oznacza niepotwierdzone, nie niedostępne. Ocena /100 nie jest skalibrowanym prawdopodobieństwem."))
    doc = SimpleDocTemplate(str(out), pagesize=(190*mm,270*mm), leftMargin=10*mm, rightMargin=10*mm, topMargin=12*mm, bottomMargin=12*mm)
    doc.build(story)
    if out.stat().st_size < 1000:
        raise RuntimeError("PDF failed validation")
    print(f"{day}: {groups} matches, {positions} selections, {out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    build(parser.parse_args().date)
