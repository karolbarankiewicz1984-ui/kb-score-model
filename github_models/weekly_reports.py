"""Render seven Warsaw-day PDFs from ONE frozen A/B/C evaluation.

Rendering is strictly read-only w.r.t. model scores, sources and immutable
archives. Missing fixtures/source dates are shown as missing, not forecasted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path

from github_models.abc_chronological_pdf import render_day

DAYS = 7
SCHEMA = "github-models-seven-day-pdf-v1"


def build(root, base_day, *, days=DAYS):
    if type(days) is not int or not 1 <= days <= DAYS:
        raise ValueError("weekly_horizon_must_be_1_to_7")
    day = date.fromisoformat(str(base_day))
    root = Path(root)
    queue = json.loads((root / "queues" / (str(day) + ".json")).read_text(encoding="utf-8"))
    selected = json.loads((root / "filters" / ("ABC_" + str(day) + ".json")).read_text(encoding="utf-8"))
    expected = [(day + timedelta(days=i)).isoformat() for i in range(days)]
    if queue.get("dates") != expected:
        raise ValueError("frozen_queue_dates_do_not_match_requested_horizon")
    if not isinstance(selected.get("candidates"), list):
        raise ValueError("missing_frozen_abc_candidates")
    fixtures = {str(row["fixture_id"]): row for row in queue["fixtures"]}
    if len(fixtures) != len(queue["fixtures"]):
        raise ValueError("duplicate_frozen_fixture")
    missing = set(queue.get("missing_dates", []))
    invalid = set(queue.get("invalid_dates", []))
    if (missing | invalid) - set(expected) or missing & invalid:
        raise ValueError("inconsistent_frozen_queue_coverage")

    positions = []
    for report_day in expected:
        target = root / "pdf" / ("GITHUB_MODELS_V2_ABC_" + report_day + ".pdf")
        stats = render_day(
            selected, fixtures, str(target), report_day,
            source="Single frozen A/B/C run; odds unverified")
        if not target.is_file() or target.stat().st_size < 1024:
            raise ValueError("missing_or_empty_date_pdf:" + report_day)
        if target.read_bytes()[:5] != b"%PDF-":
            raise ValueError("invalid_pdf_header:" + report_day)
        status = ("source_snapshot_missing" if report_day in missing else
                  "source_snapshot_invalid" if report_day in invalid else "source_snapshot_valid")
        fixture_count = sum(row["kickoff_utc"][:10] == report_day
                            for row in fixtures.values()
                            if "kickoff_utc" in row)
        positions.append(dict(date=report_day, status=status,
                              fixtures_in_queue=fixture_count,
                              **stats))
    manifest = dict(schema=SCHEMA,
                    base_day=str(day), horizon_days=days,
                    frozen_at_utc=selected.get("input_cutoff_utc"),
                    source="one immutable A/B/C snapshot, no re-estimation",
                    odds_verified=False, probabilities_calibrated=False,
                    all_source_dates_valid=not (missing or invalid),
                    missing_dates=sorted(missing), invalid_dates=sorted(invalid),
                    reports=positions)
    path = root / "filters" / ("SEVEN_DAY_MANIFEST_" + str(day) + ".json")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="reports/github_models")
    parser.add_argument("--day", required=True, help="First report day in Europe/Warsaw")
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()
    result = build(args.root, args.day, days=args.days)
    print(json.dumps({"horizon_days": result["horizon_days"],
                      "all_source_dates_valid": result["all_source_dates_valid"],
                      "positions_by_date": {x["date"]: x["unique_positions"]
                                            for x in result["reports"]}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
