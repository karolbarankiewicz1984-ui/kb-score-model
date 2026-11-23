"""Two MultiModel V2 user-facing PDFs, read-only from frozen GitHub Actions artifacts.

No odds requests, probability re-estimation, invented prices, or production
changes. Exact ABC/SHADOW/OddsPapi queue provenance is mandatory.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime
from html import escape
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, LongTable, Paragraph, Spacer, TableStyle, KeepTogether

ZONE = ZoneInfo("Europe/Warsaw")
MARKETS = {"1X2":"Wynik 1X2","double_chance":"Podwójna szansa","goals":"Bramki","corners":"Rzuty rożne",
           "fouls":"Faule","cards":"Kartki","btts":"BTTS","handicap":"Handicap"}

def load(root, path, optional=False):
    p = Path(root) / path
    if not p.exists() and optional:
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def moment(value):
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(ZONE)

def percent(x):
    return "—" if x is None else ("%.1f%%" % (float(x)*100)).replace(".",",")

def number(x):
    return "—" if x is None else ("%.2f" % float(x)).replace(".",",")

def key(row):
    return (str(row["fixture_id"]), str(row["market"]), str(row["selection"]),
            str(row.get("line") if row.get("line") is not None else ""))

def market_label(r):
    m, s, line = r["market"], r["selection"], r.get("line")
    if m == "1X2":
        return {"1":"Wygrana gospodarzy","X":"Remis","2":"Wygrana gości"}.get(s,s)
    if m == "double_chance":
        choices = {"1X": "Gospodarze lub remis (1X)",
                   "X2": "Remis lub goście (X2)",
                   "12": "Gospodarze lub goście (12)"}
        if s not in choices or line is not None:
            raise ValueError("invalid_double_chance_identity")
        return choices[s]
    if m == "btts":
        return "Obie drużyny strzelą — " + ("TAK" if s=="yes" else "NIE")
    if m == "handicap":
        return ("Gospodarze " if s=="home" else "Goście ") + ("%+g" % float(line)).replace(".",",")
    side = {"over":"powyżej","under":"poniżej"}.get(s,s)
    suffix = (" " + str(line).replace(".",",")) if line is not None else ""
    return MARKETS.get(m,m)+" "+side+suffix

def pdf_style():
    path="/usr/share/fonts/truetype/dejavu/"
    pdfmetrics.registerFont(TTFont("Multi",path+"DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("MultiBold",path+"DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFontFamily("Multi",normal="Multi",bold="MultiBold")
    return {
        "title":ParagraphStyle("T",fontName="MultiBold",fontSize=16,leading=21,
                               textColor=colors.HexColor("#192E45"),spaceAfter=9),
        "head":ParagraphStyle("H",fontName="MultiBold",fontSize=10,leading=14,
                              textColor=colors.HexColor("#213D5A"),spaceBefore=12,spaceAfter=4),
        "body":ParagraphStyle("B",fontName="Multi",fontSize=8,leading=12,spaceAfter=6),
        "cell":ParagraphStyle("C",fontName="Multi",fontSize=7,leading=10),
        "tablehead":ParagraphStyle("TH",fontName="MultiBold",fontSize=7,leading=10,
                                   textColor=colors.white)
    }

def paragraph(x,style):
    return Paragraph(escape(str(x)),style)

def make_table(headings, rows, widths, st):
    if not rows:
        return paragraph("Brak pozycji.",st["body"])
    data=[[paragraph(h,st["tablehead"]) for h in headings]]
    data.extend([[paragraph(c,st["cell"]) for c in row] for row in rows])
    t=LongTable(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#213A56")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.white,colors.HexColor("#F0F4F8")]),
        ("GRID",(0,0),(-1,-1),.2,colors.HexColor("#CBD5E0")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)
    ]))
    return t

def export_pdf(path, story):
    path=Path(path)
    doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=14*mm,
        rightMargin=14*mm,topMargin=15*mm,bottomMargin=15*mm)
    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont("Multi",7)
        canvas.drawString(14*mm,9*mm,"MULTIMODEL V2 | Dane badawcze — niegwarantowana skuteczność")
        canvas.drawRightString(A4[0]-14*mm,9*mm,"Strona "+str(doc.page))
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    if path.stat().st_size<1500 or path.read_bytes()[:5]!=b"%PDF-":
        raise ValueError("Bad PDF: "+str(path))

def build_day(abc_root,odds_root,day,dest):
    p="reports/github_models/"
    q=load(abc_root,p+f"queues/{day}.json")
    a=load(abc_root,p+f"filters/ABC_{day}.json")
    shadow=load(abc_root,p+f"shadow/{day}.json",True)
    oq=load(odds_root,"pitch_queue.json")
    market=load(odds_root,"market_overlay.json")
    sq=load(odds_root,"SHADOW_SUPERBET_OVERLAY.json",True)
    if q!=oq or q.get("generated_at_utc")!=a.get("input_cutoff_utc"):
        raise ValueError("ABC/Superbet frozen inputs differ")
    if market.get("bookmakers")!=["superbet.pl"] or not market.get("research_only"):
        raise ValueError("Unverified bookmaker provenance")
    if shadow and shadow.get("generated_at_utc")!=q.get("generated_at_utc"):
        raise ValueError("SHADOW/ABC cutoff mismatch")
    if sq and sq.get("forecast_cutoff_utc")!=q.get("generated_at_utc"):
        raise ValueError("SHADOW/Superbet cutoff mismatch")
    fixtures={str(f["fixture_id"]):f for f in q["fixtures"]
              if moment(f["kickoff_utc"]).date().isoformat()==day}
    rows={}
    for c in a["candidates"]:
        fid=str(c["fixture_id"])
        if fid not in fixtures:
            continue
        k=key(c)
        probability=c.get("probability",c.get("probability_min"))
        if type(probability) not in (int,float) or not math.isfinite(probability) or not 0<=probability<=1:
            raise ValueError("Invalid ABC probability")
        if k not in rows:
            rows[k]={**c,"probability":probability,"kind":"ABC",
                     "variants":set(),"odds":None}
        rows[k]["variants"].add(c["variant"])
    for c in market["comparisons"]:
        k=key(c)
        if k not in rows or c.get("bookmaker")!="superbet.pl":
            continue
        pr=c.get("price")
        if not c.get("eligible_min_odds_1_20") or type(pr) not in (int,float) or pr<1.20:
            continue
        if abs(float(c.get("p_model",-1))-rows[k]["probability"])>0.00001:
            continue
        if moment(c["odds_captured_at_utc"])>=moment(fixtures[k[0]]["kickoff_utc"]):
            continue
        rows[k]["odds"]=pr
    if shadow:
        for c in shadow["candidates"]:
            if str(c["fixture_id"]) not in fixtures:
                continue
            k=key(c)
            if k in rows:
                raise ValueError("Duplicate ABC/SHADOW market key")
            rows[k]={**c,"kind":"SHADOW","variants":set(),"odds":None}
    if sq:
        for c in sq["rows"]:
            k=key(c)
            if k not in rows or rows[k]["kind"]!="SHADOW" or c.get("status")!="quoted_research":
                continue
            pr=c.get("odds")
            if type(pr) not in (int,float) or pr<1.20:
                continue
            if abs(float(c["probability"])-rows[k]["probability"])>0.00001:
                continue
            if moment(c["price_captured_at_utc"])>=moment(fixtures[k[0]]["kickoff_utc"]):
                continue
            rows[k]["odds"]=pr
    # Exact, independently documented OddsPapi Asian half-goal market
    # identity. Retain SHADOW research status; do not imply real book payouts.
    priced_shadow_by_market = {"btts": 0, "handicap": 0}
    if shadow:
        from github_models.priced_shadow_settlement import quote_pairs
        matched_quotes, quote_exclusions = quote_pairs(
            load(odds_root,"collection.json"), q, shadow)
        for quote in matched_quotes:
            k = key(quote)
            # OddsPapi archives seven days, but this PDF is ONE local day.
            # Ignore correctly frozen quotes outside this report's date.
            if k[0] not in fixtures:
                continue
            if k not in rows or rows[k]["kind"] != "SHADOW":
                raise ValueError("quoted_shadow_not_in_frozen_pdf_rows")
            if rows[k]["probability"] != quote["p_model"]:
                raise ValueError("quoted_model_probability_mismatch")
            if rows[k]["odds"] is not None and rows[k]["odds"] != quote["price"]:
                raise ValueError("conflicting_quote_between_independent_adapters")
            if k[0] in fixtures:
                rows[k]["odds"] = quote["price"]
                rows[k]["price_status"] = "archived_exact_research"
                priced_shadow_by_market[quote["market"]] += 1
    st=pdf_style()
    def P(x,kind="body"):
        return paragraph(x,st[kind])
    grouped=defaultdict(list)
    for row in rows.values():
        grouped[str(row["fixture_id"])].append(row)
    abc_count=sum(r["kind"]=="ABC" for r in rows.values())
    shadow_count=sum(r["kind"]=="SHADOW" for r in rows.values())
    priced=sum(r["odds"] is not None for r in rows.values())
    story=[P("MULTIMODEL — "+day,"title"),
           P("Jeden raport: A/B/C, SHADOW oraz rzeczywiste zapisane kursy Superbet."),
           P("Prawdopodobieństwa niekalibrowane. Kursy mogą być już nieaktualne. "
             "Nie stosujemy oceny punktowej 67/100. Kurs poniżej 1,20 nie jest prezentowany. "
             "Handicapy azjatyckie ±1,5: kursy archiwalne, badawcze, niekalibrowane. "
             "Podwójna szansa 1X/X2/12: suma dwóch rozłącznych wyników 1X2, "
             "bez gwarancji dostępności kursu."),
           P(f"Zamrożenie: {moment(q['generated_at_utc']):%d.%m.%Y %H:%M} | "
             f"Oferta Superbet: {moment(market['as_of_utc']):%d.%m.%Y %H:%M} | "
             f"Mecze: {len(fixtures)} | A/B/C: {abc_count} | SHADOW: {shadow_count} | Z kursem: {priced}"),
           P("Najważniejsze do przeglądu (maksymalnie 3 na mecz)","head")]
    leaders=[]
    for fid,items in grouped.items():
        leaders.extend(sorted(items,key=lambda z:(z["odds"] is None,-z["probability"]))[:3])
    leaders.sort(key=lambda z:(z["odds"] is None,-z["probability"]))
    leading=[]
    for row in leaders[:35]:
        f=fixtures[row["fixture_id"]]
        leading.append([moment(f["kickoff_utc"]).strftime("%H:%M"),
                        f["home"]+" – "+f["away"],market_label(row),
                        percent(row["probability"]),number(row["odds"]),row["kind"]])
    story.append(make_table(["Godz.","Mecz","Rynek","P","Kurs","Model"],
                            leading,[37,131,152,48,45,52],st))
    if len(leaders)>35:
        story.append(P(f"Pozostałe {len(leaders)-35} propozycje znajdują się poniżej przy meczach."))
    story.append(P("Wszystkie rynki, pogrupowane według meczu i godziny","head"))
    for fid in sorted(grouped,key=lambda x:(moment(fixtures[x]["kickoff_utc"]),fixtures[x]["home"])):
        f=fixtures[fid]
        story.append(KeepTogether([P(f"{moment(f['kickoff_utc']):%H:%M} | {f['home']} – {f['away']} | {f.get('league','')}","head"),Spacer(1,2)]))
        rr=[]
        for row in sorted(grouped[fid],key=lambda x:(list(MARKETS).index(x["market"]) if x["market"] in MARKETS else 9,
                                                      x["kind"]!="ABC",-x["probability"])):
            variant="/".join(sorted(row["variants"])) if row["kind"]=="ABC" else "SHADOW"
            rr.append([market_label(row),percent(row["probability"]),number(row["odds"]),
                       variant,"z kursem" if row["odds"] is not None else "bez kursu"])
        story.append(make_table(["Rynek","P modelu","Superbet","Model","Status"],
                                rr,[195,67,60,65,78],st))
    story.append(P("Braki i ograniczenia","head"))
    story.append(P("Faule i kartki bez potwierdzonej zgodności źródeł pozostają badawcze, "
                   "bez przypisywania nieodpowiednich rynków i kursów. "
                   "BTTS i azjatyckie handicapy ±1,5 otrzymują jedynie dokładnie "
                   "dopasowane ceny archiwalne Superbet; nie jest to potwierdzenie "
                   "wypłaty bukmachera ani przewagi modelu. "
                   "Strzały, strzały celne i spalone nadal wymagają danych. "
                   "Nie utożsamiamy wariantów A/B/C z dostępnością kursów."))
    export_pdf(dest,story)
    return dict(fixtures=len(fixtures),abc=abc_count,shadow=shadow_count,
                with_odds=priced, priced_shadow_by_market=priced_shadow_by_market)

def build_audit(abc_root,odds_root,audit_root,day,dest):
    # Inventory of exact stored Superbet market names; no odds API requests.
    from github_models.market_rule_gate import audit as market_rule_audit
    semantics = market_rule_audit(load(odds_root,"collection.json"),
                                  load(odds_root,"market_gaps.json",True))
    p="reports/github_models/"
    a=load(abc_root,p+f"filters/AUDIT_{day}.json")
    s=load(abc_root,p+f"shadow/SHADOW_AUDIT_{day}.json",True)
    b=load(audit_root,"REPLAY_AUDIT.json",True) if audit_root else None
    priced_settlement=(load(audit_root,"PRICED_SHADOW_SETTLEMENT.json",True)
                       if audit_root else None)
    st=pdf_style()
    def P(x,kind="body"):
        return paragraph(x,st[kind])
    story=[P("MULTIMODEL — AUDYT "+day,"title"),
           P("Jeden audyt: modele A/B/C, nowe rynki SHADOW i zapisane kursy Superbet."),
           P("Historyczny wynik A/B/C nie dowodzi opłacalności nowych propozycji. "
             "Brak rozliczonych rynków Superbet nie oznacza 0% trafności."),
           P("1. Audyt historyczny A/B/C","head"),
           P(f"Archiwa: {a.get('archives_processed',0)} | "
             f"Rekordy unikalne: {a.get('unique_candidate_records',0)} | "
             f"Duplikaty pominięte: {a.get('duplicate_snapshots_suppressed',0)}")]
    summary=[]
    for row in a.get("summary",[]):
        if row.get("market")=="all":
            summary.append([row["variant"],str(row["settled"]),str(row["unresolved"]),
                            percent(row.get("hit_rate")),str(row.get("unique_fixtures",0)),
                            ("%.3f"%row["brier"]) if row.get("brier") is not None else "—"])
    story.append(make_table(["Wariant","Rozliczone","Nierozliczone","Trafność","Mecze","Brier"],
                            summary,[75,89,96,74,67,64],st))
    story.append(P("Podział według rynku — wariant A","head"))
    by=[]
    for row in a.get("summary",[]):
        if row.get("variant")=="A" and row.get("market")!="all":
            by.append([MARKETS.get(row["market"],row["market"]),str(row["settled"]),
                       str(row["unresolved"]),percent(row.get("hit_rate"))])
    story.append(make_table(["Rynek","Rozliczone","Nierozliczone","Trafność"],
                            by,[155,108,118,84],st))
    story.append(P("2. Rozliczanie SHADOW","head"))
    if s:
        story.append(P(f"Archiwa SHADOW: {s.get('archives_processed',0)} | "
                       f"Prognozy: {s.get('unique_forecasts',0)} | "
                       f"Rozliczone: {s.get('status',{}).get('settled',0)}."))
        story.append(P(
            "Uwaga do SHADOW: status nierozstrzygnięty obejmuje także "
            "przypadki, w których niezależne źródło jeszcze nie udostępniło "
            "wyniku według konserwatywnej reguły daty meczu + 2 dni. "
            "To nie dowodzi błędu dopasowania ani przegranej."))
        sr=[[MARKETS.get(x["market"],x["market"]),str(x.get("settled",0)),
             percent(x.get("hit_rate"))] for x in s.get("summary",[])]
        if sr:
            story.append(make_table(["Rynek","Rozliczone","Trafność"],sr,[240,112,113],st))
        else:
            story.append(P("Pierwszy audyt nie zawiera jeszcze wyników SHADOW. "
                           "Nie dopisujemy zerowych ani wymyślonych wskaźników."))
    else:
        story.append(P("Nie udostępniono raportu rozliczania SHADOW."))
    story.append(P("3. Niezależny audyt Superbet","head"))
    if b:
        story.append(P(f"Archiwa z kursami: {b.get('archives_processed',0)} | "
                       f"Unikalne rozliczone mecze: {b.get('unique_settled_fixtures',0)} | "
                       f"Przyszłe pozycje do rozliczenia: {b.get('pending_future_quotes',0)}."))
        story.append(P("Decyzja: "+str(b.get("decision","brak wystarczających danych"))))
    else:
        story.append(P("Brak audytu kursów — wyniki i ROI pozostają nieustalone."))
    story.append(P("4. Rozliczanie BTTS i handicapu ±1,5 na zapisanych kursach","head"))
    if priced_settlement and priced_settlement.get("schema")=="multimodel-priced-shadow-outcomes-v1":
        story.append(P(
            f"Zamrożone archiwa z cenami: {priced_settlement.get('archived_oddspapi_collections',0)} | "
            f"Unikalne wycenione typy: {priced_settlement.get('exact_quoted_selections',0)} | "
            f"Rozliczone: {priced_settlement.get('status',{}).get('settled',0)}. "
            "Wyniki niezależne od bukmachera, bez potwierdzenia wypłaty Superbet."))
        counts = priced_settlement.get("status", {})
        reasons = priced_settlement.get("status_reason_counts", {})
        story.append(P(
            f"Oczekujące: {counts.get('pending',0)} | "
            f"Nierozstrzygnięte: {counts.get('unresolved',0)} | "
            f"Brak publikacji wyniku w pierwszych 48 h od rozpoczęcia: "
            f"{reasons.get('pending:independent_result_publication_grace_48h',0)}. "
            "Wynik i uzasadnienie można podać dopiero po niezależnej obserwacji."))
        pr=[]
        for k, name in (("btts","BTTS"),("handicap","Handicap ±1,5")):
            x=priced_settlement.get("market_summary",{}).get(k,{})
            pr.append([name,str(x.get("quoted_research",0)),
                       str(x.get("settled",0)),percent(x.get("hit_rate"))])
        story.append(make_table(["Rynek","Zapisane kursy","Rozliczone","Trafność"],
                                pr,[163,115,103,84],st))
    else:
        story.append(P("Próba cenowa SHADOW oczekuje na pierwszy uruchomiony audyt "
                       "po weryfikacji rzeczywistych wyników. "
                       "Brak wartości nie oznacza przegranej."))
    story.append(P("5. Kontrola zgodności rynków Superbet","head"))
    families = semantics["family_counts"]
    gaps = semantics.get("model_vs_bookmaker_gaps", {})
    story.append(P(
        f"Sprawdzono {semantics['quotes_checked']} zapisanych ofert. "
        f"Faule zawodników: {families.get('player_fouls',0)}; "
        f"bookings/kartki: {families.get('bookings_or_cards',0)}; "
        f"handicapy azjatyckie: {families.get('asian_handicap',0)}; "
        f"handicapy europejskie: {families.get('european_handicap',0)}."))
    story.append(P(
        "Blokady: fauli zawodnika nie wolno utożsamiać z faulami całego meczu. "
        "Bookingi nie są automatycznie żółtymi kartkami. Znak i strona "
        "azjatyckiego handicapu ±1,5 zostały zweryfikowane w dokumentacji "
        "OddsPapi. Faktyczna wypłata Superbet nie jest niezależnie "
        "potwierdzona; handicap europejski (3 drogi) to inny rynek."))
    if gaps:
        fouls = gaps.get("fouls", {})
        cards = gaps.get("cards", {})
        story.append(P(
            f"Bez porównywalnego kursu: faule "
            f"{fouls.get('without_comparable_offer','—')} / "
            f"{fouls.get('modeled_candidates','—')}; "
            f"kartki {cards.get('without_comparable_offer','—')} / "
            f"{cards.get('modeled_candidates','—')}. "
            "Brak ceny nie oznacza przegranej prognozy."))
    story.append(P(
        "Przed formalną kalibracją: prospektywna próba niezależnie rozliczonych "
        "meczów, Brier/log loss na holdoucie, osobna walidacja fauli i kartek "
        "według OPTA. Historyczne trafności A/B/C nie są potwierdzeniem "
        "trafności zakładów Superbet."))
    export_pdf(dest,story)
    return dict(abc_archives=a.get("archives_processed",0),
                shadow_archives=s.get("archives_processed",0) if s else None,
                bookmaker_settled=b.get("unique_settled_fixtures",0) if b else None,
                market_rules_quotes=semantics["quotes_checked"],
                market_rules_automatic_promotions=len(semantics["automatically_promoted_markets"]))

def main():
    parser=argparse.ArgumentParser()
    for n in ("abc-dir","odds-dir","output-dir","day"):
        parser.add_argument("--"+n,required=True)
    parser.add_argument("--audit-dir")
    arg=parser.parse_args()
    out=Path(arg.output_dir);out.mkdir(parents=True,exist_ok=True)
    one=build_day(arg.abc_dir,arg.odds_dir,arg.day,out/f"MULTIMODEL_{arg.day}.pdf")
    two=build_audit(arg.abc_dir,arg.odds_dir,arg.audit_dir,arg.day,
                    out/f"MULTIMODEL_AUDYT_{arg.day}.pdf")
    state={"schema":"multimodel-two-final-pdfs-v1","day":arg.day,
           "prognoses":one,"audit":two,"minimum_verified_odds":1.20,
           "quality_67_points_mandatory":False,"raw_archives_untouched":True,
           "added_paid_api_calls":0}
    (out/"manifest.json").write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(state,ensure_ascii=False))
if __name__=="__main__":
    main()
