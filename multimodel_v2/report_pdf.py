"""Generate and validate exactly three isolated A5 reports, never source data."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta
from html import escape
import json
import os
from pathlib import Path
import tempfile

import pymupdf as fitz
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
)

from .audit import COHORTS, build_audits
from .fouls_under import fouls_under_watchlist
from .source_manifest import WARSAW, build_source_manifest, instant, local_day, number

LABELS = {"original_top": "Oryginalny TOP", "qualifying_api": "Wszystkie kwalifikujące się API",
          "fouls_under": "FAULE UNDER"}
MISSING = "BRAK ZWERYFIKOWANYCH KANDYDATUR"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
INK = colors.HexColor("#172D3A")
ACCENT = colors.HexColor("#17655D")
MUTED = colors.HexColor("#465A65")
REASONS = {
    "no_verified_snapshot_for_date": "brak zweryfikowanego snapshotu dla tej daty",
    "no_original_freeze_for_date": "brak oryginalnego przedmeczowego freeze",
    "missing_original_top": "brak oryginalnej listy TOP",
    "kickoff_date_mismatch": "data meczu w Warszawie nie odpowiada dacie raportu",
    "run_not_successful": "run nie został ukończony sukcesem",
    "date_not_covered": "run nie potwierdza pokrycia tej daty",
    "no_verified_run": "brak poprawnego ukończonego runu",
    "missing_odds": "brak oryginalnego notowania",
    "no_verified_quote": "brak zweryfikowanego kursu dla dokładnego rynku",
    "quote_market_mismatch": "tożsamość rynku notowania jest rozbieżna",
    "missing_or_invalid_api_assessment": "brak poprawnej oryginalnej oceny API",
    "snapshot_lookahead": "snapshot nie powstał przed kickoffem",
    "freeze_not_prematch": "freeze nie powstał przed kickoffem",
    "duplicate_fixture_market": "duplikat tej samej pozycji w snapshotcie",
    "conflicting_fixture": "sprzeczne dane meczu",
    "ambiguous_original_freeze": "sprzeczne kopie oryginalnego freeze",
    "missing_settlement": "brak wyniku",
    "duplicate_settlement": "niejednoznaczne powtórzone wyniki",
    "kickoff_reached": "mecz już się rozpoczął — brak nowej prognozy",
    "odds_outside_band": "brak kursu w przedziale 1.50–2.00",
    "not_90_minutes": "okres rynku nie obejmuje 90 minut",
}


def report_dates(start_date):
    start = local_day(start_date)
    return [(start + timedelta(days=i)).isoformat() for i in range(3)]


def build_daily_report(day, runs, snapshots, settlements, *, as_of):
    if not isinstance(snapshots, list):
        raise ValueError("source_lists_required")
    day_snapshots = [s for s in snapshots if not isinstance(s, dict) or s.get("date") == day]
    manifest = build_source_manifest(day, runs, day_snapshots, as_of=as_of)
    watchlist = fouls_under_watchlist(day, runs, day_snapshots, as_of=as_of)
    audits = build_audits(day, runs, snapshots, settlements, as_of=as_of)
    upcoming = []
    for record in manifest["records"]:
        try:
            if number(record["final_assessment_pct"]) < 67 or instant(record["kickoff"]) <= instant(as_of):
                continue
            quotes = [q for q in record["quotes"] if number(q["selected_odd"]) >= number("1.20")]
            if quotes:
                quote = sorted(quotes, key=lambda q: (-number(q["selected_odd"]), q["bookmaker"]))[0]
                upcoming.append(dict(record, quote=quote, status="OBSERWUJ / analiza pomocnicza (nie freeze)"))
        except ValueError:
            continue
    return {"date": day, "as_of": manifest["as_of"], "manifest": manifest,
            "watchlist": watchlist, "audits": audits, "upcoming_api": upcoming}


def _fonts(font_dir):
    for name, filename in (("DejaVuSans", "DejaVuSans.ttf"), ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf")):
        path = Path(font_dir) / filename
        if not path.is_file():
            raise ValueError(f"Missing DejaVu Sans font: {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))


class _PageNumbers(canvas.Canvas):
    """Two-pass footer, with a verifiable total on every page."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        count = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.setFillColor(MUTED)
            self.setFont("DejaVuSans", 7)
            self.drawString(11 * mm, 9 * mm, "MULTIMODEL v2 · obserwacje i audyt")
            self.drawRightString(A5[0] - 11 * mm, 9 * mm, f"Strona {self._pageNumber} / {count}")
            super().showPage()
        super().save()


