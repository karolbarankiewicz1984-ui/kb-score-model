#!/usr/bin/env python3
"""Settle frozen API Market Scan picks; never infer missing stats or rewrite predictions."""
import argparse,json,os,urllib.request
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1]
FINISHED={"FT"} # AET/PEN excluded: regulation-only markets cannot be inferred
def api(endpoint,params):
    import urllib.parse
    key=os.environ["API_FOOTBALL_KEY"]
    url="https://v3.football.api-sports.io/"+endpoint+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"x-apisports-key":key})
    with urllib.request.urlopen(req,timeout=35) as r: obj=json.load(r)
    if obj.get("errors"):raise RuntimeError(str(obj["errors"]))
    return obj.get("response",[])
def stat(stats,name):
    for s in stats or []:
        if s.get("type")==name:
            v=s.get("value")
            if isinstance(v,(int,float)) and not isinstance(v,bool):return v
            if isinstance(v,str):
                try:return float(v)
                except ValueError:pass
    return None
STAT={"corners":"Corner Kicks","fouls":"Fouls","yellow":"Yellow Cards","shots":"Total Shots","shots_on_goal":"Shots on Goal","offsides":"Offsides","goalkeeper_saves":"Goalkeeper Saves"}
def settle(pick,fixture,blocks):
    if fixture.get("fixture",{}).get("status",{}).get("short") not in FINISHED:return "pending","not full-time regulation"
    metric=pick.get("market");scope=pick.get("market_scope","team")
    side=pick.get("team_side")
    if scope not in ("team","match"):return "unresolved","unknown scope"
    if metric=="team_goals":
        goals=fixture.get("goals") or {}
        if scope=="match":
            vals=[goals.get("home"),goals.get("away")]
            value=sum(vals) if all(isinstance(v,(int,float)) for v in vals) else None
        elif side in ("home","away"):value=goals.get(side)
        else:return "unresolved","unknown team side"
    elif metric in STAT:
        byid={b.get("team",{}).get("id"):b.get("statistics") for b in blocks}
        homeid=fixture.get("teams",{}).get("home",{}).get("id")
        awayid=fixture.get("teams",{}).get("away",{}).get("id")
        if scope=="match":ids=[homeid,awayid]
        elif side=="home":ids=[homeid]
        elif side=="away":ids=[awayid]
        else:return "unresolved","unknown team side"
        vals=[stat(byid.get(i),STAT[metric]) for i in ids]
        value=sum(vals) if all(v is not None for v in vals) else None
    else:return "unresolved","unsupported market"
    if value is None:return "unresolved","missing confirmed statistic"
    try:line=float(pick["line"])
    except (ValueError,TypeError,KeyError):return "unresolved","missing line"
    direction=pick.get("direction")
    if direction not in ("over","under"):return "unresolved","unsupported direction"
    if value==line:return "push",f"actual {value:g}"
    won=value>line if direction=="over" else value<line
    return ("won" if won else "lost"),f"actual {value:g}"
def bucket(score):
    if score is None:return "unknown"
    if score<70:return "67–69"
    if score<75:return "70–74"
    if score<80:return "75–79"
    if score<85:return "80–84"
    if score<90:return "85–89"
    return "90–100"
def create_pdf(day,rows,stats,output):
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("A",font));pdfmetrics.registerFont(TTFont("AB",bold))
    title=ParagraphStyle("t",fontName="AB",fontSize=13,leading=18,spaceAfter=10)
    body=ParagraphStyle("b",fontName="A",fontSize=7,leading=11,spaceAfter=5)
    cell=ParagraphStyle("c",fontName="A",fontSize=6.6,leading=10)
    def p(s,style=body):return Paragraph(escape(str(s)),style)
    story=[p("API Market Audit — "+day,title),p("Rozliczenie zamrożonych typów z daty "+day+". Brak danych i nieukończone mecze nie są liczone jako przegrane."),p("Trafność = wygrane / (wygrane + przegrane). Zwroty i nierozstrzygnięte wyłączone. Ocena /100 nie jest prawdopodobieństwem.")]
    table=[[p(x,cell) for x in ("Ocena","Wygrane","Przegrane","Zwroty","Nierozstrz.","Trafność")]]
    for key in ("67–69","70–74","75–79","80–84","85–89","90–100"):
        s=stats.get(key,Counter());n=s["won"]+s["lost"]
        table.append([p(x,cell) for x in (key,s["won"],s["lost"],s["push"],s["pending"]+s["unresolved"],f"{100*s['won']/n:.1f}%" if n else "brak próby")])
    t=Table(table,colWidths=[27*mm,24*mm,24*mm,23*mm,34*mm,35*mm],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DBE6F0")),("GRID",(0,0),(-1,-1),.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t);story.append(Spacer(1,5*mm))
    for row in rows:
        story.append(p(f"{row.get('home')} – {row.get('away')}: {row.get('selection')} | {row.get('final_assessment_pct')} pkt | {row['result']} ({row['detail']})"))
    if not rows:story.append(p("Brak zamrożonych typów do rozliczenia."))
    output.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(output),pagesize=(190*mm,270*mm),leftMargin=11*mm,rightMargin=11*mm).build(story)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("date");ap.add_argument("--input",required=True);args=ap.parse_args()
    payload=json.loads(Path(args.input).read_text())
    if payload.get("date")!=args.date:raise ValueError("Frozen snapshot date mismatch")
    picks=payload.get("picks") or []
    fixtures={};blocks={}
    for fid in sorted({p.get("fixture_id") for p in picks if p.get("fixture_id") is not None}):
        f=api("fixtures",{"id":fid})
        fixtures[fid]=f[0] if f else None
        if fixtures[fid] and fixtures[fid].get("fixture",{}).get("status",{}).get("short") in FINISHED:
            blocks[fid]=api("fixtures/statistics",{"fixture":fid})
    rows=[];stats=defaultdict(Counter)
    for pick in picks:
        fid=pick.get("fixture_id")
        if not fixtures.get(fid):result,detail="unresolved","fixture unavailable"
        else:result,detail=settle(pick,fixtures[fid],blocks.get(fid,[]))
        row={**pick,"result":result,"detail":detail}
        rows.append(row);stats[bucket(pick.get("final_assessment_pct"))][result]+=1
    out=ROOT/"reports/api_market_scan/audit"
    out.mkdir(parents=True,exist_ok=True)
    result={"schema":"api-market-audit-v1","date":args.date,"audited_at_utc":datetime.now(timezone.utc).isoformat(),"snapshot_frozen_at_utc":payload.get("frozen_at_utc"),"summary":{k:dict(v) for k,v in stats.items()},"rows":rows}
    (out/f"API_MARKET_AUDIT_{args.date}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    create_pdf(args.date,rows,stats,out/f"API_MARKET_AUDIT_{args.date}.pdf")
    print(json.dumps({"date":args.date,"picks":len(rows),"summary":result["summary"]},ensure_ascii=False))
if __name__=="__main__":main()
