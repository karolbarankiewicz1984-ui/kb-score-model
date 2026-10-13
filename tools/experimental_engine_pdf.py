"""Readable, explicitly experimental PDF from isolated API prediction JSON."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def render(src, output):
    data=json.loads(Path(src).read_text(encoding="utf-8"))
    if data.get("status")!="EXPERIMENT_ONLY" or data.get("register_writes") is not False:
        raise ValueError("Only isolated experimental reports accepted")
    output=Path(output)
    if not str(output).startswith("reports/experimental_engine/") or output.suffix.lower()!=".pdf":
        raise ValueError("PDF output must be isolated")
    output.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet()
    styles["Title"].textColor=colors.HexColor("#15334e")
    styles["Normal"].leading=15
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=34,leftMargin=34,topMargin=40,bottomMargin=40)
    story=[Paragraph("API Experimental Engine",styles["Title"]),
           Paragraph("Data: "+escape(str(data.get("date","?"))),styles["Heading2"]),
           Paragraph("DIAGNOSTYKA - NIE SA TO TYPY KB SCORE 2.1 ANI REKOMENDACJE GRY.",styles["Normal"]),
           Paragraph("Szacunki z historycznych goli (proxy), nie z xG. Brak kursow, value i walidacji kalibracji.",styles["Normal"]),
           Spacer(1,14)]
    rows=[["Fixture ID","Over 1.5","Over 2.5","Over 3.5","BTTS"]]
    for m in data.get("matches",[]):
        q=m["markets"]
        rows.append([str(m["fixture_id"])]+[f"{q[k]*100:.1f}%" for k in ("over_1_5","over_2_5","over_3_5","btts_yes")])
    if len(rows)==1:
        story.append(Paragraph("Brak meczow z wystarczajacymi danymi.",styles["Normal"]))
    else:
        table=Table(rows,colWidths=[115,95,95,95,95],repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#15334e")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#edf3f7")]),
            ("BOTTOMPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),9),
            ("ALIGN",(1,0),(-1,-1),"CENTER"),("LINEBELOW",(0,0),(-1,0),.5,colors.HexColor("#15334e"))]))
        story.append(table)
    story.extend([Spacer(1,16),Paragraph("Pominięte: "+str(len(data.get("excluded",[])))+" | Wplyw na N KB/DEV: 0 | Rejestr: bez zmian.",styles["Normal"])])
    doc.build(story)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    render(a.input,a.output)
if __name__=="__main__":main()
