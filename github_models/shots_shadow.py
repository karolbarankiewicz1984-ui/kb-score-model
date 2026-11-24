"""Freeze isolated shots forecasts from historical archives and publish technical JSON."""
from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from github_models.shots_archive import archived_quotes, load_history
from github_models.shots_research import (
    FAMILIES, FREEZE_SCHEMA, HISTORY_SOURCE, LINES, MAX_HISTORY,
    SCOPES, SELECTIONS, identifier, poisson_probability, research_probability, timestamp,
)

ZONE = ZoneInfo("Europe/Warsaw")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, payload):
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def queue_digest(queue):
    return sha256(json.dumps(queue, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze(queue, collection, root, *, day, cutoff, replay=False):
    if queue.get("schema") != "github-models-fixture-queue-v1":
        raise ValueError("invalid_pitchapi_queue_schema")
    as_of = timestamp(cutoff)
    queue_cutoff = queue["generated_at_utc"]
    if timestamp(queue_cutoff) > as_of:
        raise ValueError("queue_unavailable_at_forecast_time")
    if not replay and as_of.astimezone(ZONE).date().isoformat() != day:
        raise ValueError("stale_day_for_prospective_shots")
    fixtures = {}
    for f in queue["fixtures"]:
        if timestamp(f["kickoff_utc"]).astimezone(ZONE).date().isoformat() != day:
            continue
        fid = str(f["fixture_id"])
        if fid in fixtures:
            raise ValueError("duplicate_queue_fixture")
        fixtures[fid] = f
    histories, ids, old_fixtures, coverage = load_history(root, cutoff)
    quotes, quote_audit = archived_quotes(collection, fixtures, cutoff, queue_cutoff)
    quote_lines = {}
    for fid, family, scope, line, _ in quotes:
        quote_lines.setdefault((fid, family, scope), set()).add(line)
    results = []
    for fid, fixture in fixtures.items():
        kickoff = fixture["kickoff_utc"]
        fixture_status = None
        if timestamp(kickoff) <= as_of:
            fixture_status = "fixture_already_started"
        elif (fixture.get("source_provider") != "PitchAPI" or fixture.get("identity_blockers")
              or not all(identifier(fixture.get(k)) for k in (
                  "fixture_id", "home_team_id", "away_team_id", "league_id", "country_code"))
              or fixture["home_team_id"] == fixture["away_team_id"]
              or timestamp(fixture.get("snapshot_utc")) > timestamp(queue_cutoff)):
            fixture_status = "unverified_prematch_fixture"
        sides, provenance = {}, {}
        if not fixture_status:
            for side in ("home", "away"):
                identity = ids.get(fixture[side + "_team_id"])
                if not identity:
                    continue
                history = histories[identity["legacy_team_id"]]
                history = [r for r in history if r["fixture_id"] not in old_fixtures.get(fid, ())]
                history = sorted(history, key=lambda x: timestamp(x["kickoff_utc"]), reverse=True)[:MAX_HISTORY]
                sides[side] = history
                provenance[side] = {**identity, "observations": history}
        candidates, markets = [], []
        for family in FAMILIES:
            team_rates = {
                side: research_probability(
                    history, family=family, selection="over", line=0.5,
                    forecast_cutoff_utc=cutoff, fixture_kickoff_utc=kickoff,
                ) for side, history in sides.items()
            }
            for scope in SCOPES:
                required = ("home", "away") if scope == "match" else (scope,)
                history_n = {side: len(sides.get(side, ())) for side in required}
                levels = {side: team_rates.get(side, {}).get("expected_count") for side in required}
                status = fixture_status
                if not status and any(side not in sides for side in required):
                    status = "unverified_team_crosswalk"
                if not status and any(rate is None for rate in levels.values()):
                    status = "insufficient_history"
                key = (fid, family, scope)
                lines = sorted(set(LINES[family]["match" if scope == "match" else "team"])
                               | quote_lines.get(key, set()))
                markets.append({"market": family, "scope": scope,
                                "status": status or "research_only_uncalibrated",
                                "history_n": history_n, "lines": lines,
                                "price_status": ("archived_exact_quote" if key in quote_lines
                                                 else "exact_quote_unavailable")})
                if status:
                    continue
                expected = sum(levels.values())
                for line in lines:
                    for selection in SELECTIONS:
                        quote = quotes.get((*key, line, selection))
                        candidates.append({"fixture_id": fid, "market": family, "scope": scope,
                                           "period": "fulltime", "line": line, "selection": selection,
                                           "probability": poisson_probability(expected, line, selection),
                                           "expected_count": expected, "history_n": history_n,
                                           "odds": quote["odds"] if quote else None, "quote": quote})
        results.append({"identity": public_identity_if_present(fixture),
                        "markets": markets, "history": provenance, "candidates": candidates})
    summary = Counter(m["status"] for f in results for m in f["markets"])
    summary["forecast_rows"] = sum(len(f["candidates"]) for f in results)
    summary["priced_forecast_rows"] = sum(r["odds"] is not None for f in results for r in f["candidates"])
    return {"schema": FREEZE_SCHEMA, "day": day, "mode": "historical_replay" if replay else "prospective",
            "frozen_at_utc": cutoff, "queue_cutoff_utc": queue_cutoff, "queue_sha256": queue_digest(queue),
            "training_source": HISTORY_SOURCE, "calibration_authorized": False,
            "fixtures": results, "coverage": coverage, "summary": dict(summary), "quote_audit": quote_audit}


def public_identity_if_present(row):
    # Preserve coverage reasons even when a fixture has incomplete identifiers.
    return {k: row.get(k) for k in ("fixture_id", "kickoff_utc", "home", "away", "league",
                                     "country_code", "league_id", "home_team_id", "away_team_id")}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--replay-cutoff", help="Backtest only. Never archived as prospective evidence.")
    args = parser.parse_args()
    cutoff = args.replay_cutoff or datetime.now(timezone.utc).isoformat()
    result = freeze(read(args.queue), read(args.collection), args.root,
                    day=args.day, cutoff=cutoff, replay=args.replay_cutoff is not None)
    write_new(args.output, result)
    print(json.dumps({k: result[k] for k in ("summary", "coverage", "quote_audit")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
