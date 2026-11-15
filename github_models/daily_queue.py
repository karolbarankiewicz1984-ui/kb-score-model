"""Independent GitHub Models daily fixture queue.

Uses existing PitchAPI snapshots read-only. Never imports MULTIMODEL scores or
selects fixtures based on bookmaker odds. No fabricated model predictions.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
MODELS = ("dixon-coles", "elo", "xgboost")

def build_queue(snapshot_dir, *, start_date, as_of_utc, days=3):
    if type(days) is not int or not 1 <= days <= 7:
        raise ValueError("queue_horizon_days_must_be_1_to_7")
    as_of = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise ValueError("as_of_timezone_required")
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    if as_of.astimezone(WARSAW).date() != start:
        raise ValueError("date_not_current_warsaw_day")
    items, missing, invalid, partial, exclusions = [], [], [], [], []
    seen = set()
    for offset in range(days):
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
                payload["schema"] not in ("pitchapi-prematch-context-v1", "pitchapi-research-fixtures-v1") or
                not isinstance(payload["fixtures"], list)):
                raise ValueError("invalid_snapshot")
            if payload["schema"] == "pitchapi-research-fixtures-v1":
                status = payload.get("source_status")
                if status not in ("ok", "partial"):
                    raise ValueError("incomplete_pitchapi_source_response")
                if status == "partial":
                    # Individual source rows were rejected and are NOT eligible
                    # for prediction; retain verified fixture subset, but mark
                    # that the provider calendar is not exhaustive.
                    partial.append(day)
                    exclusions.append(dict(date=day, fixture_id=None,
                                           reason="partial_source_calendar",
                                           rejected_rows=len(payload.get("errors", []))))
            day_rows, day_seen = [], set()
            for f in payload["fixtures"]:
                kick = datetime.fromisoformat(f["kickoff_utc"].replace("Z", "+00:00"))
                if kick.tzinfo is None or kick <= as_of or snap >= kick:
                    exclusions.append(dict(date=day, fixture_id=f.get("pitch_match_id"),
                                           reason="kickoff_not_verified_future_prematch"))
                    continue
                if kick.astimezone(WARSAW).date().isoformat() != day:
                    # Provider groups some cross-midnight games by UTC date.
                    # Skip the out-of-day fixture, never invalidate the entire snapshot.
                    exclusions.append(dict(date=day, fixture_id=f.get("pitch_match_id"),
                                           reason="kickoff_outside_warsaw_snapshot_date"))
                    continue
                native_id = f["pitch_match_id"]
                if isinstance(native_id, bool) or not isinstance(native_id, (str, int)) or not str(native_id).strip():
                    raise ValueError("invalid_fixture_id")
                fid = str(native_id).strip()
                if fid in seen or fid in day_seen:
                    raise ValueError("duplicate_fixture")
                if not all(isinstance(f.get(k), str) and f[k].strip()
                           for k in ("league", "home", "away")):
                    raise ValueError("invalid_teams")
                day_seen.add(fid)
                day_rows.append(dict(fixture_id=fid, league=f["league"], home=f["home"],
                                     away=f["away"], kickoff_utc=f["kickoff_utc"],
                                     snapshot_utc=payload["snapshot_utc"], league_id=f.get("league_id"),
                                     country_code=f.get("country_code"),
                                     home_team_id=f.get("home_team_id"), away_team_id=f.get("away_team_id"),
                                     source_provider="PitchAPI", identity_blockers=f.get("identity_blockers", []),
                                     context_sufficient=bool(f.get("both_sides_sufficient")),
                                     models_requested=list(MODELS)))
            items.extend(day_rows)
            seen.update(day_seen)
        except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            invalid.append(day)
            exclusions.append(dict(date=day, fixture_id=None, reason="invalid_snapshot:" + str(exc)))
    return dict(schema="github-models-fixture-queue-v1", generated_at_utc=as_of_utc,
                dates=[(start + timedelta(days=i)).isoformat() for i in range(days)],
                missing_dates=missing, invalid_dates=invalid, partial_dates=partial,
                exclusions=exclusions,
                exclusion_summary=dict(Counter(row["reason"] for row in exclusions)),
                fixtures=sorted(items, key=lambda x: (x["kickoff_utc"], x["fixture_id"])),
                note="Queue only; not model predictions. Each model independently checks training readiness.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", default="data/pitchapi/prematch")
    parser.add_argument("--output-dir", default="reports/github_models/queues")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--days", type=int, default=3, choices=range(1, 8))
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    start = as_of.astimezone(WARSAW).date().isoformat()
    queue = build_queue(args.snapshot_dir, start_date=start, as_of_utc=args.as_of, days=args.days)
    path = Path(args.output_dir) / (start + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GitHub Models queue: {len(queue['fixtures'])} fixtures, missing={queue['missing_dates']}, invalid={queue['invalid_dates']}, partial={queue['partial_dates']}")

if __name__ == "__main__":
    main()
