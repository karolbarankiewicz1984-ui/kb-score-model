"""Unified Polish PDF layout for the isolated GitHub Models A/B/C reports."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

INK = colors.HexColor("#172C3A")
ACCENT = colors.HexColor("#175E59")
MUTED = colors.HexColor("#546977")
PALE = colors.HexColor("#E8F1EF")
DIVIDER = colors.HexColor("#CDDAD8")
WIDTH = A4[0] - 72

def fonts():
    root = Path("/usr/share/fonts/truetype/dejavu")
    for name, filename in (("ABCRegular", "DejaVuSans.ttf"),
                           ("ABCBold", "DejaVuSans-Bold.ttf")):
        path = root / filename
        if not path.is_file():
            raise RuntimeError("missing_pdf_font: " + str(path))
        pdfmetrics.registerFont(TTFont(name, str(path)))

def styles():
    def sty(name, size, leading, **kw):
        args = dict(fontName="ABCRegular", fontSize=size, leading=leading,
                    textColor=INK, spaceAfter=6)
        args.update(kw)
        return ParagraphStyle("ABC_" + name, **args)
    return {
        "title": sty("Title", 16.5, 22, fontName="ABCBold", spaceAfter=9),
        "sub": sty("Sub", 8.4, 12, textColor=MUTED),
        "head": sty("Head", 10.5, 15, fontName="ABCBold", textColor=ACCENT,
                    spaceBefore=13, spaceAfter=7, keepWithNext=True),
        "body": sty("Body", 8.5, 12),
        "small": sty("Small", 7.4, 10.7),
        "cell": sty("Cell", 7.1, 10.3, spaceAfter=0),
        "header": sty("Header", 7.2, 10.5, fontName="ABCBold", spaceAfter=0)
    }

def p(value, style):
    # Never interpret source names or source metadata as ReportLab XML.
    return Paragraph(escape(str(value)), style)

def table(rows, widths, st):
    cells = [[p(value, st["header"] if i == 0 else st["cell"])
              for value in row] for i, row in enumerate(rows)]
    result = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("LINEBELOW", (0, 0), (-1, 0), .8, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), .25, DIVIDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return result

def footer(canv, doc):
    canv.saveState()
    canv.setFont("ABCRegular", 7)
    canv.setFillColor(MUTED)
    canv.drawString(36, 20, "MULTIMODEL GitHub V2 | badanie A/B/C")
    canv.drawRightString(A4[0] - 36, 20, "Strona " + str(doc.page))
    canv.restoreState()

def render(story, output, title):
    fonts()
    dest = Path(output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(dest), pagesize=A4,
                            leftMargin=36, rightMargin=36,
                            topMargin=38, bottomMargin=40,
                            title=title, author="MULTIMODEL GitHub V2")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    if not dest.is_file() or dest.stat().st_size < 1000:
        raise RuntimeError("abc_pdf_not_generated")
