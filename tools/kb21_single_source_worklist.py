"""All API-Football KB21 candidates -> evidence-first human worklist.

The bounded form pack enriches at most five games/day. This module preserves
ALL other in-scope future candidates instead of silently dropping them.
It cannot create STR/QUAL/MATCH, original P(model), freeze, odds or PLAY.
"""
import argparse
import json
from pathlib import Path

from tools.kb21_single_source_calendar import DAY_SCHEMA, SCHEMA, WARSAW, _iso_datetime

SCHEMA_OUT = "kb21-single-source-analyst-worklist-v1"
FORM_SCHEMA = "kb21-single-provider-team-form-v1"


def build(manifest, calendars, form_manifest, forms):
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
            or manifest.get("single_source_gate") != "PASS_SOURCE"
            or manifest.get("provider_count") != 1
            or manifest.get("authoritative_calendar_provider") != "API-Football"
            or manifest.get("safe_to_publish_play") is not False
            or not isinstance(manifest.get("dates"), list)
            or len(manifest["dates"]) != 2
            or len(set(manifest["dates"])) != 2):
        raise ValueError("Refuse unverified or multi-source calendar")
    days = manifest["dates"]
    if (not isinstance(form_manifest, dict)
            or form_manifest.get("schema") != FORM_SCHEMA
            or form_manifest.get("source") != "API-Football"
            or form_manifest.get("safe_to_publish_play") is not False
            or form_manifest.get("scoring_fields_filled_automatically") != 0
            or form_manifest.get("kb21_n_written") is not False
            or form_manifest.get("dates") != days
            or set(calendars) != set(days) or set(forms) != set(days)):
        raise ValueError("Refuse incompatible or promoted team-form research")
    created = _iso_datetime(form_manifest.get("generated_at_utc"))
    source_created = _iso_datetime(manifest.get("generated_at_utc"))
    if created is None or source_created is None or created < source_created:
        raise ValueError("Invalid source/form capture provenance")

    output = []
    for day in days:
        calendar, form = calendars[day], forms[day]
        if (not isinstance(calendar, dict)
                or calendar.get("schema") != DAY_SCHEMA
                or calendar.get("date") != day
                or calendar.get("source") != "API-Football"
                or calendar.get("single_source_gate") != "PASS_SOURCE"
                or calendar.get("safe_to_publish_play") is not False
                or calendar.get("pre_match_fixtures") != len(calendar.get("candidates", []))
                or not isinstance(calendar.get("provider_events"), list)
                or not isinstance(form, dict)
                or form.get("day") != day
                or not isinstance(form.get("matches"), list)):
            raise ValueError("Invalid calendar/form day provenance")

        source_by_id = {}
        for event in calendar["provider_events"]:
            if not isinstance(event, dict):
                raise ValueError("Malformed provider event")
            ident = event.get("fixture_id")
            if not isinstance(ident, int) or isinstance(ident, bool) or ident in source_by_id:
                raise ValueError("Invalid or duplicated provider ID")
            source_by_id[ident] = event

        eligible = {}
        for match in calendar["candidates"]:
            if not isinstance(match, dict):
                raise ValueError("Malformed calendar candidate")
            ident = match.get("fixture_id")
            kickoff = _iso_datetime(match.get("kickoff_utc"))
            if (ident in eligible or source_by_id.get(ident) != match
                    or kickoff is None or kickoff.astimezone(
                        __import__("zoneinfo").ZoneInfo("Europe/Warsaw")
                    ).date().isoformat() != day
                    or match.get("status") != "NS"
                    or match.get("provider") != "API-Football"
                    or match.get("eligible_for_prematch_research") is not True):
                raise ValueError("Candidate not identical to validated provider event")
            eligible[ident] = match

        context = {}
        for match in form["matches"]:
            if not isinstance(match, dict):
                raise ValueError("Invalid history row")
            ident = match.get("fixture_id")
            event = eligible.get(ident)
            if (ident in context or event is None
                    or match.get("event") != event["home"] + " – " + event["away"]
                    or match.get("kickoff_utc") != event["kickoff_utc"]
                    or match.get("home_team_id") != event["home_team_id"]
                    or match.get("away_team_id") != event["away_team_id"]
                    or match.get("safe_to_publish_play") is not False
                    or match.get("odds") is not None
                    or match.get("selection") is not None
                    or match.get("analyst_assessment", {}).get("P_model_pre_odds") is not None
                    or match.get("analyst_assessment", {}).get("sport_score_0_100") is not None):
                raise ValueError("History item contaminated or not in provider calendar")
            if not isinstance(match.get("history"), dict):
                raise ValueError("Invalid factual history provenance")
            context[ident] = match["history"]

        records = []
        for event in sorted(eligible.values(), key=lambda e: (e["kickoff_utc"], e["fixture_id"])):
            ident = event["fixture_id"]
            kickoff = _iso_datetime(event["kickoff_utc"])
            before_start = kickoff > created
            records.append({
                "fixture_id": ident,
                "fixture": event["home"] + " – " + event["away"],
                "competition": event["league"],
                "country": event["country"],
                "date_warsaw": day,
                "kickoff_utc": event["kickoff_utc"],
                "kickoff_warsaw": event["kickoff_warsaw"],
                "source": "API-Football",
                "source_snapshot_utc": calendar["snapshot_utc"],
                "status": ("AWAITING_HUMAN_PREMARKET_ASSESSMENT" if before_start
                           else "KICKOFF_PASSED_NO_LATE_FREEZE"),
                "factual_goal_history_available": ident in context,
                "factual_goal_history_not_xg": context.get(ident),
                "assessment_template": {
                    "fixture_id": ident,
                    "fixture": event["home"] + " – " + event["away"],
                    "kickoff": event["kickoff_utc"],
                    "market": None, "freeze_at": None, "analyst": None,
                    "reasoning": None, "str": None, "qual": None, "match": None,
                    "str_evidence": [], "qual_evidence": [], "match_evidence": [],
                    "p_model": None, "p_model_method": None, "confidence": None,
                },
                "sport_score": None, "original_kb21_p_model": None,
                "odds": None, "decision": None,
                "safe_to_publish_play": False,
            })
        output.append({
            "date": day, "calendar_candidates": len(eligible),
            "form_history_records": len(context),
            "analyst_assessments_generated": 0,
            "records": records,
        })
    return {
        "schema": SCHEMA_OUT, "dates": days, "created_at_utc": created.isoformat(),
        "source": "API-Football", "single_source_gate": "PASS_SOURCE_ONLY_NOT_PLAY",
        "days": output,
        "total_candidates": sum(x["calendar_candidates"] for x in output),
        "total_with_factual_goal_history": sum(x["form_history_records"] for x in output),
        "automatic_p_model_count": 0, "automatic_play_count": 0,
        "kb21_n_effect": 0, "register_writes": False,
        "safe_to_publish_play": False,
        "note": "All API calendar candidates, not just five enriched games/day. "
                "Factual goals are not xG; missing values are intentionally blank. "
                "An analyst must create a genuine pre-odds freeze and evidence. "
                "No historical P(model), automated selection, or PLAY.",
    }


