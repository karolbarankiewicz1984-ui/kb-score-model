"""Compact, honest selections PDF derived from UNCHANGED API Market Scan snapshot.

No new API calls, odds lookup, bet placement or model recalibration.
Only pre-kickoff positions with exact, already quoted line and API score.
Polish-bookmaker availability is explicitly NOT verified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from api_market_policy import selection_quotes, target_date
from api_market_presentation import practical_shortlist, fouls_under_watchlist

WARSAW=ZoneInfo("Europe/Warsaw")
SCORE_FLOOR=67.0
ODD_FLOOR=1.20
MAX_GOALS=6
MAX_OTHER=6
MIN_LEAD_MINUTES=15


def _dt(value):
    if not isinstance(value,str):
        return None
    try:
        x=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return x.astimezone(timezone.utc) if x.tzinfo is not None else None


def pick_research_positions(payload, now=None):
    """A small display-only cross-match list from the existing practical list."""
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware capture required")
    now=now.astimezone(timezone.utc)
    day=payload.get("date")
    if (payload.get("schema") not in ("api-market-scan-v2","api-market-scan-v3")
            or not isinstance(day,str) or not isinstance(payload.get("top_positions"),list)):
        raise ValueError("Invalid API Market report snapshot")
    stamp=_dt(payload.get("generated_at_utc") or
             (payload.get("publication") or {}).get("captured_at_utc"))
    if stamp is None or stamp>now:
        raise ValueError("Provider quotes need genuine existing capture time")
    raw=practical_shortlist(payload["top_positions"],min_odd=ODD_FLOOR,
                            max_per_match=3,min_score=SCORE_FLOOR)
    groups={"goals":[],"other":[]}
    used=set()
    for p in raw:
        fid=p.get("fixture_id")
        kickoff=_dt(p.get("kickoff") or p.get("kickoff_utc"))
        if (fid is None or fid in used or kickoff is None
                or kickoff.astimezone(WARSAW).date().isoformat()!=day
                or kickoff<=now):
            continue
        # Quoted selections in this PDF never contain a price < 1.20.
        eligible=[q for q in selection_quotes(p)
                  if type(q.get("selected_odd")) in (int,float)
                  and q["selected_odd"]>=ODD_FLOOR]
        if not eligible:
            continue
        if (not isinstance(p.get("selection"),str) or not p["selection"].strip()
                or not isinstance(p.get("home"),str)
                or not isinstance(p.get("away"),str)):
            continue
        cat=("goals" if "gole" in p["selection"].casefold() else "other")
        if len(groups[cat])>=(MAX_GOALS if cat=="goals" else MAX_OTHER):
            continue
        offered=max(eligible,key=lambda q:q["selected_odd"])
        qtime=kickoff.astimezone(WARSAW).strftime("%H:%M")
        item={
            "fixture_id":fid,
            "fixture":p["home"]+" – "+p["away"],
            "kickoff_warsaw":qtime,
            "selection":p["selection"],
            "score":float(p["final_assessment_pct"]),
            "api_best_odd":float(offered["selected_odd"]),
            "api_best_odd_provider":str(offered.get("bookmaker") or "nieznany"),
            "eligible_quote_count":len(eligible),
            "market":p.get("market"),
            "category":cat,
            "quote_capture_utc":stamp.isoformat(),
            "verification":"OFFER_NOT_VERIFIED_AT_POLISH_BOOKMAKER",
        }
        groups[cat].append(item)
        used.add(fid)
    # Additional observation lane, independent of the one-per-match shortlist.
    # Unlike the official score-gated section it can show sub-67 experiments.
    fouls_under=[]
    watch=fouls_under_watchlist(payload,limit=10)
    for found in watch["rows"]:
        p,quote=found["item"],found["quote"]
        kickoff=_dt(p.get("kickoff") or p.get("kickoff_utc"))
        if kickoff is None or kickoff<=now or kickoff.astimezone(WARSAW).date().isoformat()!=day:
            continue
        fouls_under.append({
            "fixture_id":p.get("fixture_id"),
            "fixture":p["home"]+" – "+p["away"],
            "kickoff_warsaw":kickoff.astimezone(WARSAW).strftime("%H:%M"),
            "selection":p["selection"],
            "score":found["score"],
            "api_best_odd":float(quote["selected_odd"]),
            "api_best_odd_provider":str(quote.get("bookmaker") or "nieznany"),
            "category":"fouls_under_observational",
            "status":"TEST - poniżej progu 67" if found["score"]<SCORE_FLOOR else "OBSERWUJ - API",
            "quote_capture_utc":str(quote.get("provider_updated_at") or stamp.isoformat()),
            "verification":"OFFER_NOT_VERIFIED_AT_POLISH_BOOKMAKER",
        })
    return {
        "date":day,"schema":"api-market-practical-card-v1",
        "quote_capture_utc":stamp.isoformat(),
        "generated_utc":now.isoformat(),
        "fouls_under":fouls_under,
        "goal_markets":groups["goals"],
        "other_markets":groups["other"],
        "total":len(groups["goals"])+len(groups["other"]),
        "min_score":SCORE_FLOOR,"min_api_odd":ODD_FLOOR,
        "original_market_model_modified":False,
        "polish_bookmaker_verified":False,
        "recommendation_is_guaranteed":False,
        "note":"Presentation-only: price is provider API snapshot, not current live sportsbook availability.",
    }


def render_pdf(report, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer

    if (report.get("schema")!="api-market-practical-card-v1"
            or report.get("polish_bookmaker_verified") is not False
            or report.get("original_market_model_modified") is not False):
        raise ValueError("Cannot present unverified recommendations as verified bets")
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not Path(font).exists():
        raise RuntimeError("Missing Polish Unicode font")
    if "AMShort" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("AMShort",font))
    ink=colors.HexColor("#17243A")
    muted=colors.HexColor("#485A6C")
    heading=ParagraphStyle("head",fontName="AMShort",fontSize=14,leading=19,textColor=ink,spaceAfter=9)
    body=ParagraphStyle("body",fontName="AMShort",fontSize=7.4,leading=11,textColor=ink,spaceAfter=5)
    sub=ParagraphStyle("sub",fontName="AMShort",fontSize=8,leading=12,textColor=muted,spaceAfter=7)
    small=ParagraphStyle("small",fontName="AMShort",fontSize=7,leading=10,textColor=ink)
    white=ParagraphStyle("white",fontName="AMShort",fontSize=7.5,leading=10,textColor=colors.white)
    label=lambda text,st:Paragraph(escape(str(text)),st)
    filename=Path(path)
    filename.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(filename),pagesize=A4,
        leftMargin=13*mm,rightMargin=13*mm,topMargin=13*mm,bottomMargin=14*mm,
        title="API Market - praktyczne rynki do sprawdzenia")
    story=[
        label(f"API MARKET | KONKRETNE RYNKI | {report['date']}",heading),
        label("Lista do sprawdzenia przed obstawieniem, NIE potwierdzone oferty STS/Superbet. "
              "Jeden wariant na mecz; ocena 67+/100, kurs źródłowy 1,20+.",sub),
        label("Kursy: zapis API z "+report["quote_capture_utc"][:16].replace("T"," ")
              +" UTC. Ocena /100 NIE jest prawdopodobieństwem trafienia. "
              "Sprawdź godzinę, dokładną linię i aktualny kurs u bukmachera.",body)
    ]
    widths=[46*mm,67*mm,17*mm,52*mm]
    def table_group(title,entries):
        story.append(Spacer(1,3*mm))
        story.append(label(f"{title} ({len(entries)} propozycji)",heading))
        if not entries:
            story.append(label("Brak zgodnych, nadal nierozpoczętych spotkań.",sub))
            return
        rows=[[label(x,white) for x in ("Mecz / start PL","Konkretny rynek","Ocena","Kurs API i źródło")]]
        for x in entries:
            rows.append([
                label(x["fixture"]+"\n"+x["kickoff_warsaw"],small),
                label(x["selection"],small),
                label(f"{x['score']:.1f}/100",small),
                label(f"{x['api_best_odd']:.2f} | {x['api_best_odd_provider']}",small),
            ])
        t=Table(rows,colWidths=widths,repeatRows=1,splitByRow=1,hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),ink),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F3F6FA")]),
            ("LINEBELOW",(0,0),(-1,-1),.4,colors.HexColor("#D5DDE7")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("TOPPADDING",(0,0),(-1,-1),7),
            ("BOTTOMPADDING",(0,0),(-1,-1),7),
            ("LEFTPADDING",(0,0),(-1,-1),6),
            ("RIGHTPADDING",(0,0),(-1,-1),6),
        ]))
        story.append(t)
    table_group("Rynki bramkowe",report["goal_markets"])
    table_group("Pozostałe rynki: kartki, rożne, faule i inne",report["other_markets"])
    story.append(Spacer(1,2*mm))
    story.append(label("FAULE UNDER | KURSY 1,50–2,00 | ODRĘBNA SEKCJA",heading))
    story.append(label(
        "Lista obserwacyjna, niezależna od głównego TOP. Może zawierać oceny poniżej 67/100; "
        "kursy to historyczne zapisy API. Brak wyliczonego value i brak potwierdzenia STS/Superbet.",sub))
    table_group("FAULE UNDER — do sprawdzenia",report.get("fouls_under") or [])
    story += [
        Spacer(1,4*mm),
        label("WAŻNE: notowanie z API nie oznacza dostępności danego zakładu "
              "w STS, Superbet ani innych polskich serwisach. Przykładowy rynek "
              "kartek może być rozliczany inaczej niż punkty kartek. "
              "Jeśli linia/kurs niedostępne albo mecz już trwa: pomiń.",sub),
        label("Wybory to automatyczny ranking badawczy API Market, nie gotowe zakłady "
              "o udokumentowanej przewadze finansowej. Model KB Score 2.1, "
              "historyczne N i oddzielne modele xG pozostają bez zmian.",sub),
    ]
    def footer(canv,doc):
        canv.saveState()
        canv.setFont("AMShort",6.7)
        canv.setFillColor(muted)
        canv.drawString(13*mm,9*mm,"API Market Scan | wyłącznie źródłowe kursy | sprawdź ofertę przed grą")
        canv.drawRightString(A4[0]-13*mm,9*mm,f"str. {doc.page}")
        canv.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    if not filename.is_file() or filename.stat().st_size<2000 or filename.read_bytes()[:5]!=b"%PDF-":
        raise ValueError("Invalid PDF")
    return filename


def main():
    p=argparse.ArgumentParser()
    p.add_argument("date",nargs="?")
    p.add_argument("--source")
    p.add_argument("--output")
    args=p.parse_args()
    day=target_date(args.date)
    src=Path(args.source or f"data/api_football/market_scan/{day}.json")
    payload=json.loads(src.read_text(encoding="utf-8"))
    if payload.get("date")!=day:
        raise ValueError("Source and report dates differ")
    result=pick_research_positions(payload)
    target=args.output or f"reports/api_market_scan/API_MARKET_PRAKTYCZNE_TYPY_{day}.pdf"
    render_pdf(result,target)
    print(json.dumps({"date":day,"positions":result["total"],
                       "goal_markets":len(result["goal_markets"]),
                       "other_markets":len(result["other_markets"]),
                       "pdf":target,"score_is_calibrated_probability":False,
                       "verified_at_polish_bookmaker":False},ensure_ascii=False))


if __name__=="__main__":
    main()
