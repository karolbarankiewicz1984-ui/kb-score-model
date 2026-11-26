"""Read-only real archive benchmark; no provider calls or output data files."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from github_models.elo_engine import utc
from github_models.settlement import CachedHistoricalPool, matching_outcomes

AT = "2026-11-25T18:13:46Z"
DIGEST = "ea610904dd34f3b697bce61cb43e30813f364c798a7b7a902cde0affb9fe3e7c"

def outcome(f, pool, identity):
    try:
        return ("ok", matching_outcomes(f, pool, as_of_utc=AT, resolved_identity=identity))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return (type(e).__name__, str(e))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    args = p.parse_args()
    if hashlib.sha256(args.evidence.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("wrong_evidence_digest")
    with ZipFile(args.evidence) as z:
        pools = {k: json.loads(z.read("data/github_models/settlement_verified_"+k+".json"))
                 for k in ("results","events")}
    candidates = {}
    for path in sorted((args.archive/"frozen").glob("*/*.json")):
        rel = path.relative_to(args.archive/"frozen")
        qpath = args.archive/"queues"/rel
        if not qpath.is_file():
            continue
        load = lambda f: json.loads(f.read_text(encoding="utf-8"))
        queue = {str(f["fixture_id"]): f for f in load(qpath)["fixtures"]}
        for pred in load(path)["predictions"]:
            f = queue[str(pred["fixture_id"])]
            if utc(f["kickoff_utc"]) >= utc(AT) or utc(pred["frozen_at_utc"]) > utc(AT):
                continue
            identity = pred.get("resolved_identity")
            key = (str(f["fixture_id"]), json.dumps(identity,sort_keys=True))
            candidates.setdefault(key,(f,identity))
    # Round-robin leagues, deterministic sample. Full archive not claimed.
    groups = {}
    for f, identity in candidates.values():
        groups.setdefault(str(f.get("league")), []).append((f,identity))
    cases = []
    while groups and len(cases) < 48:
        for league in sorted(list(groups)):
            cases.append(groups[league].pop(0))
            if not groups[league]:
                del groups[league]
            if len(cases) == 48:
                break
    if len(cases) < 24:
        raise ValueError("insufficient_real_cases")
    total_direct = total_indexed = 0.0
    for label, rows in pools.items():
        start = perf_counter()
        expected = [outcome(f, rows, i) for f,i in cases]
        direct = perf_counter() - start
        start = perf_counter()
        indexed = CachedHistoricalPool(rows)
        actual = [outcome(f, indexed, i) for f,i in cases]
        elapsed = perf_counter() - start
        if expected != actual:
            raise AssertionError("real_archive_parity_mismatch:"+label)
        statuses = Counter("matched" if k=="ok" and v else "no_match" if k=="ok" else "blocked" for k,v in actual)
        print(json.dumps(dict(pool=label, rows=len(rows), cases=len(cases), status=dict(statuses),
              direct_seconds=round(direct,3), indexed_seconds=round(elapsed,3),
              mismatches=0, leagues=len({f["league"] for f,_ in cases})), sort_keys=True),flush=True)
        total_direct += direct
        total_indexed += elapsed
    print(json.dumps(dict(total_comparisons=2*len(cases), direct_seconds=round(total_direct,3),
          indexed_seconds=round(total_indexed,3), speedup=round(total_direct/max(total_indexed,1e-9),2))),flush=True)
    if total_indexed >= total_direct:
        raise ValueError("no_sample_speedup")

if __name__ == "__main__":
    main()
