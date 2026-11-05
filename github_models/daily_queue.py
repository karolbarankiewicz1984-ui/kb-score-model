"""Independent GitHub Models daily fixture queue.

Uses existing PitchAPI snapshots read-only. Never imports MULTIMODEL scores or
selects fixtures based on bookmaker odds. No fabricated model predictions.
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
MODELS = ("dixon-coles", "elo", "xgboost")

def build_queue(snapshot_dir, *, start_date, as_of_utc):
    as_of = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise ValueError("as_of_timezone_required")
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    if as_of.astimezone(WARSAW).date() != start:
        raise ValueError("date_not_current_warsaw_day")
    items, missing, invalid = [], [], []
    seen = set()
    for offset in range(3):
        day = (start + timedelta(days=offset)).isoformat()
        path = Path(snapshot_dir) / (day + ".json")
        if not path.exists():
            missing.append(day)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            snap = datetime.fromisoformat(payload["snapshot_utc"].replace("Z", "+00:00"))
            if (snap.tzinfo is None or snap > as_of or
                payload["target_date"] != day or payload["source"] != "PitchAPI" or
                payload["schema"] != "pitchapi-prematch-context-v1" or
                not isinstance(payload["fixtures"], list)):
                raise ValueError("invalid_snapshot")
            day_rows = []
            for f in payload["fixtures"]:
                kick = datetime.fromisoformat(f["kickoff_utc"].replace("Z", "+00:00"))
                if kick.tzinfo is None or kick <= as_of or snap >= kick:
                    continue
                if kick.astimezone(WARSAW).date().isoformat() != day:
                    # Provider groups some cross-midnight games by UTC date.
                    # Skip the out-of-day fixture, never invalidate the entire snapshot.
                    continue
                fid = str(f["pitch_match_id"])
                if fid in seen:
                    raise ValueError("duplicate_fixture")
                if not all(isinstance(f.get(k), str) and f[k].strip()
                           for k in ("league", "home", "away")):
                    raise ValueError("invalid_teams")
                seen.add(fid)
                day_rows.append(dict(fixture_id=fid, league=f["league"], home=f["home"],
                                     away=f["away"], kickoff_utc=f["kickoff_utc"],
                                     snapshot_utc=payload["snapshot_utc"], league_id=f.get("league_id"),
                                     context_sufficient=bool(f.get("both_sides_sufficient")),
                                     models_requested=list(MODELS)))
            items.extend(day_rows)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            invalid.append(day)
    return dict(schema="github-models-fixture-queue-v1", generated_at_utc=as_of_utc,
                dates=[(start + timedelta(days=i)).isoformat() for i in range(3)],
                missing_dates=missing, invalid_dates=invalid,
                fixtures=sorted(items, key=lambda x: (x["kickoff_utc"], x["fixture_id"])),
                note="Queue only; not model predictions. Each model independently checks training readiness.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", default="data/pitchapi/prematch")
    parser.add_argument("--output-dir", default="reports/github_models/queues")
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    start = as_of.astimezone(WARSAW).date().isoformat()
    queue = build_queue(args.snapshot_dir, start_date=start, as_of_utc=args.as_of)
    path = Path(args.output_dir) / (start + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GitHub Models queue: {len(queue['fixtures'])} fixtures, missing={queue['missing_dates']}, invalid={queue['invalid_dates']}")

if __name__ == "__main__":
    main()
