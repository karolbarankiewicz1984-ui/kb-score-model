"""Render isolated A/B/C research candidates from frozen forecasts."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
from github_models.abc_filter import evaluate

def build(predictions, events, queue, output_json, output_pdf):
    result = evaluate(predictions, events)
    fixture_ids = {str(f["fixture_id"]): f for f in queue["fixtures"]}
    if len(fixture_ids) != len(queue["fixtures"]):
        raise ValueError("duplicate_fixture")
    if any(str(row["fixture_id"]) not in fixture_ids for row in result["candidates"]):
        raise ValueError("unknown_fixture")
    result["queue_fixtures"] = len(fixture_ids)
    result["input_cutoff_utc"] = predictions.get("as_of_utc") or predictions.get("frozen_at_utc")
    result["rules"] = {"A": "P>=70%", "B": "P>=75%", "C": "P>=80%",
                       "1X2": "both Elo and Dixon-Coles pass; max 10pp difference",
                       "events": "single-model, mathematically complete over/under pairs"}
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n",encoding="utf-8")
    base = "/usr/share/fonts/truetype/dejavu/"
    pdfmetrics.registerFont(TTFont("DejaVuR",base+"DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuB",base+"DejaVuSans-Bold.ttf"))
    body = ParagraphStyle("body",fontName="DejaVuR",fontSize=8,leading=12,spaceAfter=6)
    title = ParagraphStyle("title",fontName="DejaVuB",fontSize=16,leading=21,spaceAfter=12)
    head = ParagraphStyle("head",fontName="DejaVuB",fontSize=11,leading=16,spaceBefore=12,spaceAfter=7)
    para = lambda s,st=body: Paragraph(escape(str(s)),st)
    story = [para("MULTIMODEL V2 — FILTRY A/B/C",title),
             para("Raport badawczy. Prawdopodobieństwa niekalibrowane; brak zweryfikowanej wartości bukmacherskiej."),
             para("Kolejka: "+str(len(fixture_ids))+" spotkań. Cutoff wejść: "+str(result["input_cutoff_utc"])),
             para("Liczba kandydatów po filtrach",head)]
    rows = [["Wariant","Próg","Liczba propozycji"]]
    for v,p in (("A","70%"),("B","75%"),("C","80%")):
        rows.append([v,p,str(result["counts"][v])])
    t=Table([[para(c) for c in row] for row in rows],colWidths=[95,95,290],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E6ECF1")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),.3,colors.grey)]))
    story.append(t)
    story.append(para("Wszystkie propozycje pozostają w kategorii OBSERWACJA, dopóki nie potwierdzimy kalibracji, czasu zamrożenia i stabilności danych. Nie obliczamy fikcyjnego V2 Score.",head))
    for variant in ("B","C","A"):
        selected = [x for x in result["candidates"] if x["variant"]==variant]
        selected.sort(key=lambda x: (-x.get("probability_min",x.get("probability",0)),str(x["fixture_id"]),x["market"]))
        story.append(para("Wariant "+variant+" — "+str(len(selected))+" propozycji",head))
        for x in selected[:100]:
            f=fixture_ids[str(x["fixture_id"])]
            label=str(f.get("home","?"))+" – "+str(f.get("away","?"))
            market=x["market"]+(" "+str(x.get("line")) if "line" in x else "")
            p=x.get("probability_min",x.get("probability",0))
            story.append(para(label+" | "+market+" "+x["selection"]+" | P="+format(p*100,".1f")+"% | "+x["status"]))
        if len(selected)>100:
            story.append(para("Pozostałe "+str(len(selected)-100)+" propozycji: pełny JSON obok PDF."))
    story.append(para("Metodologia i ograniczenia",head))
    story.append(para("Filtry A/B/C są równoległe, więc ta sama propozycja może wystąpić w kilku wariantach. Rynki zdarzeń są jednopomodelowe. Filtr nie potwierdza dostępności kursu, wartości zakładu ani skuteczności historycznej. Nie modyfikuje innych modeli."))
    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(output_pdf),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42).build(story)
    return result

def main():
    p=argparse.ArgumentParser()
    for arg in ("predictions","events","queue","output-json","output-pdf"):
        p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    load=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    build(load(a.predictions),load(a.events),load(a.queue),a.output_json,a.output_pdf)
if __name__=="__main__":
    main()
