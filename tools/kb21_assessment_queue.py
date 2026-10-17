"""Join unverified fixtures with analyst assessment forms without inventing scores.

Fixture source is ESPN discovery. All outputs remain REVIEW / NO PLAY.
Usage: python -m tools.kb21_assessment_queue snapshot1.json snapshot2.json --output queue.json
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def build(paths):
    # Resolve all requested Warsaw dates BEFORE filtering any cross-midnight event.
    loaded = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    days = {source["date"] for source in loaded if source.get("date")}
    matches, errors, source_status = {}, [], {}
    for source in loaded:
        errors.extend(source.get("errors", []))
        if source.get("date"):
            days.add(source["date"])
            source_status[source["date"]] = source.get("sources", [])
        for f in source.get("fixtures", []):
            if not all(f.get(k) for k in ("league", "event_id", "home", "away", "kickoff")):
                continue
            try:
                kickoff = datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
                if kickoff.tzinfo is None:
                    continue
                warsaw = kickoff.astimezone(ZoneInfo("Europe/Warsaw"))
            except (ValueError, TypeError):
                continue
            if days and warsaw.date().isoformat() not in days:
                continue  # Never add a fourth unrequested Warsaw-local report day.
            key = (f["league"], f["event_id"])
            matches[key] = {
                "fixture_id": f"{f['league']}:{f['event_id']}", "fixture": f"{f['home']} - {f['away']}",
                "competition": f.get("competition", f["league"]),
                "kickoff": warsaw.isoformat(), "date_warsaw": warsaw.date().isoformat(),
                "calendar_source": "ESPN / unverified", "official_calendar": None,
                "independent_calendar": f.get("source", "ESPN third-party"),
                "calendar_gate": "BLOCKED", "markets": [],
                "assessment": {
                    # Directly compatible with kb21_analyst_assessment.validate.
                    # Blank fields are deliberate and MUST be filled pre-match by an analyst.
                    "fixture": f"{f['home']} - {f['away']}",
                    "fixture_id": f"{f['league']}:{f['event_id']}",
                    "kickoff": warsaw.isoformat(),
                    "market": None, "freeze_at": None, "analyst": None,
                    "reasoning": None, "str": None, "qual": None, "match": None,
                    "str_evidence": [], "qual_evidence": [], "match_evidence": [],
                    "sport_score": None, "p_model": None, "p_model_method": None,
                    "confidence": None,
                },
                "publication": "DIAGNOSTIC / NO PLAY"}
    if not days:
        days.update(f["date_warsaw"] for f in matches.values())
    return {"status": "REVIEW_REQUIRED", "calendar_gate": "BLOCKED",
            "days": sorted(days), "source_status": source_status,
            "source_errors": errors, "fixtures": sorted(matches.values(), key=lambda f: f["kickoff"]),
            "note": "Unverified fixture candidates only. No inferred Sport Score, P(model), market selection, or historical writes."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = build(args.inputs)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['fixtures'])} unverified fixture assessment forms")


if __name__ == "__main__":
    main()
