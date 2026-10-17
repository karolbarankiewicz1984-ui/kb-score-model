"""Compare candidate European Qualifiers to dated UEFA historical-edition evidence.

This is a CYCLE-CLASSIFICATION alert only: never attest team, date, kickoff,
complete organizer fixture inventories or verified zero-game days.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from tools.kb21_official_uefa_qualifiers_cycle import (
    EDITION, LAST_FINAL_DAY, SOURCE,
)


def compare(queue, official):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Expected KB21 fixture queue")
    days = queue["days"]
    if (not isinstance(official, dict)
            or official.get("schema") != "kb21-official-uefa-2026-qualifiers-cycle-v1"
            or official.get("league_id") != "fifa.worldq.uefa"
            or official.get("edition") != EDITION
            or official.get("official_url") != SOURCE
            or official.get("calendar_gate") != "BLOCKED"
            or official.get("full_calendar_verified") is not False
            or official.get("date_verified") is not False
            or official.get("kickoff_timezone_verified") is not False
            or official.get("reviewer_signed") is not False
            or official.get("confirmed_zero_matches") is not False
            or set(official.get("days", [])) != set(days)
            or not isinstance(official.get("day_cycle_status"), dict)
            or not isinstance(official.get("by_day"), dict)):
        raise ValueError("Invalid unsigned qualifiers cycle record")
    # Never allow a 'historical complete' flag from an untrusted artifact to
    # certify these dates: only actual organizer-specific day review can do it.
    if any(official["by_day"].get(day) != [] for day in days):
        raise ValueError("Historical cycle source cannot declare dated fixtures")
    valid_source = (official.get("status") == "DOCUMENTED_HISTORICAL_CYCLE_ONLY"
                    and official.get("errors") == []
                    and official.get("documented_last_playoff_day")
                    == LAST_FINAL_DAY.isoformat())
    if not valid_source and official.get("status") != "OFFICIAL_CYCLE_SOURCE_UNVERIFIED":
        raise ValueError("Untrusted cycle status")
    out = {
        "schema": "kb21-qualifiers-cycle-context-compare-v1",
        "league_id": "fifa.worldq.uefa",
        "days": {}, "organizer_source": SOURCE,
        "calendar_gate": "BLOCKED",
        "full_day_attestation": False,
        "publication": "DIAGNOSTIC / NO PLAY",
    }
    for day in days:
        after = dt.date.fromisoformat(day) > LAST_FINAL_DAY
        expected = ("AFTER_DOCUMENTED_WORLD_CUP_2026_QUALIFICATION_CYCLE"
                    if valid_source and after else
                    "HISTORICAL_CYCLE_DOCUMENTED_BUT_DAY_NOT_ATTESTED"
                    if valid_source else "ORGANIZER_CYCLE_SOURCE_UNVERIFIED")
        if official["day_cycle_status"].get(day) != expected:
            raise ValueError("Historical source's per-day status contradictory")
        candidates = [x for x in queue["fixtures"]
                      if isinstance(x, dict)
                      and x.get("date_warsaw") == day
                      and str(x.get("fixture_id", "")).startswith("fifa.worldq.uefa:")]
        out["days"][day] = {
            "statuses": {}, "organizer_count": 0,
            "espn_count": len(candidates), "cycle_status": expected,
            "historical_cycle_outside_window_candidates": (
                [x.get("fixture_id") for x in candidates] if valid_source and after
                else []),
            "time_approved_matches": 0, "no_games_certified": False,
            "calendar_gate": "BLOCKED",
        }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queue")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    report = compare(json.loads(Path(a.queue).read_text(encoding="utf-8")),
                     json.loads(Path(a.source).read_text(encoding="utf-8")))
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("UEFA European Qualifiers: historical cycle classification only; "
          f"unresolved candidates {sum(len(x['historical_cycle_outside_window_candidates']) for x in report['days'].values())}; "
          "Calendar Gate BLOCKED / NO PLAY")


if __name__ == "__main__":
    main()