def _styles():
    def style(name, size, leading, **extra):
        settings = dict(fontName="DejaVuSans", fontSize=size, leading=leading,
                        textColor=INK, spaceAfter=5, alignment=TA_LEFT, splitLongWords=True)
        settings.update(extra)
        return ParagraphStyle(name, **settings)
    return {
        "title": style("Title", 19, 23, fontName="DejaVuSans-Bold", spaceAfter=7),
        "section": style("Section", 11.5, 15, fontName="DejaVuSans-Bold", textColor=ACCENT,
                         spaceBefore=7, spaceAfter=7, keepWithNext=True),
        "body": style("Body", 8.5, 12),
        "small": style("Small", 7.2, 10),
        "card": style("Card", 8.3, 11.4, borderPadding=7, borderWidth=0.4,
                      borderColor=colors.HexColor("#CEDDD9"), backColor=colors.HexColor("#F2F7F5")),
    }


def _p(value, style):
    # Untrusted source strings are always text, never ReportLab markup/links.
    return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)


def _market_text(identity):
    scope = "cały mecz" if identity["market_scope"] == "match" else f"drużyna ID {identity['team_id']}"
    period = "90 min" if identity["settlement_period"] == "regulation_time" else identity["settlement_period"]
    market = {"fouls": "Faule", "corners": "Rożne", "team_goals": "Gole drużyny",
              "yellow_cards": "Żółte kartki"}.get(identity["market"], identity["market"])
    return f"{market} · {identity['direction'].upper()} {identity['line']} · {scope} · {period}"


def _card(item, styles, *, rank=None, compact=False):
    identity, quote = item["market_identity"], item.get("quote")
    time = instant(item["kickoff"]).astimezone(WARSAW).strftime("%H:%M")
    first = f"{rank}. " if rank is not None else ""
    text = [f"{first}{time} · {item['home']} — {item['away']}", _market_text(identity)]
    score = item.get("api_assessment", item.get("final_assessment_pct"))
    if quote:
        text.append(f"Kurs {quote['selected_odd']} · {quote['bookmaker']} · API {score}/100")
        text.append(f"Notowanie {quote['provider_updated_at']}")
    else:
        text.append(f"API {score if score is not None else 'brak oceny'}/100 · brak zamrożonego kursu")
    text.append(item.get("status", "OBSERWUJ"))
    source = item.get("source")
    if source and not compact:
        text.append(f"Fixture {identity['fixture_id']} · run {source['run_id']} · snapshot {source['snapshot_at']}")
    return _p("\n".join(text), styles["card"])


def _value(value, suffix=""):
    return "niedostępne" if value is None else f"{value}{suffix}"


