"""PitchAPI-first read-only input gate for three-day MULTIMODEL reports.

Does not compute picks, odds, model scores or overwrite historical TOP.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json

WARSAW = ZoneInfo("Europe/Warsaw")


def three_day_pitchapi_inventory(start_date: str, snapshot_dir: str | Path, *, as_of: str) -> list[dict]:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        raise ValueError("as_of_timezone_required")
    if cutoff.astimezone(WARSAW).date() != start:
        raise ValueError("start_date_not_current_warsaw_day")
    result = []
    for offset in range(3):
        day = (start + timedelta(days=offset)).isoformat()
        path = Path(snapshot_dir) / (day + ".json")
        item = {"date": day, "source": "PitchAPI", "status": "missing",
                "fixtures": [], "top_authorized": False, "quotes_authorized": False,
                "model_scores_authorized": False, "blockers": []}
        if not path.is_file():
            item["blockers"].append("pitchapi_snapshot_missing")
            result.append(item)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema") != "pitchapi-prematch-context-v1" or data.get("target_date") != day or data.get("source") != "PitchAPI":
                raise ValueError("pitchapi_schema_date_source_mismatch")
            stamp = datetime.fromisoformat(data["snapshot_utc"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp > cutoff:
                raise ValueError("pitchapi_snapshot_after_report_cutoff")
            rows = data.get("fixtures")
            if not isinstance(rows, list):
                raise ValueError("pitchapi_fixtures_invalid")
            seen = set()
            for row in rows:
                kickoff = datetime.fromisoformat(row["kickoff_utc"].replace("Z", "+00:00"))
                if kickoff.tzinfo is None or kickoff.astimezone(WARSAW).date().isoformat() != day:
                    raise ValueError("pitchapi_kickoff_date_invalid")
                if stamp >= kickoff:
                    raise ValueError("pitchapi_snapshot_not_prematch")
                match_id = str(row["pitch_match_id"])
                if match_id in seen:
                    raise ValueError("pitchapi_duplicate_fixture")
                seen.add(match_id)
                for side in ("home_recent", "away_recent"):
                    sample = row[side]
                    for previous in sample.get("samples", []):
                        previous_time = datetime.fromisoformat(previous["kickoff_utc"].replace("Z", "+00:00"))
                        if previous_time.tzinfo is None or previous_time >= stamp:
                            raise ValueError("pitchapi_historical_lookahead")
                item["fixtures"].append({
                    "pitch_match_id": match_id, "league": row.get("league"),
                    "home": row.get("home"), "away": row.get("away"),
                    "kickoff_utc": row["kickoff_utc"],
                    "both_sides_sufficient": bool(row.get("both_sides_sufficient")),
                    "home_recent": row["home_recent"], "away_recent": row["away_recent"],
                })
            item["status"] = "context_only"
            item["snapshot_utc"] = data["snapshot_utc"]
            item["fixtures_count"] = len(item["fixtures"])
            item["sufficient_fixtures"] = sum(r["both_sides_sufficient"] for r in item["fixtures"])
            item["blockers"].append("independent_scored_market_and_exact_quote_not_available_from_pitchapi_context")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            item["status"] = "invalid"
            item["fixtures"] = []
            item["blockers"].append(str(exc))
        result.append(item)
    return result
