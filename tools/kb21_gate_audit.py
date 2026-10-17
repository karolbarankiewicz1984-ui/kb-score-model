"""Read-only KB21 candidate provenance diagnostic; NOT the original LIVE model.

Real xG / projected goals and large goal samples were never mandatory in the
original analyst-led 35/35/30 method. Missing auxiliary metrics are warnings,
not false Calendar Gate failures. This audit NEVER grants freeze or PLAY.
"""
import argparse
import json
import math
from pathlib import Path

# These API proxy ratings are diagnostics only, not recovered LIVE 35/35/30 scores.
DIAGNOSTIC_FIELDS = ("structural_0_100", "quality_0_100", "matchup_0_100")
OPTIONAL_FIELDS = ("home_expected_goals", "away_expected_goals")


def assess(record):
    reasons = []
    warnings = []
    if not record.get("fixture_verified_official"):
        reasons.append("OFFICIAL_FIXTURE_UNVERIFIED")
    if not record.get("fixture_verified_independent"):
        reasons.append("INDEPENDENT_FIXTURE_UNVERIFIED")
    sources = record.get("sources") or []
    if len(set(str(source) for source in sources)) < 2:
        reasons.append("SOURCE_PROVENANCE_INSUFFICIENT")
    if (record.get("fixture_verified_official") and record.get("fixture_verified_independent")
            and not record.get("calendar_evidence")):
        reasons.append("CALENDAR_EVIDENCE_MISSING")
    if sources and all("api-football" in str(source).lower() for source in sources):
        reasons.append("ONLY_ONE_SOURCE_PROVIDER")

    # API proxy score fields do not themselves reproduce original STR/QUAL/MATCH.
    for name in DIAGNOSTIC_FIELDS:
        v = record.get(name)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            warnings.append("MISSING_" + name.upper())
        elif not 0 <= v <= 100:
            warnings.append("OUT_OF_RANGE_" + name.upper())

    for name in OPTIONAL_FIELDS:
        v = record.get(name)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            warnings.append("MISSING_" + name.upper())
        elif not .05 <= v <= 6:
            warnings.append("OUT_OF_RANGE_" + name.upper())

    rates = record.get("api_goal_rates") or {}
    for side in ("home", "away"):
        side_rates = rates.get(side)
        if not isinstance(side_rates, dict) or side_rates.get("sample_size", 0) < 5:
            warnings.append("GOAL_HISTORY_INSUFFICIENT_" + side.upper())

    # A human must still assess original STR/QUAL/MATCH, P(model), lineup,
    # source authenticity and FULL competition coverage before any freeze.
    return {
        "fixture_id": record.get("fixture_id"),
        "event": record.get("event"),
        "ready_for_review": not reasons,
        "blocking_reasons": reasons,
        "warnings": warnings,
        "freeze_allowed": False,
        "kb_status": "NOT_ASSIGNED",
        "original_scoring_recovered": False,
    }


def audit(data):
    rows = [assess(r) for r in data.get("candidates", [])]
    ready = sum(x["ready_for_review"] for x in rows)
    reason_counts = {}
    warning_counts = {}
    for row in rows:
        for reason in row["blocking_reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for warning in row["warnings"]:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    return {
        "date": data.get("date"),
        "status": "GATE_AUDIT_ONLY",
        "total": len(rows),
        "ready_for_review": ready,
        "blocked": len(rows) - ready,
        "blocker_counts": dict(sorted(reason_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
        "rows": rows,
        "calendar_gate": "UNVERIFIED" if data.get("calendar_gate") != "VERIFIED" else "REVIEW_REQUIRED",
        "kb_n_effect": 0,
        "dev_n_effect": 0,
        "register_writes": False,
        "note": ("Data availability diagnostic only. xG, projected goals and goal samples are optional. "
                 "Review eligibility does NOT mean official complete calendar or LIVE KB21 restored."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = audit(data)
    out = Path(args.output) if args.output else Path("reports/kb21_gate") / (str(report["date"]) + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "total": report["total"], "blocked": report["blocked"],
                      "ready_for_review": report["ready_for_review"], "warnings": report["warning_counts"]}))


if __name__ == "__main__":
    main()