def _render_pdf(report, path, *, font_dir=FONT_DIR):
    _fonts(font_dir)
    styles = _styles()
    story = []
    add = lambda text, style="body": story.append(_p(text, styles[style]))
    add("MULTIMODEL v2", "title")
    add(f"{report['date']} · Europe/Warsaw", "section")
    add(f"Stan źródeł na {report['as_of']}. Dokument obserwacyjny; bez zmian modeli i rejestrów.", "small")
    story.append(HRFlowable(width="100%", color=ACCENT, thickness=1))
    add("FAULE UNDER · kurs 1.50–2.00", "section")
    watch = report["watchlist"]["candidates"]
    if watch:
        add(f"Zweryfikowane kandydatury: {len(watch)}. Na tej stronie pierwsze {min(2, len(watch))}; pełna lista dalej.", "small")
        for item in watch[:2]:
            story.extend([_card(item, styles, compact=True), Spacer(1, 5)])
    else:
        add(MISSING, "card")
        add("Brak źródła lub kompletnej kandydatury. Ten komunikat nie oznacza braku spotkań w kalendarzu.", "small")
    add("Pokrycie źródeł", "section")
    api_status = ("zweryfikowany run i snapshot" if report["manifest"]["status"] == "covered"
                  else "BRAK zweryfikowanego runu / snapshotu dla tej daty")
    add(f"API Market: {api_status}.\nOryginalny TOP: " +
        ("potwierdzony freeze" if report["audits"]["cohorts"]["original_top"]["status"] == "complete"
         else "BRAK kompletnego oryginalnego freeze / TOP"), "small")
    add("KB Score: brak aktualnej prognozy (brak eksportu źródłowego).\n"
        "Konsensus: brak aktualnej prognozy (brak eksportu źródłowego).\n"
        "PitchAPI: brak zweryfikowanego kontekstu w wejściu tego raportu.", "small")
    add("Ocena API /100 nie jest P(HIT). Powiązane rynki jednego meczu są skorelowane. "
        "Status obserwacyjny nie jest KB PLAY ani potwierdzeniem dostępności STS/Superbet.", "small")

    story.append(PageBreak())
    add("Trzy niezależne audyty", "title")
    add("Wyłącznie oryginalne pozycje zamrożone przed kickoffem. Wyniki są dołączane osobno; "
        "brak statystyki pozostaje nierozliczony. Liczności poniżej są diagnostyką tego wejścia, nie zapisami N.", "small")
    for name in COHORTS:
        cohort = report["audits"]["cohorts"][name]
        metrics = cohort["metrics"]
        parts = [_p(LABELS[name], styles["section"])]
        status = {"source_missing": "BRAK ŹRÓDŁA — liczebność nieustalona",
                  "incomplete": "Dane niekompletne — bez pełnych miar", "complete": "Potwierdzone członkostwo grupy"}[cohort["status"]]
        parts.append(_p(status, styles["body"]))
        parts.append(_p(f"Pozycje: {_value(metrics['positions'])} · mecze: {_value(metrics['fixtures'])} · "
                        f"rozliczone: {_value(metrics['settled'])} · nierozliczone: {_value(metrics['unresolved'])}", styles["small"]))
        parts.append(_p(f"Hit-rate: {_value(metrics['hit_rate_pct'], '%')} · ROI: {_value(metrics['roi_pct'], '%')}\n"
                        f"ROI z równą wagą meczu: {_value(metrics['fixture_equal_roi_pct'], '%')}", styles["small"]))
        story.append(KeepTogether(parts))
    add("ROI wymaga kompletu wyników i oryginalnych zamrożonych kursów dla całej grupy. "
        "Stawka diagnostyczna: 1 jednostka na pozycję; void/push zwraca stawkę (zysk 0). "
        "Nie jest to potwierdzenie faktycznie zawartych zakładów.", "small")
    add("Źródła i ograniczenia", "section")
    if not report["manifest"]["sources"]:
        add("BRAK ŹRÓDEŁ API dla tej daty. Nie wykorzystano dawnych rejestrów jako świeżej prognozy.", "small")
    for source in report["manifest"]["sources"]:
        add(f"Run {source['run_id']} · {source['conclusion']} · snapshot {source['snapshot_at']}\n"
            f"SHA runu: {source['head_sha']}\nArtefakt: {source['snapshot_artifact']}", "small")
    reasons = {r["reason"] for r in report["manifest"]["rejections"] +
               report["audits"]["rejections"] + report["watchlist"]["rejections"]}
    for reason in sorted(reasons):
        description = REASONS.get(reason, "niespójne lub niepełne dowody źródłowe — szczegóły w audycie")
        add(f"Brak / odrzucenie: {description}", "small")

    top = report["audits"]["cohorts"]["original_top"]
    active_top = [(rank, row) for rank, row in enumerate(top["rows"], 1)
                  if row["validation"] == "verified" and instant(row["record"]["kickoff"]) > instant(report["as_of"])]
    if active_top:
        story.append(PageBreak())
        add("Oryginalny TOP · przed meczem", "title")
        add("Oryginalna kolejność i numer pozycji. Pierwsze trzy pozycje na mecz tutaj; reszta w aneksie.", "small")
        counts, appendix = defaultdict(int), []
        for rank, row in active_top:
            fid = row["market_identity"]["fixture_id"]
            counts[fid] += 1
            if counts[fid] > 3:
                appendix.append((rank, row))
            else:
                item = dict(row["record"], quote=row["frozen_quote"], status="ORYGINALNY FREEZE · obserwacja")
                story.extend([_card(item, styles, rank=rank), Spacer(1, 6)])
        if appendix:
            add("Aneks · pozostałe pozycje oryginalnego TOP", "section")
            for rank, row in appendix:
                story.extend([_card(dict(row["record"], quote=row["frozen_quote"], status="ORYGINALNY FREEZE"), styles, rank=rank), Spacer(1, 6)])
    for heading, rows in (("Wszystkie kwalifikujące się API", report["upcoming_api"]),
                          ("FAULE UNDER · pełna lista", watch)):
        if rows:
            story.append(PageBreak())
            add(heading, "title")
            add("Wyłącznie pozycje tego dnia przed kickoffem. To obserwacje z istniejących ocen i kursów.", "small")
            for row in rows:
                story.extend([_card(row, styles), Spacer(1, 7)])

    historical = any(row["record"] and instant(row["record"]["kickoff"]) <= instant(report["as_of"])
                     for cohort in report["audits"]["cohorts"].values() for row in cohort["rows"])
    if historical:
        story.append(PageBreak())
        add("Aneks audytu historycznego", "title")
        add("Oryginalne freeze, bez nowych prognoz po kickoffie. Brak wyniku nie oznacza przegranej.", "small")
        for name in COHORTS:
            add(LABELS[name], "section")
            for i, row in enumerate(report["audits"]["cohorts"][name]["rows"], 1):
                identity = row["market_identity"]
                if identity is None:
                    add(f"{i}. Niezweryfikowana oryginalna pozycja: {row['reason']}", "small")
                    continue
                outcome = row["settlement"]["outcome"] if row["settlement"] else "nierozliczone"
                add(f"{i}. Fixture {identity['fixture_id']} · {_market_text(identity)}\n"
                    f"Wynik: {outcome}; powód braku: "
                    f"{REASONS.get(row['settlement_reason'], 'niepełne dowody wyniku') if row['settlement_reason'] else 'brak'}.\n"
                    f"Freeze {row['freeze']['id']} · run {row['freeze']['run_id']}", "small")
                if row["settlement"]:
                    add(f"Źródło wyniku: {row['settlement']['result_source']}", "small")

    doc = SimpleDocTemplate(str(path), pagesize=A5, rightMargin=11 * mm, leftMargin=11 * mm,
                            topMargin=16 * mm, bottomMargin=17 * mm,
                            title=f"MULTIMODEL {report['date']}", author="MULTIMODEL v2")

    def header(page_canvas, document):
        page_canvas.saveState()
        page_canvas.setFont("DejaVuSans", 7)
        page_canvas.setFillColor(MUTED)
        page_canvas.drawString(11 * mm, A5[1] - 9 * mm, f"MULTIMODEL · {report['date']} · Europe/Warsaw")
        page_canvas.restoreState()

    doc.build(story, onFirstPage=header, onLaterPages=header, canvasmaker=_PageNumbers)


