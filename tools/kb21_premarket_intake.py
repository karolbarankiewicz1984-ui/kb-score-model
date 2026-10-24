"""KB Score 2.1 prospective, analyst-only pre-odds assessment intake.

Ties explicitly authored 35/35/30 and P(model) to the frozen API-Football
two-day worklist.  Source/format checks never prove that a human really
observed the evidence or restore the unknown original probability method.

No API calls, bookmaker input, Google Sheet changes, retroactive predictions,
automatic probability estimates, selection decisions or PLAY.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from tools.kb21_analyst_assessment import _time, validate as validate_assessment

SCHEMA = "kb21-prospective-premarket-intake-v1"
WORKLIST_SCHEMA = "kb21-single-source-analyst-worklist-v1"
PROHIBITED = frozenset({
    "odds", "bookmaker", "ev", "market_signal", "consensus", "result",
    "result_ft", "ft_score", "outcome", "bet_result", "pnl", "profit",
    "closing_odds", "brier", "logloss", "p_cal", "p_hit", "match_result",
    "settlement", "settled", "selection_decision", "decision",
})


def _clock(value):
    dt = _time(value)
    if dt is None:
        raise ValueError("Timestamp must have timezone")
    return dt.astimezone(timezone.utc)


def build(manifest, worklists, submissions=None, now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if (_time(manifest.get("created_at_utc")) is None
            or manifest.get("schema") != WORKLIST_SCHEMA
            or manifest.get("source") != "API-Football"
            or manifest.get("single_source_gate") != "PASS_SOURCE_ONLY_NOT_PLAY"
            or manifest.get("safe_to_publish_play") is not False
            or manifest.get("register_writes") is not False
            or manifest.get("kb21_n_effect") != 0
            or manifest.get("automatic_p_model_count") != 0
            or manifest.get("automatic_play_count") != 0
            or not isinstance(manifest.get("dates"), list)
            or len(manifest["dates"]) != 2
            or len(set(manifest["dates"])) != 2):
        raise ValueError("Refuse worklist that is not the strict two-day KB21 research source")
    created = _clock(manifest["created_at_utc"])
    days = manifest["dates"]
    if set(worklists) != set(days):
        raise ValueError("Worklist days do not match original manifest")
    canonical = {}
    counts = {}
    for day in days:
        worklist = worklists[day]
        if (worklist.get("date") != day
                or not isinstance(worklist.get("records"), list)
                or worklist.get("calendar_candidates") != len(worklist["records"])):
            raise ValueError("Malformed or incomplete fixture worklist")
        counts[day] = len(worklist["records"])
        for row in worklist["records"]:
            if not isinstance(row, dict):
                raise ValueError("Malformed worklist row")
            fid = row.get("fixture_id")
            if type(fid) is not int or fid <= 0 or fid in canonical:
                raise ValueError("Invalid or repeated canonical fixture ID")
            src = _clock(row.get("source_snapshot_utc"))
            kickoff = _clock(row.get("kickoff_utc"))
            if (row.get("source") != "API-Football"
                    or row.get("date_warsaw") != day
                    or not isinstance(row.get("fixture"), str)
                    or row.get("status") not in {
                        "AWAITING_HUMAN_PREMARKET_ASSESSMENT",
                        "KICKOFF_PASSED_NO_LATE_FREEZE"}
                    or row.get("safe_to_publish_play") is not False
                    or row.get("original_kb21_p_model") is not None
                    or row.get("sport_score") is not None
                    or row.get("odds") is not None
                    or row.get("decision") is not None
                    or not isinstance(row.get("assessment_template"), dict)
                    or row["assessment_template"].get("p_model") is not None
                    or row["assessment_template"].get("freeze_at") is not None
                    or src > created or src >= kickoff):
                raise ValueError("Source row is late, contaminated, or unverified")
            canonical[fid] = dict(row, source_clock=src, kickoff_clock=kickoff)
    if sum(counts.values()) != manifest.get("total_candidates"):
        raise ValueError("Original two-day fixture count mismatch")

    submitted = submissions if submissions is not None else []
    if not isinstance(submitted, list):
        raise ValueError("Submissions must be a list")
    seen = set()
    entries = {day: [] for day in days}
    validated = invalid = 0
    for value in submitted:
        if not isinstance(value, dict):
            raise ValueError("Every submission must be an object")
        fid = value.get("fixture_id")
        if type(fid) is not int or fid in seen:
            raise ValueError("Duplicate or invalid submitted fixture ID")
        seen.add(fid)
        if fid not in canonical:
            raise ValueError("Assessment for foreign/not-in-calendar fixture")
        src = canonical[fid]
        errors = []
        if src["status"] != "AWAITING_HUMAN_PREMARKET_ASSESSMENT":
            errors.append("Worklist was already late before assessment")
        if value.get("fixture") != src["fixture"] or value.get("kickoff") != src["kickoff_utc"]:
            errors.append("Fixture name/kickoff not identical to frozen API record")
        if value.get("source_snapshot_utc") != src["source_snapshot_utc"]:
            errors.append("Source snapshot time not identical to frozen API record")
        if value.get("date_warsaw") != src["date_warsaw"]:
            errors.append("Wrong local fixture date")
        if any(field in value for field in PROHIBITED):
            errors.append("Betting/settlement fields forbidden before market-freeze")
        assessed = validate_assessment(value)
        errors.extend(assessed["errors"])

        freeze = _time(value.get("freeze_at"))
        submitted_at = _time(value.get("submitted_at"))
        if freeze is not None:
            freeze = freeze.astimezone(timezone.utc)
            if freeze < src["source_clock"] or freeze < created:
                errors.append("Freeze predates the captured source/worklist")
            if freeze > now:
                errors.append("Freeze is in the future")
        if submitted_at is None:
            errors.append("Missing submitted_at with timezone (actual recorded submission time)")
        else:
            submitted_at = submitted_at.astimezone(timezone.utc)
            if submitted_at > now:
                errors.append("Submission time is in the future")
            if submitted_at >= src["kickoff_clock"]:
                errors.append("Submission cannot be recorded after kickoff")
            if submitted_at < created:
                errors.append("Submission predates the captured worklist")
            if freeze is not None and submitted_at < freeze:
                errors.append("Submission predates freeze")
        status = "REVIEW_REQUIRED" if not errors else "INVALID"
        validated += status == "REVIEW_REQUIRED"
        invalid += status == "INVALID"
        entries[src["date_warsaw"]].append({
            "fixture_id": fid, "fixture": src["fixture"],
            "kickoff_utc": src["kickoff_utc"],
            "submitted_at": value.get("submitted_at"),
            "freeze_at": value.get("freeze_at"),
            "status": status,
            "sport_score": assessed["sport_score"] if not errors else None,
            "p_model": assessed["p_model"] if not errors else None,
            "errors": errors, "human_review_not_attested": True,
            "safe_to_publish_play": False,
        })

    result_days = []
    for day in days:
        rows = sorted(entries[day], key=lambda x: x["fixture_id"])
        result_days.append({
            "date": day, "total_fixtures": counts[day],
            "submitted": len(rows),
            "awaiting_submission": counts[day] - len(rows),
            "valid_format_pending_human_review": sum(r["status"] == "REVIEW_REQUIRED" for r in rows),
            "invalid": sum(r["status"] == "INVALID" for r in rows),
            "rows": rows,
        })
    return {
        "schema": SCHEMA, "dates": days, "source": "API-Football",
        "validated_at_utc": now.isoformat(),
        "source_worklist_created_at_utc": created.isoformat(),
        "total_fixtures": sum(counts.values()),
        "submitted_assessments": len(submitted),
        "format_validated_pending_review": validated,
        "invalid_assessments": invalid,
        "automatic_p_model_count": 0, "automatic_play_count": 0,
        "kb21_n_effect": 0, "register_writes": False,
        "safe_to_publish_play": False,
        "publication": "RESEARCH / ANALYST REVIEW / NO PLAY",
        "human_evidence_authenticity_verified": False,
        "original_p_model_formula_recovered": False,
        "days": result_days,
    }


def render(day):
    lines = [
        "# KB Score 2.1 — oceny analityczne przed kursem / " + day["date"], "",
        "**RESEARCH / ANALYST REVIEW / NO PLAY**", "",
        "Kandydaci: " + str(day["total_fixtures"]) +
        "; przedstawione oceny: " + str(day["submitted"]) +
        "; poprawne formalnie: " + str(day["valid_format_pending_human_review"]) +
        "; niepoprawne: " + str(day["invalid"]) + ".",
        "Brak oceny nigdy nie jest zerem ani wynikiem modelu.", "",
        "| Mecz | Status | Sport Score | P(model) | Problemy |",
        "|---|---|---:|---:|---|",
    ]
    for row in day["rows"]:
        p = "—" if row["p_model"] is None else f'{row["p_model"] * 100:.1f}%'
        score = "—" if row["sport_score"] is None else str(row["sport_score"])
        errors = "; ".join(row["errors"]).replace("|", "/") or "kontrola człowieka wymagana"
        lines.append("| " + row["fixture"].replace("|", "/") +
                     " | " + row["status"] + " | " + score + " | " + p +
                     " | " + errors + " |")
    if not day["rows"]:
        lines.append("| Brak dostarczonych ocen analityka | AWAITING | — | — | NIE wyliczono P(model) |")
    lines += ["", "Wymagana rzeczywista kontrola źródeł, modelu i ceny PO freeze.",
              "Walidacja daty zapisu w JSON nie dowodzi autentyczności czasu.",
              "Brak automatycznych rekomendacji PLAY, kursów i zmian historycznego N.", ""]
    return "\n".join(lines)


def write(result, output):
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    for day in result["days"]:
        base = "KB21_PREMARKET_REVIEW_" + day["date"]
        (folder / (base + ".json")).write_text(
            json.dumps(day, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (folder / (base + ".md")).write_text(render(day), encoding="utf-8")
    (folder / "KB21_PREMARKET_REVIEW_MANIFEST.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "days"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--worklist-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--submissions-file", default="")
    args = p.parse_args()
    src = Path(args.worklist_dir)
    manifest_path = src / "KB21_ANALYST_WORKLIST_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    worklists = {
        day: json.loads((src / ("KB21_ANALYST_WORKLIST_" + day + ".json")).read_text(encoding="utf-8"))
        for day in manifest["dates"]
    }
    submissions = None
    if args.submissions_file:
        raw = json.loads(Path(args.submissions_file).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("assessments"), list):
            raise ValueError("Submissions file must contain an assessments array")
        submissions = raw["assessments"]
    result = build(manifest, worklists, submissions)
    result["worklist_sha256"] = hashlib.sha256(
        manifest_path.read_bytes() + b"\n" +
        b"\n".join((src / ("KB21_ANALYST_WORKLIST_" + day + ".json")).read_bytes()
                   for day in manifest["dates"])).hexdigest()
    write(result, args.output_dir)
    print("KB21 premarket review: " + str(result["total_fixtures"]) +
          " fixtures; " + str(result["format_validated_pending_review"]) +
          " assessments valid format; NO PLAY")


if __name__ == "__main__":
    main()