def render_day(doc):
    lines = [
        "# KB Score 2.1 — kolejka analityczna / " + doc["date"], "",
        "**WYŁĄCZNIE PRZEDRYNKOWY SZABLON / NO PLAY.**",
        "Terminarz: wyłącznie API-Football, pełna lista kandydatów.",
        "STR/35, QUAL/35, MATCH/30 oraz P(model) pozostają nieustalone.",
        "Historia: faktyczne gole, NIE xG. Brak danych ≠ zero.", "",
        f"Kandydaci: {doc['calendar_candidates']}; z historią: {doc['form_history_records']}.", "",
        "| PL | Mecz | Rozgrywki | Historia goli | Stan |",
        "|---|---|---|---|---|",
    ]
    for item in doc["records"]:
        lines.append(
            f"| {item['kickoff_warsaw'][11:16]} | {item['fixture']} | "
            f"{item['competition']} | {'tak' if item['factual_goal_history_available'] else 'brak'} | "
            f"{item['status']} |"
        )
    if not doc["records"]:
        lines.append("| — | Brak kandydatów w poprawnej odpowiedzi API | — | — | — |")
    lines += ["", "Pola oceny przed kursem są w dołączonym JSON. Nie dopisywać wyników "
              "po starcie meczu. Nie uzupełniać archiwalnego N z tego raportu.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    src = Path(args.calendar_dir)
    manifest = json.loads((src / "SINGLE_SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    form_manifest = json.loads((src / "KB21_FORM_MANIFEST.json").read_text(encoding="utf-8"))
    calendars = {day: json.loads((src / ("KB21_API_CALENDAR_" + day + ".json")).read_text(encoding="utf-8"))
                 for day in manifest["dates"]}
    forms = {day: json.loads((src / ("KB21_FORM_" + day + ".json")).read_text(encoding="utf-8"))
             for day in manifest["dates"]}
    result = build(manifest, calendars, form_manifest, forms)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for day in result["days"]:
        prefix = "KB21_ANALYST_WORKLIST_" + day["date"]
        (out / (prefix + ".json")).write_text(
            json.dumps(day, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / (prefix + ".md")).write_text(render_day(day), encoding="utf-8")
    (out / "KB21_ANALYST_WORKLIST_MANIFEST.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "days"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("KB21 analyst worklist:", result["total_candidates"],
          "candidates across 2 days, factual goal histories:",
          result["total_with_factual_goal_history"], "; PLAY: NO")


if __name__ == "__main__":
    main()
