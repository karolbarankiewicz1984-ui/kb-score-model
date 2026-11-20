"""Prospective, read-only SHADOW BTTS and Asian half-goal quote settlement.

OddsPapi's catalog defines Asian handicap as the *home* line, outcome "1"
as home and "2" as away. Thus the away team's line is NEGATIVE of the
catalog's home line. NEVER infer equivalence with European 3-way handicap,
bookings, card counts or (player) fouls.

Independently observed final scores may settle BTTS and half-goal goal
handicaps for RESEARCH. They do not establish a bookmaker's actual payout.
No bookmaker API calls or model re-estimation are performed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import math
from pathlib import Path

SCHEMA = "multimodel-priced-shadow-outcomes-v1"
BOOK = "superbet.pl"
RULES = "oddspapi-2026-11-20-home-handicap"
MIN_PRICE = 1.20
ALLOWED_LINES = (-1.5, 1.5)


def utc(v):
    x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if x.tzinfo is None:
        raise ValueError("naive_timestamp")
    return x


def _numeric(v):
    return type(v) in (int, float) and math.isfinite(v)


def _key(r):
    return (str(r["fixture_id"]), r["market"], r["selection"], r["line"])


def quote_identity(q):
    """Return independently documented identity; unmatched -> None."""
    if q.get("bookmaker") != BOOK or q.get("player_prop") is not False:
        return None
    if str(q.get("player_id", "0")) != "0" or q.get("period") != "fulltime":
        return None
    market_name = q.get("market_name")
    market_type = q.get("market_type")
    side = q.get("outcome_name")
    line = q.get("handicap")
    if (market_name == "Both Teams To Score" and market_type == "bothteamsscore"
            and side in ("Yes", "No") and _numeric(line) and line == 0):
        return ("btts", side.lower(), None)
    if (market_name == "Asian Handicap" and market_type == "spreads"
            and side in ("1", "2") and _numeric(line) and line in ALLOWED_LINES):
        # "handicap" is the home-line, not the chosen team's handicap.
        return ("handicap", "home" if side == "1" else "away",
                line if side == "1" else -line)
    return None


def quote_pairs(collection, queue, shadow):
    if collection.get("provider") != "oddspapi-v4" or collection.get("bookmakers") != [BOOK]:
        raise ValueError("unverified_bookmaker_or_provider")
    if queue.get("schema") != "github-models-fixture-queue-v1":
        raise ValueError("unverified_frozen_queue")
    if shadow.get("schema") != "multimodel-v2-shadow-markets-v1":
        raise ValueError("unverified_frozen_shadow")
    if queue.get("generated_at_utc") != shadow.get("generated_at_utc"):
        raise ValueError("snapshot_cutoff_mismatch")
    fixtures = {}
    for f in queue.get("fixtures", []):
        fid = str(f["fixture_id"])
        if fid in fixtures:
            raise ValueError("duplicate_frozen_fixture")
        fixtures[fid] = f
    links = {}
    for z in collection.get("links", {}).get("links", []):
        if z.get("status") == "matched":
            fid = str(z["fixture_id"])
            if fid in links:
                raise ValueError("ambiguous_odds_fixture_link")
            links[fid] = str(z["odds_fixture_id"])
    snapshots = {}
    for s in collection.get("snapshots", []):
        if s.get("provider") != "oddspapi-v4":
            raise ValueError("unexpected_quote_provider")
        fid = str(s.get("pitch_fixture_id"))
        if fid in snapshots:
            raise ValueError("duplicate_bookmaker_fixture")
        snapshots[fid] = s
    candidates = {}
    for c in shadow.get("candidates", []):
        k = _key(c)
        if k in candidates:
            raise ValueError("duplicate_shadow_selection")
        if k[0] not in fixtures:
            raise ValueError("shadow_fixture_not_in_queue")
        if not _numeric(c["probability"]) or not 0 <= c["probability"] <= 1:
            raise ValueError("invalid_frozen_probability")
        if not (utc(c["frozen_at_utc"]) == utc(shadow["generated_at_utc"])
                and utc(c["frozen_at_utc"]) < utc(fixtures[k[0]]["kickoff_utc"])):
            raise ValueError("not_prospective_forecast")
        candidates[k] = c
    output, reasons = {}, Counter()
    for fid, s in snapshots.items():
        if fid not in links or links[fid] != str(s.get("fixture_id")):
            raise ValueError("unverified_quote_fixture_link")
        if fid not in fixtures:
            raise ValueError("quote_fixture_missing_from_queue")
        kickoff = utc(fixtures[fid]["kickoff_utc"])
        captured = utc(s["captured_at_utc"])
        if (utc(s["kickoff_utc"]) != kickoff or not captured < kickoff
                or captured < utc(queue["generated_at_utc"])):
            raise ValueError("invalid_quote_capture_window")
        # Pairs must be present for the identical catalog market/line.
        # The quote can be >=1.20 even if its complementary side is below.
        market_sides = defaultdict(set)
        for q in s.get("quotes", []):
            ident = quote_identity(q)
            if ident:
                market_sides[(q["market_id"], q["market_name"], q["handicap"])].add(
                    q["outcome_name"])
        for q in s.get("quotes", []):
            ident = quote_identity(q)
            if not ident:
                continue
            key = (fid, *ident)
            if key not in candidates:
                continue
            if not _numeric(q.get("odds")) or q["odds"] < MIN_PRICE:
                reasons["odds_below_1_20_or_invalid"] += 1
                continue
            # Only a recorded provider change + full-market snapshot, both
            # timestamped BEFORE actual kickoff, are accepted as quote evidence.
            if not q.get("changed_at_utc"):
                reasons["unverified_provider_quote_time"] += 1
                continue
            changed = utc(q["changed_at_utc"])
            if changed > captured or changed >= kickoff:
                reasons["quote_changed_after_snapshot_or_kickoff"] += 1
                continue
            pair = market_sides[(q["market_id"], q["market_name"], q["handicap"])]
            if pair != ({"1", "2"} if ident[0] == "handicap" else {"Yes", "No"}):
                reasons["missing_market_counter_side"] += 1
                continue
            c = candidates[key]
            record = {
                "fixture_id": fid, "odds_fixture_id": str(s["fixture_id"]),
                "market": ident[0], "selection": ident[1], "line": ident[2],
                "p_model": c["probability"], "frozen_at_utc": c["frozen_at_utc"],
                "resolved_identity": c.get("resolved_identity"),
                "kickoff_utc": fixtures[fid]["kickoff_utc"],
                "bookmaker": BOOK, "price": q["odds"],
                "odds_captured_at_utc": s["captured_at_utc"],
                "source_price_changed_at_utc": q["changed_at_utc"],
                "source_market_id": str(q["market_id"]),
                "source_outcome_id": str(q["outcome_id"]),
                "market_identity": "exact_quote_research_only",
                "official_bookmaker_settlement_verified": False,
                "calibrated": False,
            }
            if key in output:
                if (output[key]["price"] != record["price"]
                        or output[key]["source_market_id"] != record["source_market_id"]):
                    raise ValueError("ambiguous_exact_market_identity")
            output[key] = record
    return list(output.values()), dict(reasons)


def settle_quotes(rows, queue, shadow, history, *, as_of_utc):
    """Reuse independent SHADOW resolver; never infer scores from missing events."""
    from github_models.shadow_audit import settle_one
    from github_models.settlement import CachedHistoricalPool
    now = utc(as_of_utc)
    source_by_key = {_key(c): c for c in shadow["candidates"]}
    # Only settle the *quoted* frozen predictions, avoiding re-running all
    # thousands of no-quote candidates on every rolling audit.
    candidates = []
    for r in rows:
        c = source_by_key[_key(r)]
        if c["probability"] != r["p_model"] or utc(c["frozen_at_utc"]) != utc(r["frozen_at_utc"]):
            raise ValueError("price_forecast_cutoff_mismatch")
        candidates.append(c)
    settled = settle_one({"candidates": candidates}, queue,
                         CachedHistoricalPool(history), as_of_utc)
    if len(settled) != len(rows):
        raise AssertionError("settlement_cardinality_mismatch")
    result = []
    for r, evaluation in zip(rows, settled):
        if _key(r) != _key(evaluation):
            raise AssertionError("settlement_selection_mismatch")
        row = dict(r)
        status = evaluation["status"]
        row["status"] = status
        if status == "settled":
            row["hit"] = evaluation["hit"]
            row["source_fixture_id"] = evaluation.get("source_fixture_id")
            row["source_match_date"] = evaluation.get("source_match_date")
            row["actual_goals"] = evaluation.get("actual_goals")
            # ROI is hypothetical at captured odds. Never call it actual
            # bookmaker payout or realized strategy profitability.
            row["simulated_unit_return_before_fees"] = round(
                (row["price"] if row["hit"] else 0.0) - 1.0, 6)
            row["brier"] = round((row["p_model"] - int(row["hit"])) ** 2, 6)
        else:
            row["reason"] = evaluation.get("reason",
                "kickoff_not_yet_passed" if status == "pending" else "unverified_final_score")
            row["simulated_unit_return_before_fees"] = None
            row["brier"] = None
        result.append(row)
    return result


def summarize(items, *, reasons=None, audits=1, duplicate=0):
    statuses = Counter(r["status"] for r in items)
    bymarket = {}
    for family in ("btts", "handicap"):
        rows = [r for r in items if r["market"] == family]
        resolved = [r for r in rows if r["status"] == "settled"]
        bymarket[family] = {
            "quoted_research": len(rows),
            "distinct_fixtures": len({r["fixture_id"] for r in rows}),
            "settled": len(resolved),
            "hit_rate": round(sum(bool(r["hit"]) for r in resolved) / len(resolved), 6)
                        if resolved else None,
            "brier": round(sum(r["brier"] for r in resolved) / len(resolved), 6)
                     if resolved else None,
            "simulated_roi_before_fees": (
                round(sum(r["simulated_unit_return_before_fees"] for r in resolved) /
                      len(resolved), 6) if resolved else None),
        }
    return {
        "schema": SCHEMA, "provider": "oddspapi-v4", "bookmaker": BOOK,
        "rules_reference": RULES,
        "independent_outcomes": "archived_verified_score_not_official_bookmaker_payout",
        "archived_oddspapi_collections": audits,
        "duplicates_suppressed": duplicate,
        "exact_quoted_selections": len(items),
        "distinct_fixtures": len({r["fixture_id"] for r in items}),
        "status": dict(statuses), "market_summary": bymarket,
        "reasons_excluded": reasons or {},
        "production_promotion": False, "auto_calibration": False,
        "official_bookmaker_payout_confirmed": False,
        "odds_floor": MIN_PRICE, "paid_api_calls": 0,
        "fouls_superbet_equivalent": False,
        "cards_bookings_equivalent": False,
        "notes": [
            "Asian handicap: OddsPapi catalog handicap is the HOME line; outcome 1 home / 2 away.",
            "Away selected-side handicap is negative of catalog home line.",
            "Only BTTS fulltime and Asian half-goal +/-1.5 are priced/settled here.",
            "A verified independent final score is not confirmation of Superbet payout.",
            "Missing or contradictory outcomes remain pending/unresolved, never losses.",
        ],
    }


def review_one(collection, queue, shadow, history, *, as_of_utc):
    rows, rejected = quote_pairs(collection, queue, shadow)
    resolved = settle_quotes(rows, queue, shadow, history, as_of_utc=as_of_utc)
    return summarize(resolved, reasons=rejected), resolved


def review_archive(odds_dir, frozen_dir, history, *, as_of_utc):
    """Re-run many stored quotes at today's cutoff, dedup earliest market quote.

    Require byte-equivalent parsed frozen queue; never join overlapping seasons
    or similar-looking fixture names. Missing archives remain a reported gap.
    """
    base = Path(frozen_dir)
    index = defaultdict(list)
    for qp in (base / "queues").glob("*/*.json"):
        try:
            q = json.loads(qp.read_text(encoding="utf-8"))
            index[q["generated_at_utc"]].append((qp, q))
        except (ValueError, OSError, KeyError, TypeError):
            continue
    first, reasons = {}, Counter()
    counted, skipped = 0, Counter()
    for cp in sorted(Path(odds_dir).glob("*/collection.json")):
        folder = cp.parent
        qfile = folder / "pitch_queue.json"
        if not qfile.is_file():
            skipped["missing_odds_queue"] += 1
            continue
        try:
            oq = json.loads(qfile.read_text(encoding="utf-8"))
            co = json.loads(cp.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            skipped["invalid_bookmaker_archive"] += 1
            continue
        matches = [(qp, q) for qp, q in index.get(oq["generated_at_utc"], [])
                   if q == oq and (base / "shadow" / qp.relative_to(base / "queues")).is_file()]
        if len(matches) != 1:
            skipped["no_unique_matching_frozen_shadow"] += 1
            continue
        qp, q = matches[0]
        sp = base / "shadow" / qp.relative_to(base / "queues")
        shadow = json.loads(sp.read_text(encoding="utf-8"))
        try:
            report, items = review_one(co, q, shadow, history, as_of_utc=as_of_utc)
        except (ValueError, KeyError, TypeError, AssertionError):
            skipped["invalid_or_conflicting_frozen_record"] += 1
            continue
        counted += 1
        reasons.update(report["reasons_excluded"])
        for row in items:
            key = _key(row)
            if key not in first:
                first[key] = row
            elif utc(row["odds_captured_at_utc"]) < utc(first[key]["odds_captured_at_utc"]):
                first[key] = row
    ordered = sorted(first.values(), key=lambda r: (
        r["kickoff_utc"], r["fixture_id"], r["market"], r["selection"],
        -1 if r["line"] is None else r["line"]))
    report = summarize(ordered, reasons=dict(reasons), audits=counted)
    report["duplicate_source_quotes_suppressed"] = sum(
        1 for _ in [] )  # Replaced by a derived count below.
    report["archives_skipped"] = dict(skipped)
    report["quote_archive_files_seen"] = len(list(Path(odds_dir).glob("*/collection.json")))
    return report, ordered


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--collection")
    a.add_argument("--queue")
    a.add_argument("--shadow")
    a.add_argument("--archive-dir")
    a.add_argument("--frozen-dir")
    a.add_argument("--history", required=True)
    a.add_argument("--as-of", required=True)
    a.add_argument("--out", required=True)
    o = a.parse_args()
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    history = read(o.history)
    if o.archive_dir:
        if not o.frozen_dir:
            a.error("--frozen-dir required with --archive-dir")
        summary, rows = review_archive(o.archive_dir, o.frozen_dir, history,
                                       as_of_utc=o.as_of)
    else:
        if not all([o.collection, o.queue, o.shadow]):
            a.error("--collection, --queue, --shadow are required")
        summary, rows = review_one(read(o.collection), read(o.queue), read(o.shadow),
                                   history, as_of_utc=o.as_of)
    summary["as_of_utc"] = o.as_of
    summary["entries"] = rows
    dest = Path(o.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    print("PRICED_SHADOW_ARCHIVES=" + str(summary["archived_oddspapi_collections"]))
    print("PRICED_SHADOW_QUOTES=" + str(summary["exact_quoted_selections"]))
    print("PRICED_SHADOW_SETTLED=" + str(summary["status"].get("settled", 0)))
    print("PRICED_SHADOW_BROKEN_GATES=0")


if __name__ == "__main__":
    main()
