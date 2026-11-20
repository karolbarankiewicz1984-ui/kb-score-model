"""Independent SHADOW post-match audit; immutable first pre-match forecast per selection."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from github_models.abc_metrics import metrics
from github_models.elo_engine import utc
from github_models.settlement import (CachedHistoricalPool, fixture_index,
                                      matching_outcomes, source_match_date)


def settle_one(frozen, queue, history, at):
    now = utc(at)
    fixtures = fixture_index(queue)
    out = []
    cache = {}
    for c in frozen.get("candidates", []):
        fid = str(c["fixture_id"])
        if fid not in fixtures:
            raise ValueError("shadow_unknown_fixture")
        f = fixtures[fid]
        start = utc(f["kickoff_utc"])
        before = utc(c["frozen_at_utc"])
        if not before < start or before > now:
            raise ValueError("shadow_not_prospective")
        p = c["probability"]
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("invalid_shadow_probability")
        market, selection, line = c["market"], c["selection"], c["line"]
        if not ((market == "btts" and selection in ("yes", "no") and line is None)
                or (market == "handicap" and selection in ("home", "away")
                    and line in (-1.5, 1.5))):
            raise ValueError("unverified_shadow_market_identity")
        row = {"fixture_id": fid, "market": market, "selection": selection,
               "line": line, "probability": p, "status": "pending",
               "frozen_at_utc": c["frozen_at_utc"]}
        if start >= now:
            out.append(row)
            continue
        if fid not in cache:
            try:
                cache[fid] = (matching_outcomes(f, history, as_of_utc=at,
                    resolved_identity=c.get("resolved_identity")), None)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                cache[fid] = (None, type(exc).__name__)
        games, error = cache[fid]
        if error:
            row.update(status="unmapped", reason="identity_" + error)
        elif len(games) != 1:
            row.update(status="unresolved",
                       reason="no_exact_final" if not games else "ambiguous_final")
        else:
            game = games[0]
            hg, ag = game["home_goals"], game["away_goals"]
            if any(type(v) is not int or v < 0 for v in (hg, ag)):
                row.update(status="unresolved", reason="invalid_final_score")
            else:
                hit = ((hg > 0 and ag > 0) == (selection == "yes")
                       if market == "btts" else
                       (hg + line > ag if selection == "home" else ag + line > hg))
                row.update(status="settled", hit=bool(hit),
                           actual_goals=[hg, ag],
                           source_match_date=source_match_date(game).isoformat(),
                           source_fixture_id=game.get("fixture_id"))
        out.append(row)
    return out


def audit(root, historical_results, at):
    root = Path(root)
    pool = CachedHistoricalPool(historical_results)
    # Earliest archived snapshot for an exact fixture/market/side/line is
    # selected, so changing forecasts later cannot rewrite the original.
    records, duplicate = {}, 0
    archive_count = 0
    for path in sorted((root/"shadow").glob("*/*.json")):
        rel = path.relative_to(root/"shadow")
        qpath = root/"queues"/rel
        if not qpath.is_file():
            continue
        frozen = json.loads(path.read_text(encoding="utf-8"))
        queue = json.loads(qpath.read_text(encoding="utf-8"))
        if frozen.get("schema") != "multimodel-v2-shadow-markets-v1":
            continue
        for row in settle_one(frozen, queue, pool, at):
            key = (row["fixture_id"], row["market"], row["selection"], row["line"])
            if key not in records or utc(row["frozen_at_utc"]) < utc(records[key]["frozen_at_utc"]):
                records[key] = row
            else:
                duplicate += 1
        archive_count += 1
    groups = defaultdict(list)
    for r in records.values():
        groups[r["market"]].append(r)
    return {
        "schema": "multimodel-v2-shadow-audit-v1", "as_of_utc": at,
        "archives_processed": archive_count,
        "unique_forecasts": len(records), "duplicates_suppressed": duplicate,
        "status": dict(Counter(r["status"] for r in records.values())),
        "summary": [{"market": m, **metrics(rows)} for m, rows in sorted(groups.items())],
        "calibration": "not_proven", "bookmaker_roi": None,
        "production_promoted": False,
        "note": "No recorded exact market odds are used here. Never infer ROI.",
    }


def main():
    p = argparse.ArgumentParser()
    for key in ("archive-dir", "history", "as-of", "output"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    history = json.loads(Path(a.history).read_text(encoding="utf-8"))
    report = audit(a.archive_dir, history, a.as_of)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print("SHADOW_AUDIT_ARCHIVES=" + str(report["archives_processed"]))
    print("SHADOW_AUDIT_SETTLED=" + str(report["status"].get("settled", 0)))


if __name__ == "__main__":
    main()
