"""Research A/B/C audit PDF."""
import argparse
import json
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def build(data, output):
    pdfmetrics.registerFont(TTFont("DV","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    style=ParagraphStyle("audit",fontName="DV",fontSize=10,leading=15,spaceAfter=10)
    lines=["MULTIMODEL V2 — audyt A/B/C",
           "UTC: "+str(data["as_of_utc"]),
           "Archiwa: "+str(data["archives_processed"]),
           "Unikalne propozycje: "+str(data.get("unique_candidate_records","nieustalone")),
           "Powtórzone migawki pominięte: "+str(data.get("duplicate_snapshots_suppressed",0)),
           "Niezweryfikowane wyniki nie są nietrafieniami."]
    for row in data["summary"]:
        rate=row["hit_rate"]
        lines.append("%s / %s: %d rozliczonych, %d trafień, skuteczność %s, Brier %s, log loss %s" %
                     (row["variant"],row["market"],row["settled"],row["hits"],
                      "brak" if rate is None else "%.1f%%"%(rate*100),
                      str(row["brier"]),str(row["log_loss"])))
    for reason,count in sorted(data.get("unresolved_reasons",{}).items(),key=lambda x:-x[1])[:8]:
        lines.append("Nierozliczone — "+str(reason)+": "+str(count))
    lines.append("Bez automatycznej zmiany progów; weryfikacja po 100–150 unikalnych meczach.")
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(output).build([Paragraph(line,style) for line in lines])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    build(json.loads(Path(a.input).read_text(encoding="utf-8")),a.output)
if __name__=="__main__":
    main()
