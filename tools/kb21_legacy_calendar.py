"""Strict, API-free calendar gate for KB21 manual recovery.

Input JSON must contain date, official_source, independent_source and fixtures.
Each fixture needs matching records from both sources with identical kickoff,
competition, home and away. Source URLs are audit evidence, not automatically verified.
No network requests, no paid API, no changes to LIVE model.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def check(data):
    errors = []
    if not isinstance(data, dict):
        return {"status": "BLOCKED", "errors": ["Input is not an object"], "fixtures": []}
    date = data.get("date")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        errors.append("Invalid date")
    for field in ("official_source", "independent_source"):
        source = data.get(field)
        if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://") or not source.get("retrieved_at"):
            errors.append(f"Missing auditable {field} URL/time")
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("No independently matched fixtures")
        fixtures = []
    accepted = []
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            errors.append(f"Fixture {index}: invalid entry")
            continue
        a, b = fixture.get("official"), fixture.get("independent")
        keys = ("competition", "home", "away", "kickoff")
        if not isinstance(a, dict) or not isinstance(b, dict) or any(not a.get(k) or a.get(k) != b.get(k) for k in keys):
            errors.append(f"Fixture {index}: source disagreement or missing details")
            continue
        try:
            kickoff = datetime.fromisoformat(a["kickoff"])
            if kickoff.tzinfo is None:
                raise ValueError("Timezone missing")
        except (TypeError, ValueError):
            errors.append(f"Fixture {index}: kickoff must include timezone")
            continue
        if date and kickoff.astimezone(ZoneInfo("Europe/Warsaw")).date().isoformat() != date:
            errors.append(f"Fixture {index}: kickoff date outside requested date")
            continue
        accepted.append({k: a[k] for k in keys})
    # Even exact fixture matching cannot prove the entire daily calendar is complete.
    # An analyst must explicitly sign off coverage after checking official schedules.
    if data.get("coverage_reviewed") is not True:
        errors.append("Full competition coverage not reviewed")
    return {"status": "REVIEW_REQUIRED" if not errors else "BLOCKED", "errors": errors, "fixtures": accepted,
            "note": "Matching user-supplied entries is not independent verification of source authenticity or calendar completeness. Never auto-publish PLAY."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = check(json.loads(Path(args.input).read_text(encoding="utf-8")))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status']}: {len(result['fixtures'])} matches, {len(result['errors'])} errors")


if __name__ == "__main__":
    main()
