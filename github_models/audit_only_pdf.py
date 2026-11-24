"""Read-only MultiModel settlement audit PDF independent of today's fixture/odds queue.

Only consumes independently published archived JSON. Never calls providers,
rewrites historical predictions, or confuses repeated selections with matches.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from github_models.report_freshness import WARSAW, aware

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate(replay, shadow, readiness, *, now):
    if replay.get("schema") != "github-models-oddspapi-frozen-audit-v1":
        raise ValueError("unexpected_replay_audit_schema")
    if shadow.get("schema") != "multimodel-priced-shadow-outcomes-v1":
        raise ValueError("unexpected_shadow_settlement_schema")
    if readiness.get("schema") != "multimodel-calibration-readiness-v1":
        raise ValueError("unexpected_calibration_readiness_schema")
    cutoff = aware(replay.get("as_of_utc"), "replay_as_of_utc")
    if cutoff > now:
        raise ValueError("future_audit_not_allowed")
    if readiness.get("abc_settled_quotes") != replay.get("settled_selection_quotes"):
        raise ValueError("replay_calibration_quote_count_mismatch")
    if readiness.get("abc_distinct_settled_fixtures") != replay.get("unique_settled_fixtures"):
        raise ValueError("replay_calibration_fixture_count_mismatch")
    if readiness.get("shadow_settled_quotes") != shadow.get("status", {}).get("settled"):
        raise ValueError("shadow_calibration_quote_count_mismatch")
    if readiness.get("calibration_authorized") is True or readiness.get("model_weights_changed") is True:
        raise ValueError("unexpected_automated_calibration_or_weights")
    ids = replay.get("settled_fixture_ids", [])
    if len(set(ids)) != replay.get("unique_settled_fixtures"):
        raise ValueError("inconsistent_unique_abc_fixtures")
    return cutoff


def build(replay, shadow, readiness, dest, *, now_utc=None, source_run=None):
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = _validate(replay, shadow, readiness, now=now)
    fonts = (( "Audit", "DejaVuSans.ttf"), ("AuditBold", "DejaVuSans-Bold.ttf"))
    for name, filename in fonts:
        if not (FONT_DIR / filename).is_file():
            raise RuntimeError("missing_dejavu_font")
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
    black, teal = colors.HexColor("#263645"), colors.HexColor("#165D58")
    small = ParagraphStyle("aSmall", fontName="Audit", fontSize=8.4, leading=12, textColor=black, spaceAfter=8)
    heading = ParagraphStyle("aHead", parent=small, fontName="AuditBold", fontSize=12, leading=16,
                             spaceBefore=15, spaceAfter=8, textColor=teal)
    title = ParagraphStyle("aTitle", parent=small, fontName="AuditBold", fontSize=18, leading=23,
                           spaceAfter=12, textColor=black)
    cell = ParagraphStyle("aCell", parent=small, fontSize=7.6, leading=11, spaceAfter=0)
    def paragraph(s, sty=small):
        return Paragraph(escape(str(s)), sty)
    def table(rows, widths):
        t = Table([[paragraph(v, cell) for v in row] for row in rows], colWidths=widths, repeatRows=1,
                  hAlign="LEFT")
        t.setStyle(TableStyle([
            ("VALIGN", (0,0),(-1,-1),"TOP"),
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E4F2F0")),
            ("LINEBELOW",(0,0),(-1,0),0.6,teal),
            ("LINEBELOW",(0,1),(-1,-1),0.25,colors.HexColor("#CBD6D5")),
            ("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        return t
    counts = replay["status_counts"]
    scounts = shadow["status"]
    union = readiness.get("combined_distinct_fixtures_exact")
    wanted = readiness.get("fixtures_remaining_to_100_review")
    report_day = now.astimezone(WARSAW).date().isoformat()
    story = [
        paragraph("MULTIMODEL — NIEZALEŻNY AUDYT", title),
        paragraph(f"Data opracowania: {report_day} (Europe/Warsaw). "
                  f"Źródło rozliczeń: stan archiwum {cutoff.astimezone(WARSAW):%d.%m.%Y %H:%M}."),
        paragraph("To raport historyczny, NIE bieżący kupon. Nie wymaga dostępnych dziś typów ani "
                  "świeżych notowań i nie potwierdza oficjalnej wypłaty Superbet."),
        paragraph("1. Rozliczenia wycen A/B/C", heading),
        table([["Wskaźnik", "Wynik"],
               ["Pozycje rozliczone", counts.get("settled", "n/d")],
               ["Różne mecze rozliczone", replay.get("unique_settled_fixtures", "n/d")],
               ["Nierozstrzygnięte selekcje", counts.get("unresolved", "n/d")],
               ["Oczekujące na wyniki", counts.get("pending_future", "n/d")],
               ["Główne powody braków", json.dumps(replay.get("unresolved_by_market", {}), ensure_ascii=False)]],
              [240, 290]),
        paragraph("Powyższe selekcje są skorelowane: wiele typów może pochodzić z tego samego meczu. "
                  "Nie liczymy liczby typów jako liczby niezależnych obserwacji."),
        paragraph("2. Rozliczenia SHADOW BTTS i handicapów", heading),
        table([["Wskaźnik", "Wynik"],
               ["Pozycje rozliczone", scounts.get("settled", "n/d")],
               ["Różne mecze z wynikiem", readiness.get("shadow_distinct_settled_fixtures", "n/d")],
               ["Oczekujące", scounts.get("pending", "n/d")]], [240, 290]),
    ]
    rows = [["Rynek SHADOW", "Rozliczone", "Trafność", "Brier"]]
    for m, label in (("btts","BTTS"),("handicap","Handicap ±1,5")):
        x = shadow.get("market_summary",{}).get(m,{})
        rate = x.get("hit_rate")
        brier = x.get("brier")
        rows.append([label, x.get("settled",0), ("%.1f%%" %(rate*100) if rate is not None else "n/d"),
                     ("%.3f" % brier if brier is not None else "n/d")])
    story.append(table(rows,[180,105,105,140]))
    story.extend([
        paragraph("3. Gotowość do kalibracji", heading),
        table([["Kryterium", "Wynik"],
               ["Dokładna unia niezależnych meczów A/B/C + SHADOW", union if union is not None else "n/d"],
               ["Brakuje do przeglądu 100 różnych meczów", wanted if wanted is not None else "n/d"],
               ["Niezależny chronologiczny holdout", "NIE" if not readiness.get("holdout_evidence_available") else "TAK"],
               ["Kalibracja uprawniona", "NIE" if not readiness.get("calibration_authorized") else "TAK"],
               ["Zmiana wag modeli", "NIE" if not readiness.get("model_weights_changed") else "TAK"]],
              [370, 160]),
        paragraph("Brak holdoutu i 100 niezależnych spotkań blokuje formalną kalibrację. "
                  "Wskaźniki skuteczności są badawcze i nie stanowią dowodu przewagi nad kursem bukmachera."),
        paragraph("4. Pochodzenie i ograniczenia", heading),
        paragraph(f"Archiwa A/B/C: {replay.get('archives_processed', 'n/d')}; "
                  f"Archiwa SHADOW z kursami: {shadow.get('archived_oddspapi_collections', 'n/d')}; "
                  f"Run audytu: {source_run or 'brak ID w metadanych'}."),
        paragraph("Wyniki sprawdzane niezależnie od prognoz; brak oficjalnego potwierdzenia wypłaty "
                  "Superbet i braki zgodności semantycznej fauli/kartek. "
                  "Nie dopisujemy fikcyjnych kursów ani nie rozliczamy braku danych jako przegranej."),
    ])
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(dest), pagesize=A4, leftMargin=31, rightMargin=31,
                            topMargin=35, bottomMargin=35,
                            title=f"MultiModel niezależny audyt {report_day}")
    doc.build(story)
    if dest.stat().st_size < 1000 or dest.read_bytes()[:5] != b"%PDF-":
        raise RuntimeError("invalid_pdf_output")
    return {"schema": "multimodel-independent-audit-pdf-v1", "report_day": report_day,
            "source_replay_as_of_utc": cutoff.isoformat(),
            "source_run_id": source_run, "abc_settled": counts.get("settled"),
            "abc_fixtures": replay.get("unique_settled_fixtures"),
            "shadow_settled": scounts.get("settled"),
            "exact_union": union, "auto_calibration_allowed": False,
            "paid_api_calls": 0, "current_betting_recommendations": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-run-id")
    args = parser.parse_args()
    root = Path(args.input_dir)
    out = Path(args.output_dir)
    day = datetime.now(timezone.utc).astimezone(WARSAW).date().isoformat()
    audit_pdf = out / ("MULTIMODEL_AUDYT_" + day + ".pdf")
    manifest = build(read(root/"REPLAY_AUDIT.json"),
                     read(root/"PRICED_SHADOW_SETTLEMENT.json"),
                     read(root/"MULTIMODEL_CALIBRATION_READINESS.json"),
                     audit_pdf, source_run=args.source_run_id)
    (out/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n",
                                    encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
