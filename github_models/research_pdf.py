"""Daily A5 PDF for independent, uncalibrated research forecasts."""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

def build(predictions, queue, settlement, output):
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.exists():
        raise RuntimeError("DejaVuSans font required for Polish text")
    pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontName="DejaVu", fontSize=13, leading=18, spaceAfter=10))
    styles.add(ParagraphStyle(name="ReportText", fontName="DejaVu", fontSize=8, leading=12, spaceAfter=5))
    styles.add(ParagraphStyle(name="ReportSmall", fontName="DejaVu", fontSize=7, leading=10))
    styles.add(ParagraphStyle(name="ReportHead", fontName="DejaVu", fontSize=9, leading=13, spaceBefore=10, spaceAfter=6))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out), pagesize=A5, leftMargin=27, rightMargin=27, topMargin=27, bottomMargin=27)
    fixtures = {str(f["fixture_id"]): f for f in queue["fixtures"]}
    items = [Paragraph("KB SCORE | MODELE BADAWCZE", styles["ReportTitle"]),
             Paragraph("Elo i Dixon-Coles — prognozy niekalibrowane, NIE są rekomendacjami do obstawiania.", styles["ReportText"]),
             Paragraph("Zamrożenie: " + escape(str(predictions.get("generated_at_utc", "brak"))), styles["ReportText"]),
             Paragraph("Mecze w kolejce: " + str(len(fixtures)) + " | prognozy: " + str(len(predictions["predictions"])) +
                       " | blokady modeli: " + str(len(predictions.get("blockers", []))), styles["ReportText"])]
    by_fixture = {}
    for p in predictions["predictions"]:
        by_fixture.setdefault(str(p["fixture_id"]), []).append(p)
    items.append(Paragraph("Prognozy 1 / X / 2", styles["ReportHead"]))
    for fid, forecasts in sorted(by_fixture.items(), key=lambda v: fixtures.get(v[0], {}).get("kickoff_utc", "")):
        f = fixtures.get(fid, {})
        header = escape(str(f.get("home", "?"))) + " - " + escape(str(f.get("away", "?")))
        league = escape(str(f.get("league", "")))
        kick = escape(str(f.get("kickoff_utc", "")))
        chunk = [Paragraph(header + " | " + league, styles["ReportText"]),
                 Paragraph("Start UTC: " + kick, styles["ReportSmall"])]
        for p in forecasts:
            vals = [float(p[k]) for k in ("p_home", "p_draw", "p_away")]
            chunk.append(Paragraph(escape(str(p["model_id"])) + ": " +
                " / ".join(f"{v*100:.1f}%" for v in vals), styles["ReportSmall"]))
        chunk.append(Spacer(1, 7))
        items.append(KeepTogether(chunk))
    if not by_fixture:
        items.append(Paragraph("Brak dopuszczonych prognoz. Nie uzupełniono ich szacunkami.", styles["ReportText"]))
    items.append(Paragraph("Rozliczenia wcześniejszych prognoz", styles["ReportHead"]))
    reports = settlement.get("reports", [])
    statuses = Counter(x.get("status") for r in reports for x in r.get("result", {}).get("settlements", []))
    items.append(Paragraph("Przetworzone archiwa: " + str(len(reports)) + " | rozliczone: " +
        str(statuses.get("settled", 0)) + " | oczekujące: " + str(statuses.get("pending", 0)) +
        " | niejednoznaczne: " + str(statuses.get("ambiguous", 0)), styles["ReportText"]))
    settled = [x for r in reports for x in r.get("result", {}).get("settlements", []) if x.get("status") == "settled"]
    if settled:
        items.append(Paragraph("Brier (średnia): " + f"{sum(x['brier'] for x in settled)/len(settled):.4f}" +
            " | log loss (średnia): " + f"{sum(x['log_loss'] for x in settled)/len(settled):.4f}", styles["ReportText"]))
        items.append(Paragraph("Uwaga: rozliczenia mogą zawierać powtórzone mecze z różnych archiwów; metryki dotyczą prognoz, nie unikalnych meczów.", styles["ReportSmall"]))
    else:
        items.append(Paragraph("Brak zweryfikowanych wyników do obliczenia Brier i log loss.", styles["ReportText"]))
    reasons = Counter()
    for k, n in predictions.get("blocker_summary", {}).items():
        reasons[k.split(": ", 1)[-1].split(":", 1)[0]] += n
    items.append(Paragraph("Najczęstsze blokady", styles["ReportHead"]))
    for reason, n in reasons.most_common(6):
        items.append(Paragraph(escape(reason) + ": " + str(n), styles["ReportSmall"]))
    doc.build(items)
    if not out.is_file() or out.stat().st_size < 1000:
        raise RuntimeError("pdf_not_generated")
    print("Generated research PDF:", out, out.stat().st_size, "bytes")

def main():
    p = argparse.ArgumentParser()
    for name in ("predictions", "queue", "settlement", "output"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    build(read(a.predictions), read(a.queue), read(a.settlement), a.output)

if __name__ == "__main__":
    main()