def validate_pdf(path, expected_date):
    """Parse pages, text, geometry, embedded fonts, minimum size and links."""
    local_day(expected_date)
    path = Path(path)
    if not path.is_file() or not path.read_bytes().startswith(b"%PDF-"):
        raise ValueError("missing_or_invalid_pdf")
    try:
        with fitz.open(path) as document:
            total = len(document)
            if total < 2 or document.needs_pass:
                raise ValueError("missing_pdf_sections")
            for index, page in enumerate(document):
                if abs(page.rect.width - A5[0]) > 0.5 or abs(page.rect.height - A5[1]) > 0.5:
                    raise ValueError("pdf_not_a5")
                text = page.get_text()
                if f"MULTIMODEL · {expected_date}" not in text or f"Strona {index + 1} / {total}" not in text:
                    raise ValueError("pdf_date_or_pagination_invalid")
                if index == 0 and "FAULE UNDER" not in text:
                    raise ValueError("fouls_under_missing_from_first_page")
                if "\ufffd" in text or page.get_links():
                    raise ValueError("pdf_invalid_text_or_links")
                spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                         for line in block["lines"] for span in line["spans"] if span["text"].strip()]
                if not spans:
                    raise ValueError("pdf_empty_page")
                for span in spans:
                    if span["size"] < 6 or not span["font"].startswith("DejaVuSans"):
                        raise ValueError("pdf_font_invalid")
                    x0, y0, x1, y1 = span["bbox"]
                    if x0 < 8 or y0 < 4 or x1 > page.rect.width - 8 or y1 > page.rect.height - 4:
                        raise ValueError("pdf_text_outside_page")
                embedded = [font for font in page.get_fonts() if "DejaVuSans" in font[3]]
                if not embedded or any(not document.extract_font(font[0])[3] for font in embedded):
                    raise ValueError("pdf_font_not_embedded")
            return {"path": str(path), "date": expected_date, "pages": total, "validated": True}
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError("pdf_parser_error") from exc


