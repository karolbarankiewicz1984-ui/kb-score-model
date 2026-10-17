"""Produce three useful KB21 RESEARCH PDFs without blocking on 42 signoffs.

This is an ALTERNATIVE daily research track, NOT the original LIVE KB21
model and NOT a shortcut around Calendar Gate for publishing selections.
Select upcoming matches by SOURCE EVIDENCE (not expected win probability),
surface real goal HISTORY where independently available, explain unresolved
fixture issues, and leave pre-odds analyst STR/QUAL/MATCH/P(model) empty.

The actual signed 14-league Calendar Gate, historical N, and separate API
Market/PitchAPI engines remain untouched. Never manufacture odds or ratings.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from tools.kb21_calendar_coverage import SCOPE
from tools.kb21_fixture_crosscheck import _instant

SCHEMA = "kb21-research-first-3day-v1"
WARSAW = ZoneInfo("Europe/Warsaw")
MARKED = "DIAGNOSTIC / NO PLAY"
MATCH = "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
ORG_MATCH = "MATCHED_FOR_REVIEW"
BLOCKERS = ("KICKOFF_CONFLICT", "AMBIGUOUS", "NOT_IN_EARLY_OFFICIAL",
            "DUPLICATE", "INVALID")


def _history(context):
    if not isinstance(context, dict):
        return None
    found = {}
    for side in ("home", "away"):
        value = context.get(side)
        if not isinstance(value, dict):
            continue
        n = value.get("previous_completed_matches")
        gf, ga = value.get("goals_for_per_match"), value.get("goals_against_per_match")
        if (isinstance(n, int) and not isinstance(n, bool) and 5 <= n <= 10
                and all(isinstance(x, (float, int)) and not isinstance(x, bool)
                        and 0 <= x <= 15 for x in (gf, ga))):
            found[side] = {"sample_size": n, "goals_for": round(gf, 2),
                           "goals_against": round(ga, 2),
                           "metric": "ACTUAL GOALS, NOT xG"}
    return found or None


def build(queue, packet, now=None, limit_per_day=6):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)
            or not isinstance(packet, dict) or not isinstance(packet.get("rows"), list)
            or packet.get("schema") != "kb21-calendar-review-packet-v1"
            or packet.get("safe_to_publish_play") is not False
            or packet.get("calendar_gate") != "BLOCKED"):
        raise ValueError("Requires unsigned 3-day KB21 queue and review packet")
    days = queue["days"]
    if (len(days) != 3 or len(set(days)) != 3 or sorted(days) != days
            or set(packet.get("days", [])) != set(days)
            or not isinstance(limit_per_day, int) or isinstance(limit_per_day, bool)
            or not 1 <= limit_per_day <= 20):
        raise ValueError("Need exact ordered 3 Warsaw days and reasonable research cap")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Need timezone-aware generation time")
    now = now.astimezone(timezone.utc)
    official = {}
    for row in packet["rows"]:
        if not isinstance(row, dict) or not isinstance(row.get("fixtures"), list):
            raise ValueError("Malformed calendar review row")
        key = row.get("day"), row.get("league_id")
        if key in official or key[0] not in days or key[1] not in SCOPE:
            raise ValueError("Duplicate/foreign league or day in packet")
        official[key] = row
    if set(official) != {(day, league) for day in days for league in SCOPE}:
        raise ValueError("Missing 14-league review scope in diagnostic packet")

    research = {}
    for item in queue["fixtures"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid candidate fixture")
        fid = item.get("fixture_id")
        if not isinstance(fid, str) or ":" not in fid:
            raise ValueError("Candidate has no ID")
        key = (item.get("date_warsaw"), fid)
        if key in research or key[0] not in days or fid.rsplit(":", 1)[0] not in SCOPE:
            raise ValueError("Duplicate/foreign candidate fixture")
        research[key] = item

    packet_seen = set()
    output_days = []
    for day in days:
        candidates = []
        rejected = {"already_started": 0, "unknown_kickoff": 0,
                    "unresolved_source": 0}
        for (card_day, league), card in official.items():
            if card_day != day:
                continue
            for row in card["fixtures"]:
                if not isinstance(row, dict):
                    raise ValueError("Invalid per-fixture official comparison")
                fid = row.get("fixture_id")
                key = day, fid
                if (not isinstance(fid, str) or key not in research
                        or fid.rsplit(":", 1)[0] != league or key in packet_seen):
                    raise ValueError("Calendar packet contains missing/duplicate event")
                packet_seen.add(key)
                current = research[key]
                when = _instant(current.get("kickoff"))
                packet_when = _instant(row.get("kickoff_utc"))
                if when is None or packet_when is None:
                    rejected["unknown_kickoff"] += 1
                    continue
                if when != packet_when:
                    raise ValueError("Packet and research queue kickoff mismatch")
                if when <= now:
                    rejected["already_started"] += 1
                    continue
                early = row.get("early_official_archive") or {}
                comparator = row.get("organizer_crosscheck") or {}
                early_state = early.get("status", "NOT_ARCHIVED")
                source_state = comparator.get("organizer_comparator_status",
                                               "NO_COMPARATOR_RECORD")
                independent = current.get("independent_crosscheck") or {}
                independent_state = independent.get("status") or "NO_INDEPENDENT_MATCH"
                conflict = (any(token in str(x) for x in (early_state, source_state)
                                for token in BLOCKERS)
                            or early_state == "EARLY_ORGANIZER_KICKOFF_PROVISIONAL"
                            or source_state == "KNVB_RESULTS_DATE_PAIR_POST_START_NO_KICKOFF")
                if conflict:
                    tier = "KONFLIKT / WYMAGA SPRAWDZENIA"
                    priority = 0
                    rejected["unresolved_source"] += 1
                elif early_state == MATCH:
                    tier = "WCZESNA ZGODNOSC OFICJALNA (BEZ PODPISU)"
                    priority = 3
                elif source_state == ORG_MATCH:
                    tier = "ZGODNOSC TERMINARZA DO PRZEGLADU"
                    priority = 2
                else:
                    tier = "NIEPELNE DOWODY TERMINARZA"
                    priority = 1
                his = _history((current.get("pre_match_research") or {})
                               .get("context"))
                candidates.append({
                    "fixture_id": fid, "fixture": current.get("fixture"),
                    "league_id": league, "competition": SCOPE[league],
                    "kickoff_warsaw": when.astimezone(WARSAW).isoformat(),
                    "source_evidence_level": tier,
                    "source_evidence_priority_only": priority,
                    "early_official_status": early_state,
                    "organizer_comparison_status": source_state,
                    "independent_calendar_status": independent_state,
                    "organizer_url": card.get("organizer_url"),
                    "previous_completed_match_goals": his,
                    "sport_score": None, "str_35": None, "qual_35": None,
                    "match_30": None, "pre_price_p_model": None,
                    "bookmaker": None, "odds": None, "ev": None,
                    "requires_independent_human_analysis": True,
                    "original_calendar_gate": "BLOCKED",
                    "publication": MARKED,
                })
        candidates.sort(key=lambda r: (-r["source_evidence_priority_only"],
                                        -int(bool(r["previous_completed_match_goals"])),
                                        r["kickoff_warsaw"], r["fixture_id"]))
        output_days.append({
            "day": day,
            "future_fixture_candidates": len(candidates),
            "selected_for_source_review": len(candidates[:limit_per_day]),
            "evidence_tiers": {
                status: sum(row["source_evidence_level"] == status for row in candidates)
                for status in sorted({r["source_evidence_level"] for r in candidates})},
            "excluded": rejected,
            "fixtures": candidates[:limit_per_day],
            "calendar_gate": "BLOCKED", "publication": MARKED,
        })
    if packet_seen != set(research):
        raise ValueError("All queue candidates must be present in calendar packet")
    return {
        "schema": SCHEMA, "days": days, "generated_at_utc": now.isoformat(),
        "reports": output_days, "publication": MARKED,
        "calendar_gate": "BLOCKED", "safe_to_publish_play": False,
        "actual_betting_recommendations": 0, "analyst_scores_generated": 0,
        "old_historical_n_written": False,
        "methodology": "ORIGINAL STR/35 + QUAL/35 + MATCH/30; separate human P(model) before odds",
        "api_market_remains_separate": True,
        "note": ("Practical event-first research independent of the 42 global "
                 "manual signoffs. It NEVER grants permission to PLAY. Source "
                 "priority is NOT betting confidence. Goal history is not xG; "
                 "P(model) and bookmaker odds are deliberately unavailable."),
    }


def render_md(day):
    lines = [
        "# KB Score 2.1 — codzienny raport badawczy — " + day["day"],
        "", "**DIAGNOSTYKA / NO PLAY — NIE SĄ TO TYPY.**",
        "Badanie przyszłych spotkań może być prowadzone mimo 42 "
        "nierozstrzygniętych kontroli całego kalendarza, ale publikacja "
        "oryginalnego KB Score jako PLAY nadal nie jest dozwolona.",
        "", "Przyszłe mecze do oceny: " + str(day["future_fixture_candidates"]) +
        "; pokazane: " + str(day["selected_for_source_review"]) + ".",
        "Kolejność = udokumentowanie TERMINARZA, NIE przewidywana trafność.",
        "", "## Spotkania do dalszej oceny", "",
    ]
    if not day["fixtures"]:
        lines += ["Brak nierozpoczętych kandydatów w tej dacie. "
                  "Nie oznacza to braku meczów ani zatwierdzenia terminarza.", ""]
    for index, game in enumerate(day["fixtures"], 1):
        lines += [f"### {index}. {game['fixture']} — {game['kickoff_warsaw']}",
                  "- Rozgrywki: " + game["competition"] + " | " + game["fixture_id"],
                  "- Materiał: " + game["source_evidence_level"],
                  "- Porównanie organizatora: " + game["organizer_comparison_status"],
                  "- Archiwum przed pierwszym meczem: " + game["early_official_status"],
                  "- Dostawca niezależny: " + game["independent_calendar_status"],
                  "- Oficjalny URL do ręcznej kontroli: " +
                  str(game["organizer_url"] or "BRAK"), ]
        hist = game["previous_completed_match_goals"]
        for side, label in (("home", "Gospodarze"), ("away", "Goście")):
            if hist and side in hist:
                h = hist[side]
                lines.append(f"- {label}: {h['sample_size']} wcześniejszych gier; "
                             f"gole {h['goals_for']:.2f}, stracone {h['goals_against']:.2f} "
                             "na mecz (GOLE, NIE xG)")
        lines += ["- Analityk: STR — /35; QUAL — /35; MATCH — /30; "
                  "P(model) przed kursem: NIE WYZNACZONO.",
                  "- Decyzja: NO PLAY — analiza sportowa i kontrola rynku nadal wymagane.", ""]
    lines += ["---", "API Market i PitchAPI działają niezależnie. "
              "Nie kopiujemy ich wyników do P(model) ani historycznego N.", ""]
    return "\n".join(lines)


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, path in (("KB21", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                       ("KB21", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")):
        if Path(path).is_file():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
            return name
    return "Helvetica"


def render_pdf(day, path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer,
    )
    font = _font()
    # Narrow compact typography to avoid past excessive page counts.
    title = ParagraphStyle("KB21Title", fontName=font, fontSize=14,
                           leading=18, textColor=colors.HexColor("#1E3348"),
                           spaceAfter=9)
    body = ParagraphStyle("KB21Body", fontName=font, fontSize=8.1,
                          leading=11.6, alignment=TA_LEFT, spaceAfter=4)
    sub = ParagraphStyle("KB21Sub", parent=body, fontSize=9.4, leading=13,
                         spaceBefore=9, spaceAfter=5,
                         textColor=colors.HexColor("#1E3348"))
    warning = ParagraphStyle("KB21Warning", parent=body, fontSize=8,
                             textColor=colors.HexColor("#A24221"))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(str(path), pagesize=A4, leftMargin=35,
                               rightMargin=35, topMargin=32, bottomMargin=32)
    frame = Frame(document.leftMargin, document.bottomMargin,
                  document.width, document.height, leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates(PageTemplate(id="body", frames=[frame]))
    items = [Paragraph("KB Score 2.1 / Raport badawczy / " + day["day"], title),
             Paragraph("DIAGNOSTYKA / NO PLAY. Brak automatycznych typów, "
                       "Sport Score lub P(model).", warning),
             Paragraph("Nierozpoczęte mecze: " + str(day["future_fixture_candidates"]) +
                       "; wyświetlone: " +
                       str(day["selected_for_source_review"]) +
                       ". Kolejność dotyczy WYŁĄCZNIE jakości danych.",
                       body), Spacer(1, 5)]
    if not day["fixtures"]:
        items.append(Paragraph(
            "Brak przyszłych kandydatów. Nie dowodzi to pustego kalendarza.", body))
    for index, game in enumerate(day["fixtures"], 1):
        item = [
            Paragraph(escape(f"{index}. {game['fixture']} — {game['kickoff_warsaw']}"),
                      sub),
            Paragraph("Liga: " + escape(game["competition"]) +
                      " / " + escape(game["fixture_id"]), body),
            Paragraph("Źródło: " + escape(game["source_evidence_level"]) +
                      "; archiwum: " + escape(game["early_official_status"]), body),
            Paragraph("Organizator: " +
                      escape(game["organizer_comparison_status"]) +
                      "; niezależne: " +
                      escape(game["independent_calendar_status"]), body),
        ]
        hist = game["previous_completed_match_goals"]
        if hist:
            for side, label in (("home", "Gospodarze"),
                                ("away", "Goście")):
                if side in hist:
                    h = hist[side]
                    item.append(Paragraph(
                        f"{label}: {h['sample_size']} wcześniejszych spotkań; "
                        f"gole {h['goals_for']:.2f}/mecz, "
                        f"stracone {h['goals_against']:.2f}/mecz "
                        "(to NIE xG)", body))
        item.append(Paragraph("STR —/35 | QUAL —/35 | MATCH —/30 | "
                              "P(model) przed kursem: brak | "
                              "Decyzja: NO PLAY", warning))
        items.append(KeepTogether(item))
    items.extend([Spacer(1, 10),
                  Paragraph("To nie jest przywrócony automat oryginalnego "
                            "KB Score 2.1. Calendar Gate pozostaje BLOCKED. "
                            "Pełna weryfikacja terminarzy i niezależna "
                            "ocena analityka nadal obowiązują. "
                            "API Market działa odrębnie.", body)])
    document.build(items)


def write_reports(report, output):
    if (not isinstance(report, dict) or report.get("schema") != SCHEMA
            or report.get("safe_to_publish_play") is not False
            or report.get("calendar_gate") != "BLOCKED"
            or len(report.get("reports", [])) != 3):
        raise ValueError("Refuse unsafe or non-3-day research output")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for day in report["reports"]:
        name = "KB21_RESEARCH_" + day["day"]
        (root / (name + ".json")).write_text(
            json.dumps(day, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        (root / (name + ".md")).write_text(render_md(day), encoding="utf-8")
        pdf = root / (name + ".pdf")
        render_pdf(day, pdf)
        if not pdf.is_file() or pdf.stat().st_size < 1000 or not pdf.read_bytes().startswith(b"%PDF-"):
            raise ValueError("Research PDF missing or corrupt for " + day["day"])
        paths.append(str(pdf))
    (root / "KB21_RESEARCH_MANIFEST.json").write_text(
        json.dumps({**report, "pdf_files": [Path(p).name for p in paths]},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queue", required=True)
    p.add_argument("--packet", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--limit-per-day", type=int, default=6)
    a = p.parse_args()
    q, packet = (json.loads(Path(path).read_text(encoding="utf-8"))
                 for path in (a.queue, a.packet))
    result = build(q, packet, limit_per_day=a.limit_per_day)
    pdfs = write_reports(result, a.outdir)
    print("KB21 alternative research-first lane:",
          len(pdfs), "actual dated PDFs generated, future sources:",
          [r["selected_for_source_review"] for r in result["reports"]],
          "original Calendar Gate remains BLOCKED; no scores/PLAY.")


if __name__ == "__main__":
    main()
