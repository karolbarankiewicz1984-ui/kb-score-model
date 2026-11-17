"""Polish bookmaker odds supplement PDF: top shortlist + all verified model markets.

This is not the legacy MULTIMODEL PDF. No edits to existing reports or
research probabilities; publish as a separate clearly-labelled attachment.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from github_models.oddspapi_integration import classify_market

ZONE=ZoneInfo("Europe/Warsaw")
FAMILY_NAMES={"1X2":"1X2","goals":"Bramki","corners":"Rozne",
              "cards":"Kartki","fouls":"Faule"}
POLISH_MARKETS={"1X2":"Wynik meczu","goals":"Bramki O/U",
                "corners":"Rozne O/U","fouls":"Faule O/U"}
MAX_TOP=12


def _clock(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z","+00:00")).astimezone(ZONE).strftime("%d.%m %H:%M")
    except (ValueError,TypeError,AttributeError):
        return "n/d"


def _pct(p):
    if type(p) not in (int,float) or not 0<=p<=1:
        return "—"
    return f"{p*100:.1f}%".replace(".",",")


def _price(p):
    if type(p) not in (int,float) or p<1:
        return "brak"
    return f"{p:.2f}".replace(".",",")


def _label(row):
    kind=POLISH_MARKETS.get(row["market"],row["market"])
    if row["market"]=="1X2":
        return kind+" "+{"1":"1","X":"X","2":"2"}.get(row["selection"],row["selection"])
    return (kind+": "+("powyzej " if row["selection"]=="over" else "ponizej ")+
            str(row["line"]).replace(".",","))


def make_pdf(collection, overlay, audit, output, *, report_date=None, market_gaps=None):
    """Stand-alone Polish PDF; all displayed odds traceable to captured rows."""
    from github_models.abc_pdf_style import fonts, p, render, styles, table, WIDTH
    fonts()
    st=styles()
    story=[]
    story.append(p("GITHUB MULTIMODEL V2 | SUPERBET.PL",st["title"]))
    story.append(p("Niezalezna warstwa kursow OddsPapi | odczyt "+
                   _clock(collection.get("as_of_utc")),st["sub"]))
    story.append(p("BADANIE: Nie sa to skalibrowane prawdopodobienstwa ani gwarancje skutecznosci. "
                   "Model sportowy i warianty A/B/C pozostaja bez zmian. "
                   "STS nie byl dostepny w subskrypcji OddsPapi.",st["body"]))
    links=collection.get("links",{}).get("links",[])
    snapshots=collection.get("snapshots",[])
    comparisons=overlay.get("comparisons",[])
    matched=sum(row.get("status")=="matched" for row in links)
    counts=Counter()
    quotes=0
    for snap in snapshots:
        for row in snap.get("quotes",[]):
            counts[classify_market(row)["family"]]+=1
            quotes+=1
    story.append(p("Stan pobierania i zasieg",st["head"]))
    info=[
        ["Pozycja","Zweryfikowana liczba"],
        ["Superbet - mecze z kursami",str(len(snapshots))],
        ["Zgodne identyfikatory PitchAPI/OddsPapi",str(matched)],
        ["Wszystkie aktywne notowania",str(quotes)],
        ["Porownania dokladnych linii",str(len(comparisons))],
        ["Koszt tego uruchomienia",str(collection.get("billable_requests_made","n/d"))+" zapytania"],
        ["STS","Niedostepny w planie (nie zastapiono innym bukmacherem)"]
    ]
    story.append(table(info,[WIDTH*.64,WIDTH*.36],st))
    story.append(p("Najsilniejsze propozycje z rzeczywistym kursem (min. 1,20)",st["head"]))
    valid=[row for row in comparisons if row.get("eligible_min_odds_1_20") is True]
    ranking=sorted(valid,key=lambda x:(-x["p_model"],x["kickoff_utc"],x["fixture_id"],x["market"]))
    top=[];seen=set()
    for row in ranking:
        fid=row["fixture_id"]
        if fid in seen or row["p_model"]<.70:
            continue
        seen.add(fid);top.append(row)
        if len(top)>=MAX_TOP:break
    header=["Mecz","Typ","P(model)","Kurs","P(rynek)"]
    rows=[header]
    for r in top:
        rows.append([r["home"]+" - "+r["away"],_label(r),
                     _pct(r["p_model"]),_price(r["price"]),
                     _pct(r["market_no_vig_probability"])])
    if len(rows)>1:
        story.append(table(rows,[WIDTH*.30,WIDTH*.31,WIDTH*.13,WIDTH*.11,WIDTH*.15],st))
    else:
        story.append(p("Brak pozycji, dla ktorych jednoczesnie potwierdzono zamrozona prognoze, "
                       "dokladna linie oraz kurs minimum 1,20.",st["body"]))
    story.append(p("Wszystkie dopasowane kategorie - chronologicznie",st["head"]))
    fixture_map=defaultdict(list)
    for r in valid:
        fixture_map[(r["kickoff_utc"],r["fixture_id"],r["home"],r["away"])].append(r)
    if not fixture_map:
        story.append(p("Nie potwierdzono jeszcze wspolnych kategorii kurs/prognoza.",st["body"]))
    for (when,fid,home,away),values in sorted(fixture_map.items()):
        story.append(p(_clock(when)+" | "+home+" - "+away,st["head"]))
        content=[["Rynek","P(model)","Kurs / bukmacher","P(rynek)","Odczyt"]]
        for v in sorted(values,key=lambda r:(r["market"],r["line"],r["selection"])):
            content.append([_label(v),_pct(v["p_model"]),
                            _price(v["price"])+" / Superbet",
                            _pct(v["market_no_vig_probability"]),
                            _clock(v["odds_captured_at_utc"])])
        story.append(table(content,[WIDTH*.26,WIDTH*.12,WIDTH*.22,WIDTH*.15,WIDTH*.25],st))
    story.append(p("Pozostale rzeczywiste rynki (bez prognoz modelu)",st["head"]))
    names=[("goals","Bramki"),("corners","Rozne"),("cards_bookings","Kartki/bookings"),
           ("fouls_match","Faule lacznie"),("player_prop","Statystyki zawodnikow"),
           ("fouls_other","Faule - inne"),("shots_other","Strzaly - inne"),
           ("handicap","Handicapy"),("btts","BTTS"),("other","Inne")]
    coverage=[["Kategoria","Notowania w danych Superbet"]]
    for key,label in names:
        coverage.append([label,str(counts.get(key,0))])
    story.append(table(coverage,[WIDTH*.65,WIDTH*.35],st))
    story.append(p("Celem sekcji jest mapa oferty. Rynek dostepny w API nie oznacza, "
                   "ze model ma dla niego zweryfikowana prognoze. "
                   "Zerowa liczba fauli meczowych nie oznacza zerowej liczby fauli na boisku.",st["small"]))
    # Preserve strongest original predictions even when Superbet has no usable
    # exact market/line quote. Do not assign a fabricated price or fair probability.
    if market_gaps is not None:
        story.append(p("Prognozy modelu bez porownywalnego kursu Superbet",st["head"]))
        summary = [["Kategoria", "Prognozy >=67%", "Bez zgodnego kursu"]]
        for code, label in (("goals","Bramki"),("corners","Rozne"),
                            ("fouls","Faule lacznie"),("cards","Zolte kartki")):
            item = market_gaps.get("by_market",{}).get(code,{})
            summary.append([label,str(item.get("high_confidence_candidates",0)),
                            str(item.get("no_verified_comparable_quote",0))])
        story.append(table(summary,[WIDTH*.48,WIDTH*.25,WIDTH*.27],st))
        story.append(p("Kurs: BRAK w porownywalnym rynku. Pozycje ponizej NIE sa typami do "
                       "obstawienia. Zolte kartki modelu nie sa automatycznie tym samym "
                       "co rynki Bookings/points Superbet, a faule zawodnika nie sa suma fauli.",st["small"]))
        no_quote=market_gaps.get("model_only_candidates",[])[:25]
        if no_quote:
            missing=[["Mecz", "Rynek modelu", "P(model)", "Przyczyna"]]
            reason={"booking_rules_unverified":"rozliczenie kartek niejasne",
                    "no_verified_yellow_cards_offer":"brak kartki",
                    "player_props_not_match_total":"tylko rynki zawodnikow",
                    "no_exact_market_line":"brak tej linii",
                    "only_offer_below_minimum_odds":"kurs ponizej 1,20"}
            for item in no_quote:
                missing.append([
                    _clock(item["kickoff_utc"])+" "+item["home"]+"-"+item["away"],
                    _label(item),_pct(item["model_probability"]),
                    reason.get(item["status"],item["status"])])
            story.append(table(missing,[WIDTH*.35,WIDTH*.28,WIDTH*.12,WIDTH*.25],st))
    story.append(p("Audyt historyczny i warianty eksperymentalne",st["head"]))
    tested=(audit or {}).get("metrics",[])
    if tested:
        aud=[["Wariant","n","Trafnosc","Brier","Log loss"]]
        for a in tested:
            aud.append([a["variant"],str(a["n"]),_pct(a["hit_rate"]),
                        f'{a["brier"]:.3f}',f'{a["log_loss"]:.3f}'])
        story.append(table(aud,[WIDTH*.40,WIDTH*.08,WIDTH*.15,WIDTH*.16,WIDTH*.21],st))
        story.append(p("Metryki maja charakter retrospektywny. "
                       "Zmiana algorytmu produkcyjnego wymaga niezaleznych prob przyszlych meczow.",st["small"]))
    else:
        story.append(p("Brak zakonczo­nych i dokladnie rozliczonych, jednoczesnie zamrozonych "
                       "par prognoza/kurs. Nie podajemy wymyslonych statystyk skutecznosci.",st["body"]))
    return render(story,output,"GitHub Models V2 | Polish odds research supplement")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--collection",required=True)
    p.add_argument("--overlay",required=True)
    p.add_argument("--audit")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    load=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    make_pdf(load(a.collection),load(a.overlay),load(a.audit) if a.audit else None,a.output)
    print("ODDS_RESEARCH_PDF="+a.output)


if __name__=="__main__":
    main()