def validate_pdf_bundle(directory, start_date):
    directory = Path(directory)
    days = report_dates(start_date)
    expected = {f"MULTIMODEL_{day}.pdf" for day in days}
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != expected:
        raise ValueError("expected_exactly_three_dated_pdfs")
    return [validate_pdf(directory / f"MULTIMODEL_{day}.pdf", day) for day in days]


def generate_three_pdfs(start_date, runs, snapshots, settlements, *, as_of, output_dir, font_dir=FONT_DIR):
    """Stage/validate all PDFs before publishing paths; never overwrite files."""
    days = report_dates(start_date)
    instant(as_of)
    output = Path(output_dir).resolve()
    root = Path(__file__).resolve().parents[1]
    protected = [(root / name).resolve() for name in
                 (".git", "archive", "data", "reports", "model", "config", "tools", ".github")]
    if any(output == path or path in output.parents for path in protected):
        raise ValueError("protected_production_output_path")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output_directory_must_be_empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".multimodel-v2-", dir=output.parent) as temporary:
        staging = Path(temporary) / "pdfs"
        staging.mkdir()
        for day in days:
            report = build_daily_report(day, runs, snapshots, settlements, as_of=as_of)
            _render_pdf(report, staging / f"MULTIMODEL_{day}.pdf", font_dir=font_dir)
        validate_pdf_bundle(staging, start_date)
        os.rename(staging, output)
    return [output / f"MULTIMODEL_{day}.pdf" for day in days]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="D, local date YYYY-MM-DD in Europe/Warsaw")
    parser.add_argument("--as-of", required=True, help="Actual observation cutoff with UTC offset")
    parser.add_argument("--evidence", type=Path, help="JSON with runs, snapshots and settlements; omission means missing sources")
    parser.add_argument("--output", required=True, type=Path, help="New or empty isolated output directory")
    args = parser.parse_args(argv)
    evidence = {"runs": [], "snapshots": [], "settlements": []}
    if args.evidence:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    paths = generate_three_pdfs(args.start, evidence["runs"], evidence["snapshots"], evidence["settlements"],
                                as_of=args.as_of, output_dir=args.output)
    print(json.dumps(validate_pdf_bundle(paths[0].parent, args.start), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
