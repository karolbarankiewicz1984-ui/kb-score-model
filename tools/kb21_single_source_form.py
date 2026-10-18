"""Real API-Football team-form evidence for a small two-day KB21 research shortlist.

Use ONLY the validated sole API-Football calendar for fixture selection,
and ONLY API-Football /fixtures?team=...&last=12 for past match evidence.
This module never converts historical goals to STR/QUAL/MATCH or P(model):
the original analyst-led method requires a documented independent judgment.
The old Poisson implementation in kb21_engine.py is explicitly experimental.

Default to 5 matches per date; active workflow can explicitly choose up to 30.
Never exceed the configured global call cap or the provider's quota reserve.
No odds API and no external schedule or inferred missing matches.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

from tools.api_market_http import ApiClient
from tools.kb21_api_prematch import historic_goal_rates
from tools.kb21_api_diagnostic import diagnose as experimental_diagnose
from tools.kb21_single_source_calendar import BASE, WARSAW, DAY_SCHEMA, SCHEMA, _iso_datetime

OUT_SCHEMA = "kb21-single-provider-team-form-v1"
MAX_PER_DAY = 30
DEFAULT_PER_DAY = 5
DEFAULT_HISTORY_CALLS = 80
DEFAULT_QUOTA_RESERVE = 25
PRIMARY = {
    ("England", "Premier League"), ("Spain", "La Liga"),
    ("Italy", "Serie A"), ("Germany", "Bundesliga"),
    ("France", "Ligue 1"),
}
EUROPE = {
    "UEFA Champions League", "UEFA Europa League",
    "UEFA Europa Conference League", "UEFA Conference League",
}


def priority(event):
    # Organize the WORK QUEUE by competition relevance, not win certainty
    # or betting value. No probability/score is assigned here.
    pair = event.get("country"), event.get("league")
    if pair in PRIMARY:
        return 0
    if event.get("league") in EUROPE:
        return 1
    return 2


def _clock(now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock needed")
    return now.astimezone(timezone.utc)


def shortlist(manifest, day_docs, now=None, max_per_day=DEFAULT_PER_DAY):
    now = _clock(now)
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
            or manifest.get("single_source_gate") != "PASS_SOURCE"
            or manifest.get("authoritative_calendar_provider") != "API-Football"
            or manifest.get("provider_count") != 1
            or manifest.get("safe_to_publish_play") is not False
            or len(manifest.get("dates", [])) != 2
            or len(set(manifest["dates"])) != 2
            or not isinstance(max_per_day, int) or isinstance(max_per_day, bool)
            or not 1 <= max_per_day <= MAX_PER_DAY
            or not isinstance(day_docs, dict)
            or set(day_docs) != set(manifest["dates"])):
        raise ValueError("Expected exactly two signed-off-by-provider API-only days")
    work = []
    for day in manifest["dates"]:
        doc = day_docs[day]
        if (not isinstance(doc, dict) or doc.get("schema") != DAY_SCHEMA
                or doc.get("date") != day or doc.get("source") != "API-Football"
                or doc.get("single_source_gate") != "PASS_SOURCE"
                or doc.get("safe_to_publish_play") is not False
                or doc.get("pre_match_fixtures") != len(doc.get("candidates", []))
                or not isinstance(doc.get("provider_events"), list)
                or doc.get("provider_total_events") != len(doc["provider_events"])
                or _iso_datetime(doc.get("snapshot_utc")) is None):
            raise ValueError("Source calendar integrity error: " + day)
        source_by_id = {}
        for row in doc["provider_events"]:
            fid = row.get("fixture_id") if isinstance(row, dict) else None
            if not isinstance(fid, int) or isinstance(fid, bool) or fid in source_by_id:
                raise ValueError("Invalid duplicate/absent provider event: " + day)
            source_by_id[fid] = row
        candidates = []
        seen = set()
        for item in doc["candidates"]:
            if not isinstance(item, dict) or item.get("provider") != "API-Football":
                raise ValueError("Foreign candidate in source calendar")
            fid = item.get("fixture_id")
            if fid in seen or source_by_id.get(fid) != item:
                raise ValueError("Candidate not identical to validated provider event")
            seen.add(fid)
            kickoff = _iso_datetime(item.get("kickoff_utc"))
            if (kickoff is None or kickoff.astimezone(WARSAW).date().isoformat() != day
                    or not item.get("eligible_for_prematch_research")
                    or item.get("status") != "NS"):
                raise ValueError("Candidate not in active source or invalid status")
            if kickoff <= now:
                continue
            candidates.append(item)
        candidates.sort(key=lambda e: (
            priority(e), e["kickoff_utc"], e["fixture_id"]))
        work.append({
            "day": day, "source_calendar_candidates": len(doc["candidates"]),
            "still_prematch_candidates": len(candidates),
            "shortlisted_for_real_team_history": len(candidates[:max_per_day]),
            "skipped_from_shortlist": max(0, len(candidates) - max_per_day),
            "games": candidates[:max_per_day],
        })
    return work


def _history(response, team_id, kickoff, captured):
    if not isinstance(response, dict) or response.get("errors") not in ([], {}):
        raise ValueError("API-Football team history request failed")
    rows = response.get("response")
    if not isinstance(rows, list):
        raise ValueError("API team history malformed response")
    if (not isinstance(response.get("results"), int)
            or response["results"] != len(rows)
            or len(rows) > 12):
        raise ValueError("API team history inconsistent row count")
    # Prevent using a future match or results that were not known at the
    # actual source snapshot time. Rates require 5 genuine completed games.
    cutoff = min(kickoff, captured)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid past fixture record")
        fi = row.get("fixture")
        if not isinstance(fi, dict):
            raise ValueError("API team history missing fixture block")
        when = _iso_datetime(fi.get("date"))
        if when is None:
            raise ValueError("API team history has unparseable kickoff")
        # API may return an as-yet uncompleted match; it is ignored by
        # historic_goal_rates, not interpreted as a completed score.
        status = fi.get("status") or {}
        if status.get("short") in {"FT", "AET", "PEN"} and when >= cutoff:
            raise ValueError("History endpoint contains finished future/late data")
    rates = historic_goal_rates(rows, team_id, cutoff)
    return rates


def build_source_pack(calendar_manifest, day_docs, client, key, now=None,
                      max_per_day=DEFAULT_PER_DAY,
                      max_history_calls=DEFAULT_HISTORY_CALLS,
                      quota_reserve=DEFAULT_QUOTA_RESERVE):
    now = _clock(now)
    if not key:
        raise ValueError("API_FOOTBALL_KEY required for factual team history")
    if (not isinstance(max_history_calls, int) or isinstance(max_history_calls, bool)
            or not 1 <= max_history_calls <= 80):
        raise ValueError("max_history_calls must be an integer between 1 and 80")
    if (not isinstance(quota_reserve, int) or isinstance(quota_reserve, bool)
            or not 0 <= quota_reserve <= 1000):
        raise ValueError("quota_reserve must be an integer between 0 and 1000")
    selected = shortlist(calendar_manifest, day_docs, now, max_per_day)
    history = {}
    call_count = 0
    quota_remaining = None
    fetch_stop = None
    skipped_team_lookups = 0
    output = []
    for block in selected:
        records = []
        for item in block["games"]:
            kickoff = _iso_datetime(item["kickoff_utc"])
            team_data = {}
            for side in ("home", "away"):
                team_id = item.get(side + "_team_id")
                if not isinstance(team_id, int) or isinstance(team_id, bool) or team_id <= 0:
                    team_data[side] = {
                        "status": "MISSING_API_TEAM_ID",
                        "last_completed_games": None,
                    }
                    continue
                if team_id not in history:
                    if fetch_stop is None and call_count >= max_history_calls:
                        fetch_stop = "HISTORY_CALL_BUDGET_REACHED"
                    if fetch_stop:
                        skipped_team_lookups += 1
                        team_data[side] = {
                            "status": fetch_stop,
                            "last_completed_games": None,
                        }
                        continue
                    payload, headers = client.get(BASE, key, "fixtures", team=team_id, last=12)
                    history[team_id] = _history(payload, team_id, kickoff, now)
                    call_count += 1
                    remaining_raw = headers.get("x-ratelimit-requests-remaining") if isinstance(headers, dict) else None
                    if remaining_raw is not None:
                        try:
                            remaining = int(remaining_raw)
                        except (TypeError, ValueError, OverflowError):
                            raise ValueError("Unusable API daily request remaining header")
                        if remaining < 0:
                            raise ValueError("API remaining request count cannot be negative")
                        quota_remaining = remaining
                        if remaining <= quota_reserve:
                            fetch_stop = "DAILY_API_QUOTA_RESERVE_REACHED"
                rates = history[team_id]
                team_data[side] = {
                    "status": "HISTORY_5_TO_10" if rates else "LESS_THAN_5_COMPLETED_GAMES",
                    "last_completed_games": rates,
                }
            ready = all(team_data[side]["last_completed_games"] is not None
                        for side in ("home", "away"))
            # Reuse the pre-existing exploratory model verbatim. It blends
            # actual last-10 goals, NOT xG, and has never been calibrated
            # against the historical KB Score 2.1 methodology. Do not
            # promote it to analyst P(model), a market selection, or PLAY.
            shadow = experimental_diagnose({
                "api_goal_rates": {
                    side: team_data[side]["last_completed_games"]
                    for side in ("home", "away")
                }})
            if shadow["p_model"] is not None:
                raise ValueError("Experimental model must never fill KB21 P(model)")
            if shadow["status"] == "EXPLORATORY_API_ONLY":
                probs = shadow["diagnostic_probabilities"]
                if (set(probs) != {"home", "draw", "away", "over_2_5"}
                        or not all(isinstance(v, (int, float)) and
                                   math.isfinite(v) and 0 <= v <= 1
                                   for v in probs.values())
                        or abs(sum(probs[k] for k in ("home", "draw", "away")) - 1) > 0.0002):
                    raise ValueError("Invalid exploratory probability calculations")
            records.append({
                "fixture_id": item["fixture_id"], "event": item["home"] + " – " + item["away"],
                "date_warsaw": block["day"],
                "kickoff_utc": item["kickoff_utc"],
                "league": item["league"], "country": item["country"],
                "home_team_id": item["home_team_id"],
                "away_team_id": item["away_team_id"],
                "history": team_data,
                "both_sides_have_factual_goal_rates": ready,
                "form_metric": "ACTUAL_COMPLETED_MATCH_GOALS_NOT_XG",
                "experimental_goal_model": {
                    **shadow,
                    "role": "SHADOW_CALIBRATION_ONLY_NOT_KB21_P_MODEL",
                    "original_kb21_p_model": None,
                    "forecast_generated_before_market_prices": True,
                    "model_is_historically_validated": False,
                    "prediction_not_betting_recommendation": True,
                },
                "research_priority": "LEAGUE_CONTEXT_NOT_PREDICTION",
                "analyst_assessment": {
                    "STR_0_35": None, "QUAL_0_35": None,
                    "MATCH_0_30": None, "sport_score_0_100": None,
                    "P_model_pre_odds": None,
                    "analyst_documented_method": None,
                    "analyst_decision_utc": None,
                    "independent_sports_assessment_present": False,
                },
                "odds": None, "ev": None, "selection": None,
                "freeze_allowed": False, "safe_to_publish_play": False,
            })
        output.append({**{k: v for k, v in block.items() if k != "games"},
                       "matches": records})
    return {
        "schema": OUT_SCHEMA, "source": "API-Football",
        "calendar_gate": "PASS_SOURCE_ONLY_NOT_PLAY",
        "legacy_calendar_gate": "NOT_APPLICABLE_IN_SINGLE_SOURCE_MODE",
        "generated_at_utc": now.isoformat(),
        "dates": calendar_manifest["dates"],
        "days": output,
        "api_team_history_calls": call_count,
        "api_history_query_budget": max_history_calls,
        "api_daily_quota_reserve": quota_reserve,
        "api_daily_remaining_last_seen": quota_remaining,
        "history_fetch_stop_reason": fetch_stop,
        "team_history_queries_skipped": skipped_team_lookups,
        "historical_form_sampled": sum(len(x["matches"]) for x in output),
        "fixtures_with_two_valid_goal_histories": sum(
            bool(match["both_sides_have_factual_goal_rates"])
            for block in output for match in block["matches"]),
        "scoring_fields_filled_automatically": 0,
        "shadow_goal_forecasts_prepared": sum(
            row["experimental_goal_model"]["status"] == "EXPLORATORY_API_ONLY"
            for block in output for row in block["matches"]),
        "kb21_original_method_modified": False,
        "kb21_n_written": False, "register_writes": False,
        "safe_to_publish_play": False,
        "note": ("Evidence for a small actual match shortlist from a single "
                 "API provider, not automatic STR/QUAL/MATCH or the original "
                 "pre-price P(model). Pre-odds independent sports assessment "
                 "is still required; form goal average is not xG."),
    }


def render_day(day):
    lines = [
        "# KB Score 2.1 — rzeczywista forma drużyn: " + day["day"],
        "", "**TYLKO ANALIZA BADAWCZA — NIE TYPY I NIE PLAY.**",
        "", f"Wszystkie przyszłe mecze API: {day['source_calendar_candidates']}; "
        f"nadal nierozpoczęte: {day['still_prematch_candidates']}; "
        f"z historią: {day['shortlisted_for_real_team_history']}.",
        "Kolejność = priorytet rozgrywek, nie prognoza wyniku.",
        "WARTOŚCI PROCENTOWE PONIŻEJ to niewalidowany model cienia "
        "z faktycznych goli (nie xG). NIE jest to historyczne P(model), "
        "Sport Score, value ani typy do gry.",
        "",
    ]
    if not day["matches"]:
        lines.append("Nie ma meczów do przedmeczowej kontroli w tym dniu.")
    for item in day["matches"]:
        lines += [
            "## " + item["event"],
            f"- {item['league']} — start {item['kickoff_utc']} UTC; "
            f"ID API {item['fixture_id']}",
        ]
        for side, desc in (("home", "Gospodarze"), ("away", "Goście")):
            h = item["history"][side]
            rates = h["last_completed_games"]
            if rates:
                lines.append(
                    f"- {desc}: z {rates['sample_size']} ostatnich zakończonych gier "
                    f"gole zdobyte {rates['goals_for_per_match']:.2f}/mecz, "
                    f"stracone {rates['goals_against_per_match']:.2f}/mecz "
                    "(faktyczne GOLE, to NIE xG).")
            else:
                lines.append(f"- {desc}: {h['status']} — brak wymaganej próby.")
        shadow = item["experimental_goal_model"]
        if shadow["status"] == "EXPLORATORY_API_ONLY":
            p = shadow["diagnostic_probabilities"]
            lines.append(
                f"- SYGNAŁ EKSPERYMENTALNY (nie KB21): "
                f"1 {100*p['home']:.1f}%, X {100*p['draw']:.1f}%, "
                f"2 {100*p['away']:.1f}%, "
                f"over 2,5 {100*p['over_2_5']:.1f}%. "
                "Brak kalibracji, siły ligi, kontuzji i kursów.")
        else:
            lines.append("- SYGNAŁ EKSPERYMENTALNY: " +
                         str(shadow["status"]) + "; brak prognozy.")
        lines += [
            "- **STR —/35; QUAL —/35; MATCH —/30; "
            "P(model) przed kursem: —**.",
            "- Brak kursów oraz jakiegokolwiek automatycznego PLAY.",
            "",
        ]
    lines.append("Te niekalibrowane szacunki z 10 gier mogą służyć WYŁĄCZNIE "
                 "do osobnego audytu predykcji po meczu; nie otwierają PLAY.")
    lines.append("API Market/PitchAPI zachowują osobne oceny. "
                 "Nie kopiujemy ich do oryginalnego P(model).")
    return "\n".join(lines) + "\n"


def render_pdf(day, dest):
    """Compact factual pre-match briefing, never a betting recommendation."""
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, KeepTogether,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).is_file():
            if "KB21Form" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("KB21Form", candidate))
            font = "KB21Form"
            break
    else:
        font = "Helvetica"

    title = ParagraphStyle("FormTitle", fontName=font, fontSize=14, leading=19,
                           textColor=colors.HexColor("#20384F"),
                           spaceAfter=9)
    heading = ParagraphStyle("FormMatch", fontName=font, fontSize=9.4,
                             leading=13, textColor=colors.HexColor("#20384F"),
                             spaceBefore=7, spaceAfter=4)
    text = ParagraphStyle("FormText", fontName=font, fontSize=8.1,
                          leading=11.7, spaceAfter=3)
    warn = ParagraphStyle("FormWarning", fontName=font, fontSize=8.1,
                          leading=11.7, textColor=colors.HexColor("#943B28"),
                          spaceAfter=7)
    story = [
        Paragraph("KB Score 2.1 / Rzeczywista forma / " + day["day"], title),
        Paragraph("DANE BADAWCZE, NIE TYPY. Jedno źródło terminarza "
                  "i historii: API-Football. Originalne P(model) i "
                  "STR/QUAL/MATCH pozostają NIEOCENIONE.", warn),
        Paragraph("Kandydaci API: " + str(day["source_calendar_candidates"]) +
                  "; jeszcze nierozpoczęte: " +
                  str(day["still_prematch_candidates"]) +
                  "; wybrane do badania historii: " +
                  str(day["shortlisted_for_real_team_history"]) + ".", text),
        Spacer(1, 5),
    ]
    if not day["matches"]:
        story.append(Paragraph(
            "Brak przyszłych meczów w tej części badania. To nie jest "
            "certyfikat kompletności terminarza poza API.", text))
    for index, match in enumerate(day["matches"], 1):
        when = _iso_datetime(match["kickoff_utc"])
        label = when.astimezone(WARSAW).strftime("%H:%M")
        group = [
            Paragraph(escape(str(index) + ". " + match["event"] +
                             " / " + match["league"] + " / " + label +
                             " czasu polskiego"), heading),
        ]
        for side, name in (("home", "Gospodarze"), ("away", "Goście")):
            hist = match["history"][side]["last_completed_games"]
            if hist:
                value = (f"{name}: {hist['sample_size']} ostatnich ukończonych "
                         f"spotkań, gole strzelone {hist['goals_for_per_match']:.2f}, "
                         f"stracone {hist['goals_against_per_match']:.2f}/mecz. "
                         "To rzeczywiste GOLE, nie xG.")
            else:
                value = name + ": brak wystarczających ukończonych gier."
            group.append(Paragraph(escape(value), text))
        group += [
            Paragraph(
                ("CIEŃ niewalidowany z goli: "
                 f"1 {100*match['experimental_goal_model']['diagnostic_probabilities']['home']:.1f}% "
                 f"X {100*match['experimental_goal_model']['diagnostic_probabilities']['draw']:.1f}% "
                 f"2 {100*match['experimental_goal_model']['diagnostic_probabilities']['away']:.1f}% "
                 f"over 2,5 {100*match['experimental_goal_model']['diagnostic_probabilities']['over_2_5']:.1f}%.")
                if match["experimental_goal_model"]["status"] == "EXPLORATORY_API_ONLY"
                else "CIEŃ: brak historii pozwalającej na obliczenia.",
                text),
            Paragraph("Ocena oryginalna: STR —/35; QUAL —/35; MATCH —/30; "
                      "P(model) przed kursem: —.", text),
            Paragraph("Nie nadano Sport Score, kursu ani PLAY; "
                      "wymagana niezależna ocena.", warn),
        ]
        story.append(KeepTogether(group))
    doc = SimpleDocTemplate(str(dest), pagesize=A4, leftMargin=37,
                            rightMargin=37, topMargin=33, bottomMargin=33)
    doc.build(story)
    dest = Path(dest)
    if (not dest.is_file() or dest.stat().st_size < 1500
            or not dest.read_bytes().startswith(b"%PDF-")):
        raise ValueError("PDF rendering failed")


def shadow_snapshot(run, day):
    """Immutable-like pregame artifact for LATER independent outcome audit.

    This pure transformation performs NO odds lookup, bets, market scoring,
    or KB21 historical N mutations. Future settlement reads snapshots,
    never reruns predictions after knowing the result.
    """
    if (not isinstance(run, dict) or run.get("schema") != OUT_SCHEMA
            or run.get("source") != "API-Football"
            or run.get("safe_to_publish_play") is not False
            or not isinstance(day, dict) or day.get("day") not in run.get("dates", [])):
        raise ValueError("Shadow snapshot requires a real API-only research pack")
    generated = _iso_datetime(run.get("generated_at_utc"))
    if generated is None:
        raise ValueError("Missing valid run creation timestamp")
    predictions, seen = [], set()
    for match in day["matches"]:
        ident = match.get("fixture_id")
        kickoff = _iso_datetime(match.get("kickoff_utc"))
        if (not isinstance(ident, int) or isinstance(ident, bool)
                or ident in seen or kickoff is None or kickoff <= generated):
            raise ValueError("Do not retrospectively create duplicate/late predictions")
        seen.add(ident)
        shadow = match.get("experimental_goal_model") or {}
        if shadow.get("p_model") is not None or shadow.get("original_kb21_p_model") is not None:
            raise ValueError("Shadow cannot become original KB21 probability")
        if (match.get("analyst_assessment", {}).get("P_model_pre_odds") is not None
                or match.get("odds") is not None or match.get("ev") is not None
                or match.get("safe_to_publish_play") is not False):
            raise ValueError("Shadow snapshots cannot contain market claims")
        state = shadow.get("status")
        probabilities = shadow.get("diagnostic_probabilities")
        if state != "EXPLORATORY_API_ONLY":
            probabilities = None
        elif (not isinstance(probabilities, dict)
              or set(probabilities) != {"home", "draw", "away", "over_2_5"}
              or any(not isinstance(p, (int, float)) or isinstance(p, bool)
                     or not math.isfinite(p) or not 0 <= p <= 1
                     for p in probabilities.values())
              or abs(sum(probabilities[x] for x in ("home", "draw", "away")) - 1) > 0.0002):
            raise ValueError("Invalid market-independent shadow forecast")
        predictions.append({
            "fixture_id": ident, "event": match["event"],
            "league": match["league"], "kickoff_utc": match["kickoff_utc"],
            "forecast_run_started_utc": run["generated_at_utc"],
            "model_id": "kb21-api-last10-goals-shadow-v1",
            "forecast_status": state,
            "probabilities_1x2_over25": probabilities,
            "historical_goal_sample_size": {
                side: ((match["history"][side].get("last_completed_games") or {})
                       .get("sample_size"))
                for side in ("home", "away")},
            "calibrated": False, "original_kb21_p_model": None,
            "selection": None, "odds": None, "ev": None,
            "match_result": None,
            "register_writes": False, "safe_to_publish_play": False,
        })
    return {
        "schema": "kb21-api-shadow-forecast-snapshot-v1",
        "date": day["day"],
        "created_from_source_run_utc": run["generated_at_utc"],
        "provider": "API-Football", "model": "last10_goals_shadow_only",
        "isolated_from_original_kb21": True,
        "no_postmatch_prediction_regeneration": True,
        "predictions": predictions,
        "forecast_count": sum(x["probabilities_1x2_over25"] is not None
                              for x in predictions),
        "kb21_n_effect": 0, "register_writes": False,
        "publication": "RESEARCH_ONLY_NOT_PLAY",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-per-day", type=int, default=DEFAULT_PER_DAY)
    parser.add_argument("--max-history-calls", type=int, default=DEFAULT_HISTORY_CALLS)
    parser.add_argument("--reserve-daily-requests", type=int, default=DEFAULT_QUOTA_RESERVE)
    args = parser.parse_args()
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("API_FOOTBALL_KEY missing; no false history output")
    root = Path(args.calendar_dir)
    manifest = json.loads((root / "SINGLE_SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    docs = {
        day: json.loads((root / ("KB21_API_CALENDAR_" + day + ".json")).read_text(encoding="utf-8"))
        for day in manifest["dates"]
    }
    result = build_source_pack(manifest, docs, ApiClient(), key,
                               max_per_day=args.max_per_day,
                               max_history_calls=args.max_history_calls,
                               quota_reserve=args.reserve_daily_requests)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for item in result["days"]:
        name = "KB21_FORM_" + item["day"]
        (out / (name + ".json")).write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / (name + ".md")).write_text(render_day(item), encoding="utf-8")
        render_pdf(item, out / (name + ".pdf"))
        (out / ("KB21_SHADOW_" + item["day"] + ".json")).write_text(
            json.dumps(shadow_snapshot(result, item),
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "KB21_FORM_MANIFEST.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "days"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("KB21 factual form pack:", result["historical_form_sampled"],
          "future games; independent SHADOW forecasts:",
          result["shadow_goal_forecasts_prepared"],
          "; both teams have valid recent goals:",
          result["fixtures_with_two_valid_goal_histories"],
          "; API history calls:", result["api_team_history_calls"],
          "/", result["api_history_query_budget"],
          "; quota remaining:", result["api_daily_remaining_last_seen"],
          "; stopped:", result["history_fetch_stop_reason"],
          "; unavailable lookups:", result["team_history_queries_skipped"],
          "automated sport ratings:", result["scoring_fields_filled_automatically"],
          "PLAY: NO")


if __name__ == "__main__":
    main()
