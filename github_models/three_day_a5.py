"""Exactly three A5 MultiModel research PDFs: today, tomorrow, day after.

Read-only rendering of frozen GitHub Models V2 A/B/C queue and candidates.
A missing fixture/market does not become a bet; no odds are invented.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, KeepTogether

from github_models.report_freshness import WARSAW, MAX_AGE, MIN_LEAD, StaleReportError, aware

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FAMILIES = {
    "1X2": "Wynik", "double_chance": "Podwójna szansa",
    "goals": "Bramki", "corners": "Rożne", "fouls": "Faule", "cards": "Kartki",
    "btts": "BTTS", "handicap": "Handicap",
}


def source_gate(queue, selected, *, now_utc=None):
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = now.astimezone(WARSAW).date().isoformat()
    if queue.get("schema") != "github-models-fixture-queue-v1":
        raise StaleReportError("invalid_frozen_abc_queue")
    source = aware(queue.get("generated_at_utc"), "abc_queue_timestamp")
    if source > now or now - source > MAX_AGE or source.astimezone(WARSAW).date().isoformat() != today:
        raise StaleReportError("no_fresh_abc_queue_for_three_day_report")
    if selected.get("input_cutoff_utc") != queue.get("generated_at_utc"):
        raise StaleReportError("abc_candidates_queue_cutoff_mismatch")
    days = [(now.astimezone(WARSAW).date() + timedelta(days=i)).isoformat() for i in range(3)]
    if not isinstance(queue.get("dates"), list) or queue["dates"][:3] != days:
        raise StaleReportError("abc_queue_three_dates_mismatch")
    if not isinstance(selected.get("candidates"), list):
        raise StaleReportError("abc_candidates_missing")
    fixtures, ids = {}, set()
    for fixture in queue.get("fixtures", []):
        fid = str(fixture.get("fixture_id"))
        if not fid or fid == "None" or fid in ids:
            raise StaleReportError("abc_invalid_or_duplicate_fixture")
        ids.add(fid)
        kickoff = aware(fixture.get("kickoff_utc"), "kickoff_utc")
        if kickoff <= source:
            raise StaleReportError("postmatch_fixture_in_source_queue")
        fixtures[fid] = (fixture, kickoff)
    for row in selected["candidates"]:
        if str(row.get("fixture_id")) not in fixtures:
            raise StaleReportError("candidate_with_unknown_fixture_id")
        p = row.get("probability_min", row.get("probability"))
        if type(p) not in (int, float) or not 0 <= p <= 1:
            raise StaleReportError("invalid_abc_probability")
        if row.get("variant") not in ("A", "B", "C"):
            raise StaleReportError("invalid_abc_variant")
    return today, days, source, fixtures, now


def _market(r):
    market = FAMILIES.get(r.get("market"), str(r.get("market", "rynek")))
    side = {"1": "1", "X": "X", "2": "2", "1X": "1X", "X2": "X2",
            "12": "12", "over": "powyżej", "under": "poniżej",
            "yes": "TAK", "no": "NIE"}.get(str(r.get("selection")),str(r.get("selection")))
    line = "" if r.get("line") is None else " " + str(r["line"]).replace(".", ",")
    return f"{market}: {side}{line}"


def summarize(queue, selected, *, now_utc=None):
    today, days, stamp, fixtures, now = source_gate(queue, selected, now_utc=now_utc)
    missing, invalid, partial = (set(queue.get(k, [])) for k in
                                  ("missing_dates", "invalid_dates", "partial_dates"))
    reports = []
    for day in days:
        groups = defaultdict(dict)
        excluded_started = 0
        for row in selected["candidates"]:
            fid = str(row["fixture_id"])
            fixture, kickoff = fixtures[fid]
            if kickoff.astimezone(WARSAW).date().isoformat() != day:
                continue
            if kickoff <= now + MIN_LEAD:
                excluded_started += 1
                continue
            key = (str(row.get("market")), str(row.get("selection")),
                   str(row.get("line")), str(row.get("model")), str(row.get("scope")))
            existing = groups[fid].get(key)
            p = row.get("probability_min", row.get("probability"))
            if existing:
                if abs(existing["probability"] - p) > 1e-9:
                    raise StaleReportError("conflicting_abc_candidates_same_market")
                existing["variants"].add(row["variant"])
            else:
                groups[fid][key] = {"probability": p, "variants": {row["variant"]},
                                    "label": _market(row)}
        fixture_rows = []
        for fid in sorted(groups, key=lambda x: (fixtures[x][1],x)):
            f, kickoff = fixtures[fid]
            rows = sorted(groups[fid].values(), key=lambda x: (-x["probability"],x["label"]))
            fixture_rows.append({
                "fixture_id": fid, "home": f.get("home"), "away": f.get("away"),
                "league": f.get("league"), "kickoff_utc": kickoff.isoformat(),
                "market_rows": [
                    {"label": r["label"], "probability": r["probability"],
                     "variants": "/".join(sorted(r["variants"]))}
                    for r in rows
                ],
                "preview_count": min(3, len(rows)),
            })
        status = ("source_missing" if day in missing else
                  "source_invalid" if day in invalid else
                  "source_partial" if day in partial else
                  "frozen_abc_research")
        reports.append({"date": day, "source_status": status,
                        "excluded_started_candidates": excluded_started,
                        "fixtures": fixture_rows,
                        "raw_eligible_candidates": sum(len(x["market_rows"]) for x in fixture_rows),
                        "fixtures_with_candidates": len(fixture_rows)})
    return {"schema": "multimodel-three-day-a5-v1",
            "base_day": today, "cutoff_utc": stamp.isoformat(),
            "generated_at_utc": now.isoformat(),
            "research_only": True, "calibration_authorized": False,
            "odds_verified": False, "paid_api_calls": 0,
            "reports": reports}


def render(report, out):
    for font, filename in (("ThreeA5", "DejaVuSans.ttf"),
                           ("ThreeA5Bold", "DejaVuSans-Bold.ttf")):
        if not (FONT_DIR / filename).is_file():
            raise RuntimeError("missing_dejavu_font")
        pdfmetrics.registerFont(TTFont(font, str(FONT_DIR / filename)))
    body = ParagraphStyle("threeBody", fontName="ThreeA5",fontSize=8.2, leading=11.8,
                          textColor=colors.HexColor("#213240"),spaceAfter=5)
    small = ParagraphStyle("threeSmall",parent=body,fontSize=7.2,leading=10.3,
                           textColor=colors.HexColor("#526772"))
    title = ParagraphStyle("threeTitle",parent=body,fontName="ThreeA5Bold",
                           fontSize=15,leading=20,spaceAfter=9)
    sub = ParagraphStyle("threeSub",parent=body,fontName="ThreeA5Bold",
                         fontSize=10,leading=13,spaceBefore=10,spaceAfter=6)
    def P(txt, style=body):
        return Paragraph(escape(str(txt)), style)
    story=[P("MULTIMODEL — " + report["date"], title),
           P("Badawcze prognozy A/B/C z rzeczywistego zamrożenia. "
             "BEZ ZWERYFIKOWANYCH KURSÓW — NIE GOTOWY KUPON.", small),
           P(f"Status źródła: {report['source_status']} | "
             f"Mecze z kandydatami: {report['fixtures_with_candidates']} | "
             f"Rynki: {report['raw_eligible_candidates']}", small)]
    if report["excluded_started_candidates"]:
        story.append(P(f"Odrzucono rozpoczęte lub zbyt bliskie rozpoczęcia pozycje: "
                       f"{report['excluded_started_candidates']}.",small))
    if not report["fixtures"]:
        story.append(P("BRAK WERYFIKOWALNYCH PRZEDMECZOWYCH PROPOZYCJI", sub))
        story.append(P("Brak aktualnych, datowo poprawnych pozycji w zamrożonym źródle. "
                       "Nie przenosimy typów z poprzedniego dnia ani nie szacujemy kursów."))
    for match in report["fixtures"]:
        time = aware(match["kickoff_utc"],"kickoff_utc").astimezone(WARSAW).strftime("%H:%M")
        story.append(KeepTogether([P(f"{time} | {match['home']} – {match['away']}", sub),
                                   P(match.get("league") or "Liga niepotwierdzona", small)]))
        story.append(P("Najsilniejsze trzy pozycje do analizy:",small))
        for row in match["market_rows"][:3]:
            story.append(P(f"{row['label']} | P={row['probability']*100:.1f}% "
                           f"| wariant {row['variants']} | kurs: brak",body))
        if len(match["market_rows"])>3:
            story.append(P("Pozostałe rynki (pełny wykaz):",small))
            for row in match["market_rows"][3:]:
                story.append(P(f"{row['label']} | P={row['probability']*100:.1f}% | "
                               f"{row['variants']} | kurs: brak",small))
    story.append(Spacer(1,8))
    story.append(P("Prawdopodobieństwa surowe, niekalibrowane. "
                   "Próg rzeczywistego kursu Superbet ≥1,20 dotyczy wyłącznie "
                   "osobno potwierdzonych notowań, których ten raport nie zawiera.",small))
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(out),pagesize=A5,leftMargin=22,rightMargin=22,
                      topMargin=26,bottomMargin=27,title="MultiModel "+report["date"]).build(story)
    if out.stat().st_size < 1000 or out.read_bytes()[:5]!=b"%PDF-":
        raise RuntimeError("invalid_three_day_pdf")


def build(queue, selected, dest, *, now_utc=None):
    manifest=summarize(queue,selected,now_utc=now_utc)
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    for row in manifest["reports"]:
        render(row,dest/("MULTIMODEL_"+row["date"]+".pdf"))
    (dest/"manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue",required=True)
    parser.add_argument("--abc",required=True)
    parser.add_argument("--output-dir",required=True)
    args=parser.parse_args()
    q=json.loads(Path(args.queue).read_text(encoding="utf-8"))
    abc=json.loads(Path(args.abc).read_text(encoding="utf-8"))
    manifest=build(q,abc,args.output_dir)
    print(json.dumps({"base_day":manifest["base_day"],"pdf_count":len(manifest["reports"]),
                      "market_rows":{r["date"]:r["raw_eligible_candidates"] for r in manifest["reports"]}},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
