"""Reconcile manually verified Premier League OPTA benchmark with immutable FD archive.

The OPTA values are separately documented observations, never inferred from
the FD archive itself. This tool verifies data integrity, not source identity
or official bookmaker settlements. Fail closed on missing/ambiguous rows.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ALLOWED_MARKETS = ("fouls", "cards")


def reconcile(benchmark, archived):
    rows = benchmark.get("rows")
    if benchmark.get("schema") != "multimodel-opta-fd-crosscheck-evidence-v1" or not isinstance(rows, list):
        raise ValueError("benchmark_schema_invalid")
    if benchmark.get("pair_level_count") != 31 or len(rows) != 31:
        raise ValueError("benchmark_count_unverified")
    by = {}
    for row in archived:
        key = row.get("source_record_id")
        if key:
            by.setdefault(str(key), []).append(row)
    found = []
    seen = set()
    for row in rows:
        key = row["source_record_id"]
        if key in seen:
            raise ValueError("duplicate_benchmark_source_id")
        seen.add(key)
        matches = by.get(key, [])
        if len(matches) != 1:
            raise ValueError("missing_or_duplicate_fd_record_" + key)
        fd = matches[0]
        if (fd.get("source_provider") != "football-data.co.uk" or
                fd.get("league_code") != "E0" or
                fd.get("match_date") != row["match_date"]):
            raise ValueError("fd_source_or_date_mismatch_" + key)
        result = {"source_record_id": key, "match_date": row["match_date"],
                  "match": row["match"], "premier_league_match_id": row["premier_league_match_id"]}
        for market, source_field in (("fouls", "verified_opta_fouls_home_away"),
                                     ("cards", "verified_opta_yellow_home_away")):
            original = fd.get("events", {}).get(market)
            opta = row.get(source_field)
            if (not isinstance(original, list) or not isinstance(opta, list)
                    or len(original) != 2 or len(opta) != 2 or
                    any(type(x) is not int or x < 0 for x in original + opta)):
                raise ValueError("invalid_pair_" + key + "_" + market)
            result[market + "_FD"] = original
            result[market + "_recorded_OPTA"] = opta
            result[market + "_difference"] = [a - b for a, b in zip(original, opta)]
        result["opta_red_cards_recorded"] = row.get("opta_red_cards_home_away")
        found.append(result)
    deviations = {m: sum(any(z != 0 for z in r[m + "_difference"]) for r in found)
                  for m in ALLOWED_MARKETS}
    return {"schema": "multimodel-opta-fd-archive-reconciliation-v1",
            "source_archive_run_id": benchmark["source_archive_run_id"],
            "source_archive": benchmark["source_archive_file"],
            "premier_league_only": True, "pair_compared": len(found),
            "fouls_disagreement_matches": deviations["fouls"],
            "yellow_disagreement_matches": deviations["cards"],
            "red_cards_not_reconstructible_as_superbet_bookings": True,
            "superbet_settlement_equivalence_proven": False,
            "provider_Bookings_unit_proven": False,
            "rows": found}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--benchmark", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    res = reconcile(load(a.benchmark), load(a.events))
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OPTA_FD_MATCHES=" + str(res["pair_compared"]))
    print("OPTA_FD_FOUL_DISAGREEMENTS=" + str(res["fouls_disagreement_matches"]))
    print("OPTA_FD_YELLOW_DISAGREEMENTS=" + str(res["yellow_disagreement_matches"]))
    print("OPTA_SUPERBET_BOOKINGS_UNVERIFIED=true")


if __name__ == "__main__":
    main()
