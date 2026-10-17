"""Conservative ESPN-vs-football-data.org calendar comparison for KB21 recovery.

Reads *already stored* independent snapshots; does not call paid APIs.
A match is only a SECOND SOURCE CANDIDATE, never official organizer evidence
or proof of full-day coverage. Calendar Gate stays BLOCKED, no model/Sheet writes.
"""
import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Explicit competition IDs only: do not match same-named clubs across leagues.
ESPN_TO_FDO = {
    "eng.1": "PL", "esp.1": "PD", "ita.1": "SA", "ger.1": "BL1",
    "fra.1": "FL1", "por.1": "PPL", "ned.1": "DED",
    "uefa.champions": "CL",
}


def _canonical(name):
    name = unicodedata.normalize("NFKD", str(name or "")).casefold()
    name = "".join(c for c in name if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", name)
    if tokens and tokens[-1] == "fc":
        tokens.pop()
    if tokens and tokens[0] == "fc":
        tokens.pop(0)
    return " ".join(tokens)


def _instant(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None and dt.utcoffset() is not None:
            return dt
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def crosscheck(queue, snapshots, tolerance_minutes=5):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected queue JSON with a fixtures list")
    if not 0 <= tolerance_minutes <= 30:
        raise ValueError("tolerance_minutes must be 0..30")
    output = {**queue, "calendar_gate": "BLOCKED", "status": "REVIEW_REQUIRED",
              "publication": "DIAGNOSTIC / NO PLAY"}
    days = sorted(set(queue.get("days", [])) | {
        f["date_warsaw"] for f in queue["fixtures"] if f.get("date_warsaw")
    })
    indexed = {}
    invalid = {}
    for day in days:
        snapshot = snapshots.get(day)
        if snapshot is None:
            continue
        if (not isinstance(snapshot, dict) or snapshot.get("provider") != "football-data.org"
                or snapshot.get("date") != day or not isinstance(snapshot.get("fixtures"), list)):
            invalid[day] = "INVALID_OR_MISMATCHED_INDEPENDENT_SNAPSHOT"
            continue
        indexed[day] = snapshot

    per_day = {day: Counter() for day in days}
    used_provider_ids = Counter()
    evaluated = []
    for f in queue["fixtures"]:
        row = dict(f)
        day = f.get("date_warsaw")
        league = f.get("fixture_id", "").split(":")[0]
        code = ESPN_TO_FDO.get(league)
        matched = []
        status = "NO_INDEPENDENT_SNAPSHOT"
        source = indexed.get(day)
        if day in invalid:
            status = invalid[day]
        elif code is None:
            status = "UNSUPPORTED_PROVIDER_LEAGUE_MAPPING"
        elif source is None:
            status = "NO_INDEPENDENT_SNAPSHOT"
        elif source.get("requested_competitions") and code not in source["requested_competitions"]:
            status = "OUTSIDE_PROVIDER_SNAPSHOT_SCOPE"
        else:
            parts = f.get("fixture", "").split(" - ", 1)
            moment = _instant(f.get("kickoff"))
            if len(parts) != 2 or moment is None:
                status = "INVALID_ESPN_FIXTURE"
            else:
                home, away = [_canonical(x) for x in parts]
                for other in source["fixtures"]:
                    if not isinstance(other, dict) or other.get("competition_code") != code:
                        continue
                    other_time = _instant(other.get("kickoff_utc"))
                    if other_time is None or not home or not away:
                        continue
                    if (_canonical(other.get("home_team")) == home
                            and _canonical(other.get("away_team")) == away
                            and abs((other_time - moment).total_seconds()) <= tolerance_minutes * 60
                            and other.get("provider_match_id") is not None):
                        matched.append(other)
                status = ("MATCHED_FOR_REVIEW" if len(matched) == 1
                          else "AMBIGUOUS_MATCH" if matched else "NO_NAME_TIME_MATCH")
        match = matched[0] if status == "MATCHED_FOR_REVIEW" else None
        if match is not None:
            used_provider_ids[(day, str(match["provider_match_id"]))] += 1
        row["independent_crosscheck"] = {
            "status": status, "provider": "football-data.org" if source else None,
            "provider_match_id": match["provider_match_id"] if match else None,
            "competition_code": code, "official_verified": False,
            "calendar_gate": "BLOCKED", "freeze_allowed": False,
        }
        evaluated.append(row)

    # Never count a single provider match as uniquely matched by two candidates.
    for row in evaluated:
        check = row["independent_crosscheck"]
        key = (row.get("date_warsaw"), str(check["provider_match_id"]))
        if check["status"] == "MATCHED_FOR_REVIEW" and used_provider_ids[key] > 1:
            check["status"] = "AMBIGUOUS_MATCH"
            check["provider_match_id"] = None
        per_day.setdefault(row.get("date_warsaw"), Counter())[check["status"]] += 1

    output["fixtures"] = evaluated
    output["crosscheck_summary"] = {
        day: {"total_candidates": sum(f.get("date_warsaw") == day for f in evaluated),
              "statuses": dict(sorted(per_day[day].items())),
              "snapshot_loaded": day in indexed,
              "snapshot_invalid": invalid.get(day)}
        for day in days
    }
    output["crosscheck_note"] = (
        "Independent provider matching only, NOT an official or complete calendar. "
        "Missing provider coverage must not be called a missing fixture. "
        "No score, pre-match freeze, PLAY or historical observation is authorized."
    )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("--snapshots-dir", default="data/football_data_org")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    snapshots = {}
    for day in queue.get("days", []):
        path = Path(args.snapshots_dir) / (str(day) + ".json")
        if path.is_file():
            try:
                snapshots[day] = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                snapshots[day] = {"provider": "INVALID", "date": day, "fixtures": []}
    result = crosscheck(queue, snapshots)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(x["statuses"].get("MATCHED_FOR_REVIEW", 0)
                for x in result["crosscheck_summary"].values())
    print(f"{total} unverified fixture cross-matches, Calendar Gate BLOCKED")


if __name__ == "__main__":
    main()
