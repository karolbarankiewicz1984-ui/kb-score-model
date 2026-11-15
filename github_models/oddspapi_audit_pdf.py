"""Readable, conservative postmatch OddsPapi experimental audit PDF."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def render_audit(data, outpath):
    from github_models.abc_pdf_style import fonts,p,render,styles,table,WIDTH
    fonts()
    st=styles()
    story=[
        p("MULTIMODEL V2 | AUDYT SUPERBET.PL",st["title"]),
        p("Niezalezne rozliczenia historycznych, zamrozonych prognoz",st["sub"]),
        p("Nie jest to ranking bukmacherow ani dowod przewagi finansowej. "
          "Kursy i prognozy musza byc archiwizowane przed meczem. "
          "Nie zmieniono wag modelu produkcyjnego.",st["body"]),
        p("Stan probki",st["head"]),
    ]
    rows=[["Parametr","Wartosc"],
          ["Archiwa wejsciowe",str(data.get("archives_processed",0))],
          ["Unikatowe oferty",str(data.get("unique_selection_quotes",0))],
          ["Rozliczone oferty",str(data.get("settled_selection_quotes",0))],
          ["Rozliczone mecze",str(data.get("unique_settled_fixtures",0))],
          ["Wykluczone duplikaty",str(data.get("duplicates_suppressed",0))],
          ["Prog 100 meczow","TAK" if data.get("promotion_gate",{}).get("minimum_reached") else "NIE"]]
    story.append(table(rows,[WIDTH*.65,WIDTH*.35],st))
    story.append(p("Warianty porownawcze - dane rzeczywiste",st["head"]))
    metrics=data.get("summary",[])
    if not metrics:
        story.append(p("Brak jeszcze wystarczajacych, jednoznacznie rozliczonych pozycji. "
                       "Nie publikujemy nieistniejacych wynikow.",st["body"]))
    else:
        out=[["Wariant","n","Trafnosc","Brier","Log loss"]]
        for item in metrics:
            out.append([item["variant"],str(item["n"]),
                       ("%.1f%%"%(100*item["hit_rate"])).replace(".",","),
                       ("%.3f"%item["brier"]).replace(".",","),
                       ("%.3f"%item["log_loss"]).replace(".",",")])
        story.append(table(out,[WIDTH*.40,WIDTH*.08,WIDTH*.15,WIDTH*.17,WIDTH*.20],st))
    story.append(p("Wyniki wedlug rodzaju rynku",st["head"]))
    groups=data.get("by_market",[])
    if groups:
        out=[["Wariant / rynek","n","Trafnosc","Brier"]]
        for g in groups:
            out.append([g["variant"]+" / "+g["market"],str(g["n"]),
                        ("%.1f%%"%(100*g["hit_rate"])).replace(".",","),
                        ("%.3f"%g["brier"]).replace(".",",")])
        story.append(table(out,[WIDTH*.57,WIDTH*.11,WIDTH*.16,WIDTH*.16],st))
    else:
        story.append(p("Brak rozliczonych rynkow do wiarygodnego porownania.",st["body"]))
    story.append(p("Progi prawdopodobienstwa",st["head"]))
    bands=data.get("by_probability_band",[])
    if bands:
        out=[["Wariant / przedzial","n","Trafnosc"]]
        for b in bands:
            out.append([b["variant"]+" / "+b["band"],str(b["n"]),
                        ("%.1f%%"%(100*b["hit_rate"])).replace(".",",")])
        story.append(table(out,[WIDTH*.65,WIDTH*.12,WIDTH*.23],st))
    else:
        story.append(p("Kalibracja czeka na rozliczone prognozy.",st["body"]))
    story.append(p("Decyzja",st["head"]))
    story.append(p("BRAK ZGODY NA AUTOMATYCZNA ZMIANE PRODUKCJI. "
                   "Roznice na niewielkiej lub retrospektywnej probce wymagaja "
                   "weryfikacji na przyszlych spotkaniach.",st["body"]))
    render(story,outpath,"GitHub Models V2: independent bookmaker odds audit")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    data=json.loads(Path(a.input).read_text(encoding="utf-8"))
    render_audit(data,a.output)
    print("ODDS_AUDIT_PDF="+a.output)


if __name__=="__main__":
    main()
