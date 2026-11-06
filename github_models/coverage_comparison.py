"""Reproducible research coverage comparison against an isolated old checkout.

Readiness counts describe identity and historical sample gates, not successful
Dixon-Coles fitting or calibrated betting opportunities. No forecast is made.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from github_models.competition_identity import (
    COMPETITIONS, FOREIGN_COMPETITIONS, canonicalize, country_for_league,
)
from github_models.coverage_audit import audit
from github_models.elo_engine import eligible_history, utc
from github_models.event_markets import _event_samples

METRICS = ("identity_ready", "elo_ready", "dixon_coles_history_ready")


def baseline_audit(queue, history, *, baseline_root, as_of_utc):
    """Import the original code in a separate process and working directory."""
    root = Path(baseline_root).resolve()
    if not (root / "github_models" / "coverage_audit.py").is_file():
        raise ValueError("baseline_coverage_module_missing")
    program = (
        "import json, sys\n"
        "from github_models.coverage_audit import audit\n"
        "data=json.load(sys.stdin)\n"
        "print(json.dumps(audit(data['queue'],data['history'],as_of_utc=data['as_of_utc']),allow_nan=False))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(root))
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program], cwd=root, env=env,
        input=json.dumps(dict(queue=queue, history=history, as_of_utc=as_of_utc), allow_nan=False),
        capture_output=True, text=True, timeout=120, check=False,
    )
    if completed.returncode:
        # Tracebacks can contain local environment details; keep the failure
        # explicit without copying arbitrary subprocess output to reports.
        raise RuntimeError("baseline_audit_subprocess_failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("baseline_audit_not_json") from exc
    if not isinstance(result, dict) or not isinstance(result.get("fixtures"), list):
        raise ValueError("baseline_audit_invalid_schema")
    return result


def _index(report, fixture_ids):
    index = {}
    for row in report["fixtures"]:
        key = str(row["fixture_id"])
        if key in index:
            raise ValueError("duplicate_coverage_fixture")
        index[key] = row
    if set(index) != set(fixture_ids):
        raise ValueError("coverage_fixture_set_mismatch")
    return index


def _state(row, fixture, cutoff):
    # Old audits did not all reject already-started queued fixtures. Apply the
    # same entry gate to both summaries while retaining the original raw audit.
    if utc(fixture["kickoff_utc"]) <= cutoff:
        return dict.fromkeys(METRICS, False) | {"reason": "prediction_not_prematch"}
    resolved = row.get("identity_ready", bool(row.get("mapped_home") and row.get("mapped_away")))
    return dict(identity_ready=bool(resolved), elo_ready=bool(row.get("elo_ready")),
                dixon_coles_history_ready=bool(row.get("dixon_coles_history_ready")),
                reason=row.get("reason", "unspecified"))


def _totals(states):
    rows = list(states)
    total = len(rows)
    return dict(total=total, **{key: sum(row[key] for row in rows) for key in METRICS},
                reasons=dict(sorted(Counter(row["reason"] for row in rows).items())))


def compare(queue, history, events, *, baseline_root, as_of_utc, before_history=None):
    """Compare the two resolvers with identical as-of-eligible observations.

    ``before_history`` optionally supplies the old ingestion scope, for example
    five leagues, while ``history`` supplies the expanded scope to both codes.
    All stored queue fixtures remain in the denominator, including unsupported
    competitions and any fixtures which have started by the supplied cutoff.
    """
    cutoff = utc(as_of_utc)
    fixtures = queue["fixtures"]
    ids = [str(row["fixture_id"]) for row in fixtures]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_queue_fixture")
    available = eligible_history(history, frozen_at_utc=as_of_utc)
    before = baseline_audit(queue, available, baseline_root=baseline_root, as_of_utc=as_of_utc)
    after = audit(queue, available, as_of_utc=as_of_utc)
    old_scope = None
    if before_history is not None:
        old_scope = baseline_audit(
            queue, eligible_history(before_history, frozen_at_utc=as_of_utc),
            baseline_root=baseline_root, as_of_utc=as_of_utc,
        )
    reports = {"before_same_history": before, "after": after}
    if old_scope is not None:
        reports["before_original_history"] = old_scope
    indexed = {name: _index(report, ids) for name, report in reports.items()}
    states = {name: {} for name in reports}
    grouped = defaultdict(list)
    for fixture in fixtures:
        fid = str(fixture["fixture_id"])
        for name, index in indexed.items():
            states[name][fid] = _state(index[fid], fixture, cutoff)
        lid = fixture.get("league_id")
        key = str(lid) if lid is not None and str(lid).strip() else (
            "unverified:" + str(fixture.get("country_code") or "unknown") + ":" + str(fixture["league"]))
        grouped[key].append(fixture)
    leagues = []
    for key, members in sorted(grouped.items()):
        known = COMPETITIONS.get(key) or FOREIGN_COMPETITIONS.get(key)
        canonical_names, countries = set(), set()
        if known:
            canonical_names.add(known[0])
            countries.add(known[1])
        for fixture in members:
            try:
                canonical = canonicalize(fixture)
                canonical_names.add(canonical["league"])
                if canonical.get("country_code"):
                    countries.add(canonical["country_code"])
            except (ValueError, TypeError, KeyError):
                pass
        item = dict(league_id=key, raw_labels=sorted({f["league"] for f in members}),
                    canonical_leagues=sorted(canonical_names), countries=sorted(countries),
                    total=len(members), fixture_ids=[str(f["fixture_id"]) for f in members])
        for name in reports:
            item[name] = _totals(states[name][fid] for fid in item["fixture_ids"])
        item["identity_mapping_delta"] = item["after"]["identity_ready"] - item["before_same_history"]["identity_ready"]
        item["elo_ready_delta"] = item["after"]["elo_ready"] - item["before_same_history"]["elo_ready"]
        leagues.append(item)
    summary = {name: _totals(values.values()) for name, values in states.items()}
    for name in reports:
        if sum(league[name]["total"] for league in leagues) != len(fixtures):
            raise ValueError("coverage_denominator_not_conserved")
        for metric in METRICS:
            if sum(league[name][metric] for league in leagues) != summary[name][metric]:
                raise ValueError("coverage_metric_not_conserved")
    event_counts = {
        league: {market: len(_event_samples(events, market=market, league=league, cutoff=cutoff,
                                          country=country_for_league(league)))
                 for market in ("corners", "cards", "fouls")}
        for league in sorted({row["league"] for row in available})
    }
    result = dict(schema="github-models-coverage-comparison-v1", as_of_utc=as_of_utc,
                  scope="stored_queue_not_complete_provider_calendar", total=len(fixtures),
                  started_fixtures=sum(utc(row["kickoff_utc"]) <= cutoff for row in fixtures),
                  history_rows=len(history), eligible_history_rows=len(available),
                  event_history_rows=len(events), event_samples_available=event_counts,
                  summary=summary, leagues=leagues,
                  interpretation={
                      "before_same_history": "Original code and repaired code receive identical eligible expanded history.",
                      "before_original_history": "Optional old ingestion scope; use to measure the combined ingestion and identity change.",
                      "identity_ready": "Both team identities resolve uniquely within a verified competition.",
                      "elo_ready": "Identity and existing minimum team-history gates passed.",
                      "dixon_coles_history_ready": "Identity and league-history gate passed; not evidence that model fitting succeeds.",
                      "probabilities": "No probabilities are generated by this comparison.",
                      "archived_runs": "Older archived coverage has different code or inputs and is not this change's baseline.",
                  }, production_multimodel_unchanged=True)
    return result, reports


def _read(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for option in ("queue", "history", "events", "baseline-root", "as-of", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--before-history")
    args = parser.parse_args()
    inputs, hashes = {}, {}
    for name in ("queue", "history", "events", "before_history"):
        path = getattr(args, name)
        if path:
            inputs[name], hashes[name] = _read(path)
    result, reports = compare(inputs["queue"], inputs["history"], inputs["events"],
                              baseline_root=args.baseline_root, as_of_utc=args.as_of,
                              before_history=inputs.get("before_history"))
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.baseline_root,
                              capture_output=True, text=True, check=False)
    result["baseline_commit"] = revision.stdout.strip() if revision.returncode == 0 else None
    result["input_sha256"] = hashes
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result["audit_files"] = {}
    for name, report in reports.items():
        path = dest.with_name(dest.stem + "." + name + ".json")
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        result["audit_files"][name] = path.name
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in values.items() if key != "reasons"}
                      for name, values in result["summary"].items()}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
