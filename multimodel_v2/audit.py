"""Three independent read-only cohorts from one original pre-match freeze."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal

from .source_manifest import (
    _identity_json, build_source_manifest, identifier, instant, local_day,
    market_identity, number,
)

COHORTS = ("original_top", "qualifying_api", "fouls_under")


def _utc(value):
    return instant(value).isoformat().replace("+00:00", "Z")


def freeze_reference(snapshot):
    """Reference original publication metadata; never invent a freeze ID."""
    pub = snapshot.get("publication")
    if not isinstance(pub, dict) or pub.get("provenance") != "live_pre_match":
        raise ValueError("missing_original_freeze")
    return {"id": identifier(pub.get("id")), "run_id": identifier(snapshot.get("run_id")),
            "head_sha": snapshot["head_sha"], "artifact_name": snapshot["artifact_name"],
            "captured_at_utc": _utc(pub.get("captured_at_utc"))}


def _original_snapshot(day, runs, snapshots, cutoff):
    eligible, errors = [], []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("date") != day:
            continue
        manifest = build_source_manifest(day, runs, [snapshot], as_of=cutoff)
        errors.extend(manifest["rejections"])
        if manifest["status"] != "covered":
            continue
        try:
            freeze = freeze_reference(snapshot)
            run = next(r for r in runs if isinstance(r, dict)
                       and str(r.get("id")).strip() == freeze["run_id"])
            if not (instant(snapshot["generated_at_utc"]) <= instant(freeze["captured_at_utc"])
                    <= instant(run["updated_at"]) <= instant(cutoff)):
                raise ValueError("freeze_outside_run")
            order = (instant(freeze["captured_at_utc"]), freeze["run_id"], freeze["artifact_name"])
            eligible.append((order, snapshot, manifest, freeze))
        except ValueError as exc:
            errors.append({"reason": str(exc), "run_id": snapshot.get("run_id")})
    if not eligible:
        return None, errors + [{"reason": "no_original_freeze_for_date"}]
    eligible.sort(key=lambda item: item[0])
    first = eligible[0]
    if any(item[1] != first[1] for item in eligible[1:] if item[0] == first[0]):
        return None, errors + [{"reason": "ambiguous_original_freeze"}]
    return first[1:], errors


def _frozen_quote(raw, record):
    quote = raw.get("frozen_quote")
    if not isinstance(quote, dict) or record is None:
        return None
    try:
        identity = market_identity(quote.get("market_identity"))
        for verified in record["quotes"]:
            if (identity == market_identity(verified["market_identity"])
                    and quote.get("bookmaker") == verified["bookmaker"]
                    and number(quote.get("selected_odd")) == number(verified["selected_odd"])
                    and instant(quote.get("provider_updated_at")) == instant(verified["provider_updated_at"])):
                return deepcopy(verified)
    except ValueError:
        pass
    return None


def _quote_key(quote):
    if not isinstance(quote, dict):
        raise ValueError("missing_quote")
    return (market_identity(quote.get("market_identity")), quote.get("bookmaker"),
            number(quote.get("selected_odd")), instant(quote.get("provider_updated_at")))


def _freeze_key(freeze):
    if not isinstance(freeze, dict):
        raise ValueError("missing_freeze_reference")
    return (identifier(freeze.get("id")), identifier(freeze.get("run_id")),
            identifier(freeze.get("head_sha")), identifier(freeze.get("artifact_name")),
            instant(freeze.get("captured_at_utc")))


def _same_original(top, background):
    """Compare evidence fields, allowing harmless original display annotations."""
    try:
        return (market_identity(top) == market_identity(background)
                and instant(top.get("kickoff")) == instant(background.get("kickoff"))
                and number(top.get("final_assessment_pct")) == number(background.get("final_assessment_pct"))
                and top.get("home") == background.get("home") and top.get("away") == background.get("away"))
    except ValueError:
        return False


def _position(raw, record, freeze):
    reason = None
    try:
        identity = _identity_json(market_identity(raw))
    except ValueError:
        identity, reason = None, "invalid_original_market"
    if record is None:
        reason = reason or "unverified_original_position"
    elif instant(freeze["captured_at_utc"]) >= instant(record["kickoff"]):
        reason = "freeze_not_prematch"
    return {"market_identity": identity, "original_position": deepcopy(raw),
            "freeze": deepcopy(freeze), "record": deepcopy(record),
            "frozen_quote": _frozen_quote(raw, record),
            "validation": "unverified" if reason else "verified", "reason": reason}


def _settlement(position, settlements, day, cutoff):
    if position["validation"] != "verified":
        return None, position["reason"]
    key = market_identity(position["market_identity"])
    matching = []
    for settlement in settlements:
        if not isinstance(settlement, dict):
            continue
        try:
            if (market_identity(settlement.get("market_identity")) == key
                    and _freeze_key(settlement.get("freeze")) == _freeze_key(position["freeze"])):
                matching.append(settlement)
        except ValueError:
            continue
    if len(matching) != 1:
        return None, "missing_settlement" if not matching else "duplicate_settlement"
    result = matching[0]
    try:
        if result.get("date") != day or result.get("fixture_status") != "FT":
            raise ValueError("not_final_result_for_date")
        if result.get("outcome") not in ("win", "loss", "void", "push"):
            raise ValueError("unresolved_or_unsupported_result")
        if not isinstance(result.get("result_source"), str) or not result["result_source"].strip():
            raise ValueError("missing_result_source")
        kickoff = instant(position["record"]["kickoff"])
        if not kickoff < instant(result.get("finished_at")) <= instant(result.get("settled_at")) <= instant(cutoff):
            raise ValueError("result_outside_time_window")
        if "quote" in result and _quote_key(result["quote"]) != _quote_key(position["frozen_quote"]):
            raise ValueError("settlement_quote_mismatch")
    except ValueError as exc:
        return None, str(exc)
    return deepcopy(result), None


def _metrics(rows, complete, available):
    settled = [r for r in rows if r["settlement"] is not None]
    outcomes = Counter(r["settlement"]["outcome"] for r in settled)
    binary = outcomes["win"] + outcomes["loss"]
    fully_settled = complete and len(settled) == len(rows) and bool(rows)
    prices = all(r["frozen_quote"] is not None for r in rows)
    result = {"positions": len(rows) if available else None,
              "fixtures": len({market_identity(r["market_identity"])[0] for r in rows
                               if r["market_identity"] is not None}) if available else None,
              "settled": len(settled) if available else None,
              "unresolved": len(rows) - len(settled) if available else None,
              "wins": outcomes["win"] if available else None,
              "losses": outcomes["loss"] if available else None,
              "voids": outcomes["void"] if available else None,
              "pushes": outcomes["push"] if available else None,
              "hit_rate_pct": str(round(Decimal(100) * outcomes["win"] / binary, 6))
                  if fully_settled and binary else None,
              "roi_pct": None, "fixture_equal_roi_pct": None, "profit_units": None,
              "roi_status": "unavailable_incomplete_data"}
    if fully_settled and prices:
        by_fixture = defaultdict(list)
        for row in rows:
            outcome = row["settlement"]["outcome"]
            profit = (number(row["frozen_quote"]["selected_odd"]) - 1 if outcome == "win"
                      else Decimal(-1) if outcome == "loss" else Decimal(0))
            by_fixture[row["market_identity"]["fixture_id"]].append(profit)
        total = sum((sum(v) for v in by_fixture.values()), Decimal(0))
        equal = sum((sum(v) / len(v) for v in by_fixture.values()), Decimal(0)) / len(by_fixture)
        result.update(profit_units=str(total), roi_pct=str(round(100 * total / len(rows), 6)),
                      fixture_equal_roi_pct=str(round(100 * equal, 6)),
                      roi_status="complete_frozen_quotes_and_results")
    return result


def build_audits(report_date, runs, snapshots, settlements, *, as_of):
    """Keep cohort membership independent of results; no register/N writes.

    ROI uses ONLY an explicitly recorded frozen_quote, never a price selected
    retrospectively from available bookmakers. Unit stake per frozen position;
    void/push return the stake and contribute zero profit to that denominator.
    """
    local_day(report_date)
    instant(as_of)
    if not isinstance(settlements, list):
        raise ValueError("settlements_list_required")
    if not isinstance(runs, list) or not isinstance(snapshots, list):
        raise ValueError("source_lists_required")
    selected, errors = _original_snapshot(report_date, runs, snapshots, as_of)
    result = {"schema": "multimodel-v2-audits-v1", "date": report_date, "as_of": _utc(as_of),
              "freeze": None, "cohorts": {}, "rejections": errors}
    groups = {name: [] for name in COHORTS}
    complete = {name: selected is not None for name in COHORTS}
    available = dict(complete)
    if selected:
        snapshot, manifest, freeze = selected
        result["freeze"] = deepcopy(freeze)
        records = {market_identity(r["market_identity"]): r for r in manifest["records"]}
        background = snapshot["background_candidates"]
        for raw in background:
            try:
                record = records.get(market_identity(raw))
                score = number(raw.get("final_assessment_pct"))
                if not 0 <= score <= 100:
                    raise ValueError("invalid_api_assessment")
            except ValueError:
                complete["qualifying_api"] = False
                result["rejections"].append({"reason": "missing_or_invalid_api_assessment",
                                             "fixture_id": raw.get("fixture_id")})
                if raw.get("market") == "fouls" and raw.get("direction") == "under":
                    complete["fouls_under"] = False
                continue
            position = _position(raw, record, freeze)
            for name in ("qualifying_api", "fouls_under"):
                if name == "qualifying_api" and score < 67:
                    continue
                if name == "fouls_under" and (raw.get("market"), raw.get("direction")) != ("fouls", "under"):
                    continue
                if name == "fouls_under" and raw.get("settlement_period") != "regulation_time":
                    continue
                if position["validation"] != "verified":
                    complete[name] = False
                    result["rejections"].append({"reason": position["reason"], "cohort": name,
                                                 "market_identity": deepcopy(position["market_identity"])})
                    continue
                quotes = [q for q in record["quotes"] if (
                    number(q["selected_odd"]) >= number("1.20") if name == "qualifying_api"
                    else number("1.50") <= number(q["selected_odd"]) <= number("2.00"))]
                if quotes:
                    member = deepcopy(position)
                    if member["frozen_quote"] not in quotes:
                        member["frozen_quote"] = None
                    groups[name].append(member)
        top = snapshot.get("top_positions")
        if not isinstance(top, list) or any(not isinstance(row, dict) for row in top):
            available["original_top"] = complete["original_top"] = False
            result["rejections"].append({"reason": "missing_original_top"})
        else:
            keys = []
            for raw in top:
                try:
                    keys.append(market_identity(raw))
                except ValueError:
                    keys.append(None)
            duplicates = Counter(keys)
            for raw, key in zip(top, keys):
                position = _position(raw, records.get(key), freeze)
                # A full original TOP row is retained, never replaced/reranked
                # from the background. Divergent facts are an explicit gap.
                originals = [r for r in background if _same_original(raw, r)]
                if duplicates[key] > 1 or not originals:
                    position.update(validation="unverified", reason="top_background_mismatch_or_duplicate")
                    position["frozen_quote"] = None
                if position["validation"] != "verified":
                    complete["original_top"] = False
                groups["original_top"].append(position)

    for name, rows in groups.items():
        for row in rows:
            row["settlement"], row["settlement_reason"] = _settlement(row, settlements, report_date, as_of)
        result["cohorts"][name] = {
            "status": "source_missing" if not available[name] else "complete" if complete[name] else "incomplete",
            "rows": rows, "metrics": _metrics(rows, complete[name], available[name]),
        }
    return result
