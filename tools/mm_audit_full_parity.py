"""Full offline replay against pinned evidence; print aggregate/hash only.

Execute in separate reference and candidate Python processes with their own
PYTHONPATH. No sports endpoints, no generated forecast or report publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from github_models import abc_audit_runner, shadow_audit
from github_models.settlement import CachedHistoricalPool

AT = "2026-11-25T18:13:46Z"
DIGEST = "ea610904dd34f3b697bce61cb43e30813f364c798a7b7a902cde0affb9fe3e7c"

def serialized(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if hashlib.sha256(a.evidence.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("wrong_evidence_digest")
    with ZipFile(a.evidence) as z:
        history, events = [json.loads(z.read("data/github_models/settlement_verified_"+k+".json"))
                           for k in ("results","events")]
    original = CachedHistoricalPool.lookup
    report = {}
    for name, run in (
        ("abc", lambda: abc_audit_runner.run(a.archive, history, events, AT)),
        ("shadow", lambda: shadow_audit.audit(a.archive, history, AT)),
    ):
        transcript = hashlib.sha256()
        calls = 0
        def lookup(self, fixture, *, as_of_utc, resolved_identity=None):
            nonlocal calls
            try:
                result = original(self, fixture, as_of_utc=as_of_utc, resolved_identity=resolved_identity)
                response = ("ok", result)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                response = (type(error).__name__, str(error))
                calls += 1
                transcript.update(serialized((fixture, as_of_utc, resolved_identity, response))+b"\n")
                raise
            calls += 1
            transcript.update(serialized((fixture, as_of_utc, resolved_identity, response))+b"\n")
            return result
        CachedHistoricalPool.lookup = lookup
        started = perf_counter()
        try:
            result = run()
        finally:
            CachedHistoricalPool.lookup = original
        if calls == 0 or result["archives_processed"] == 0:
            raise ValueError("empty_replay")
        report[name] = {
            "report_sha256": hashlib.sha256(serialized(result)).hexdigest(),
            "lookup_sha256": transcript.hexdigest(),
            "lookup_calls": calls,
            "archives": result["archives_processed"],
            "records": result["unique_candidate_records"] if name == "abc" else result["unique_forecasts"],
            "seconds": round(perf_counter()-started, 3),
        }
        print(name, json.dumps(report[name],sort_keys=True), flush=True)
    a.out.write_text(json.dumps(report,sort_keys=True),encoding="utf-8")

if __name__ == "__main__":
    main()
