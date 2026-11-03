"""Read-only settlement linkage for one original native API publication.

No result, price, publication ID, cohort or observation is reconstructed from
another freeze. This module does not call providers, write files or update N.
The caller verifies the immutable source/export receipt before passing an
explicit full-pool completeness declaration.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import json

from .source_manifest import WARSAW, _identity_json, identifier, instant, local_day, market_identity, number

COHORTS = ("original_top", "qualifying_api", "fouls_under")
STATES = frozenset({"WIN", "LOSS", "VOID", "UNRESOLVED"})


def _candidate_key(row):
    canonical = deepcopy(row)
    # A native match-total row may retain a technical history-team anchor.
    # Independent quote identities are validated without this normalization.
    if canonical.get("market_scope") == "match":
        canonical["team_id"] = None
    return market_identity(canonical)


def _quote_key(quote):
    if not isinstance(quote, dict):
        raise ValueError("original_quote_missing")
    key = market_identity(quote.get("market_identity"))
    book = quote.get("bookmaker")
    if not isinstance(book, str) or not book.strip():
        raise ValueError("quote_bookmaker_missing")
    price = number(quote.get("selected_odd"))
    if price <= 1:
        raise ValueError("quote_odds_invalid")
    stamp = instant(quote.get("provider_updated_at"))
    if "direction" in quote and quote["direction"] != key[4]:
        raise ValueError("quote_direction_mismatch")
    if quote.get(key[4] + "_odd") is not None and number(quote[key[4] + "_odd"]) != price:
        raise ValueError("quote_side_price_mismatch")
    references = []
    for field in ("quote_id", "provider_quote_id", "source_id", "source_reference"):
        if field not in quote:
            continue
        value = quote[field]
        try:
            if isinstance(value, dict) and value:
                encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
            else:
                encoded = identifier(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_quote_source_reference") from exc
        references.append((field, encoded))
    return key, book.strip(), price, stamp, tuple(references)


def _native_id(outcome):
    values = [identifier(outcome[k]) for k in ("publication_id", "prediction_id") if k in outcome]
    if not values:
        raise ValueError("outcome_native_publication_id_missing")
    if len(set(values)) != 1:
        raise ValueError("outcome_publication_ids_conflict")
    return values[0]


def _position(row, captured, day, *, independent_quotes=None):
    errors, quotes = [], []
    key = None
    score = None
    kickoff = None
    frozen = None
    try:
        key = _candidate_key(row)
    except ValueError as exc:
        errors.append(str(exc))
    if not all(isinstance(row.get(field), str) and row[field].strip() for field in ("home", "away")):
        errors.append("native_fixture_teams_missing")
    for field in ("home_id", "away_id"):
        if row.get(field) is not None:
            try:
                identifier(row[field])
            except ValueError:
                errors.append("native_fixture_team_id_invalid")
    side = row.get("team_side")
    if row.get("market_scope") == "team" and side is not None:
        if side not in ("home", "away"):
            errors.append("native_team_side_invalid")
        elif row.get(side + "_id") is not None:
            try:
                if identifier(row.get("team_id")) != identifier(row[side + "_id"]):
                    errors.append("native_team_side_identity_mismatch")
            except ValueError:
                errors.append("native_fixture_team_id_invalid")
    try:
        score = number(row.get("final_assessment_pct"))
        if not 0 <= score <= 100:
            raise ValueError("invalid_api_assessment")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        kickoff = instant(row.get("kickoff"))
        if kickoff.astimezone(WARSAW).date().isoformat() != day:
            raise ValueError("candidate_event_date_mismatch")
        if captured is None or captured >= kickoff:
            raise ValueError("original_freeze_not_prematch")
    except ValueError as exc:
        errors.append(str(exc))
    native_quotes = (row.get("market_data") or {}).get("quotes") if isinstance(row.get("market_data"), dict) else None
    if native_quotes is None and independent_quotes is not None:
        # Native TOP may record only its explicit selected quote. Verify it
        # against the original background universe without adding source fields.
        native_quotes = independent_quotes
    if not isinstance(native_quotes, list):
        errors.append("independent_quotes_missing")
    else:
        seen = set()
        for quote in native_quotes:
            try:
                qkey = _quote_key(quote)
                if qkey[0] != key:
                    raise ValueError("independent_quote_market_mismatch")
                if captured is None or kickoff is None or not qkey[3] <= captured < kickoff:
                    raise ValueError("quote_or_freeze_lookahead")
                if qkey in seen:
                    raise ValueError("duplicate_independent_quote")
                seen.add(qkey)
                quotes.append(qkey)
            except ValueError as exc:
                errors.append(str(exc))
    population_errors = sorted(set(errors))
    try:
        frozen = _quote_key(row.get("frozen_quote"))
        if frozen not in quotes:
            raise ValueError("frozen_quote_not_in_original_quotes")
    except ValueError as exc:
        frozen = None
        errors.append(str(exc))
    return {"original_position": deepcopy(row), "market_identity": _identity_json(key) if key else None,
            "key": key, "score": score, "kickoff": kickoff, "quotes": quotes, "frozen_key": frozen,
            "population_errors": population_errors,
            "source_errors": sorted(set(errors)), "state": "UNRESOLVED", "settlement": None,
            "settlement_reason": "missing_native_settlement"}


def _metrics(rows, *, population_complete, source_ready):
    states = Counter(row["state"] for row in rows)
    final = states["WIN"] + states["LOSS"] + states["VOID"]
    financial_complete = source_ready and bool(rows) and final == len(rows)
    result = {"positions": len(rows) if population_complete else None, "known_positions": len(rows),
              "fixtures": len({r["market_identity"]["fixture_id"] for r in rows if r["market_identity"]}) if population_complete else None,
              "settled": final, "unresolved": len(rows) - final,
              "wins": states["WIN"], "losses": states["LOSS"], "voids": states["VOID"],
              "hit_rate_pct": None, "profit_units": None, "roi_pct": None, "fixture_equal_roi_pct": None,
              "roi_status": "AUDYT NIEPEŁNY"}
    if financial_complete:
        groups = defaultdict(list)
        for row in rows:
            profit = (row["frozen_key"][2] - 1 if row["state"] == "WIN" else
                      Decimal(-1) if row["state"] == "LOSS" else Decimal(0))
            groups[row["market_identity"]["fixture_id"]].append(profit)
        profit = sum((sum(values) for values in groups.values()), Decimal(0))
        equal = sum((sum(values) / len(values) for values in groups.values()), Decimal(0)) / len(groups)
        binary = states["WIN"] + states["LOSS"]
        result.update(profit_units=str(profit), roi_pct=str(round(100 * profit / len(rows), 6)),
                      fixture_equal_roi_pct=str(round(100 * equal, 6)),
                      hit_rate_pct=str(round(Decimal(100) * states["WIN"] / binary, 6)) if binary else None,
                      roi_status="COMPLETE_NATIVE_FROZEN_COHORT")
    elif source_ready and not rows:
        result["roi_status"] = "EMPTY_COMPLETE_COHORT_NO_DENOMINATOR"
    return result


def build_native_settlements(snapshot, outcomes, *, as_of, report_date=None,
                             full_pool_complete=None, full_pool_verification=None):
    """Audit one native freeze without updating archives or official counters.

    Outcomes must repeat the original publication/prediction ID, exact market
    and frozen quote. FT outcomes need original result_source, finished_at and
    settled_at. Cancellation VOID requires a native decision reference and
    reason; no inference from status, scores, hit flags or another publication.
    A verified export may declare full_pool_complete externally; it never adds
    that field to the native payload. Missing/partial pools do not prove zero.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("native_snapshot_required")
    if isinstance(outcomes, dict):
        outcomes = outcomes.get("observations")
    if not isinstance(outcomes, list):
        raise ValueError("native_outcome_list_required")
    if full_pool_complete is not None and type(full_pool_complete) is not bool:
        raise ValueError("explicit_pool_completeness_required")
    if full_pool_verification is not None and not isinstance(full_pool_verification, dict):
        raise ValueError("invalid_pool_verification")
    cutoff = instant(as_of)
    root_errors = []
    try:
        day = local_day(report_date if report_date is not None else snapshot.get("date")).isoformat()
        if snapshot.get("date") != day:
            raise ValueError("native_publication_date_mismatch")
    except ValueError as exc:
        day = report_date
        root_errors.append(str(exc))
    publication = snapshot.get("publication")
    native_id = None
    captured = None
    try:
        if not isinstance(publication, dict) or publication.get("provenance") != "live_pre_match":
            raise ValueError("original_native_publication_missing")
        native_id = identifier(publication.get("id"))
        captured = instant(publication.get("captured_at_utc"))
        if captured > cutoff:
            raise ValueError("publication_after_audit_cutoff")
        if "generated_at_utc" in snapshot and instant(snapshot["generated_at_utc"]) > captured:
            raise ValueError("publication_before_generation")
    except ValueError as exc:
        root_errors.append(str(exc))
    if snapshot.get("schema") != "api-market-scan-v3":
        root_errors.append("full_native_publication_schema_missing")
    background = snapshot.get("background_candidates")
    if not isinstance(background, list) or any(not isinstance(row, dict) for row in background):
        background = []
        root_errors.append("native_background_missing")
    declared_pool = full_pool_complete is True
    external_source_ready = True
    external_top_ready = True
    pool_errors = []
    if full_pool_verification is not None:
        declaration = full_pool_verification.get("full_pool_complete") is True
        declared_pool = declaration if full_pool_complete is None else declared_pool and declaration
        external_source_ready = (full_pool_verification.get("status") == "COMPLETE"
                                 and full_pool_verification.get("source_eligible") is True)
        external_top_ready = full_pool_verification.get("original_top_eligible") is True
    if "candidate_count" in snapshot and (type(snapshot["candidate_count"]) is not int or snapshot["candidate_count"] != len(background)):
        declared_pool = False
        pool_errors.append("native_candidate_count_mismatch")
    positions = [_position(row, captured, day) for row in background]
    counts = Counter(p["key"] for p in positions if p["key"] is not None)
    fixture_facts = defaultdict(lambda: defaultdict(set))
    for position in positions:
        if position["key"] is None:
            continue
        facts = fixture_facts[position["key"][0]]
        if position["kickoff"] is not None:
            facts["kickoff"].add(position["kickoff"])
        raw = position["original_position"]
        for field in ("home", "away"):
            if isinstance(raw.get(field), str) and raw[field].strip():
                facts[field].add(raw[field])
        for field in ("home_id", "away_id"):
            if raw.get(field) is not None:
                try:
                    facts[field].add(identifier(raw[field]))
                except ValueError:
                    pass  # Detailed row rejection is retained by _position.
    fixture_conflicts = {fixture for fixture, fields in fixture_facts.items()
                         if any(len(values) > 1 for values in fields.values())}
    by_key = defaultdict(list)
    for position in positions:
        if position["key"] is not None:
            by_key[position["key"]].append(position)
            if position["key"][0] in fixture_conflicts:
                position["source_errors"].append("conflicting_native_fixture_facts")
                position["population_errors"].append("conflicting_native_fixture_facts")
            if counts[position["key"]] > 1:
                position["source_errors"].append("duplicate_native_candidate")
                position["population_errors"].append("duplicate_native_candidate")
    native_top = snapshot.get("top_positions")
    top_frozen_keys = defaultdict(set)
    for raw in native_top if isinstance(native_top, list) else []:
        try:
            key = _candidate_key(raw)
            selected = _quote_key(raw.get("frozen_quote"))
            originals = by_key.get(key, [])
            if selected[0] == key and len(originals) == 1 and selected in originals[0]["quotes"]:
                top_frozen_keys[key].add(selected)
        except (ValueError, AttributeError):
            pass  # Native TOP row errors are emitted when preserving the row.
    rejections, indexed = [], defaultdict(list)
    for index, outcome in enumerate(outcomes):
        try:
            if not isinstance(outcome, dict):
                raise ValueError("invalid_native_outcome")
            if _native_id(outcome) != native_id or native_id is None:
                raise ValueError("wrong_native_publication_id")
            key = market_identity(outcome.get("market_identity"))
            frozen = _quote_key(outcome.get("frozen_quote"))
            if frozen[0] != key:
                raise ValueError("outcome_quote_market_mismatch")
            if key not in by_key:
                raise ValueError("outcome_market_not_in_native_pool")
            if (not any(position["frozen_key"] == frozen for position in by_key[key])
                    and frozen not in top_frozen_keys[key]):
                raise ValueError("outcome_frozen_quote_mismatch")
            if not isinstance(outcome.get("outcome"), str) or outcome["outcome"] not in STATES:
                raise ValueError("unsupported_native_outcome")
            indexed[(key, frozen)].append((index, deepcopy(outcome)))
        except ValueError as exc:
            rejection = {"outcome_index": index, "reason": str(exc)}
            if rejection not in rejections:
                rejections.append(rejection)

    def resolve(position, *, source_verified):
        if root_errors or not source_verified or position["source_errors"] or position["frozen_key"] is None:
            position["settlement_reason"] = "native_source_incomplete"
            return
        matches = indexed.get((position["key"], position["frozen_key"]), [])
        if len(matches) != 1:
            position["settlement_reason"] = "duplicate_native_settlement" if matches else "missing_exact_native_settlement"
            return
        index, outcome = matches[0]
        try:
            if outcome.get("date") != day:
                raise ValueError("settlement_event_date_mismatch")
            if outcome["outcome"] == "UNRESOLVED":
                position["settlement_reason"] = "native_result_unresolved"
                return
            if not isinstance(outcome.get("result_source"), str) or not outcome["result_source"].strip():
                raise ValueError("native_result_source_missing")
            if outcome["outcome"] == "VOID" and outcome.get("fixture_status") in ("CANC", "ABD", "PST"):
                if (not isinstance(outcome.get("void_reason"), str) or not outcome["void_reason"].strip()
                        or not isinstance(outcome.get("settlement_reference"), str)
                        or not outcome["settlement_reference"].strip()):
                    raise ValueError("explicit_native_void_decision_missing")
                if captured is None or not captured <= instant(outcome.get("settled_at")) <= cutoff:
                    raise ValueError("native_void_outside_time_window")
            else:
                if outcome.get("fixture_status") != "FT":
                    raise ValueError("native_result_not_final")
                if outcome.get("time_basis") == "official_final_status_observation":
                    from .outcome_bridge import final_fixture
                    receipt = outcome.get("final_status_receipt")
                    final_fixture(receipt, fixture_id=position["key"][0],
                                  kickoff=position["kickoff"].isoformat(), as_of=as_of)
                    if outcome.get("finished_at") is not None or outcome.get("final_observed_at") != receipt["received_at"]:
                        raise ValueError("native_final_observation_binding_mismatch")
                    from .capture import verify_provider_capture
                    statistics = outcome.get("statistics_receipt")
                    verify_provider_capture(statistics, as_of=as_of)
                    response = statistics["response"]
                    if (statistics["provider"] != "API-Football" or statistics["endpoint"] != "fixtures/statistics"
                            or statistics["source"] != receipt["source"] or not isinstance(response, dict)
                            or response.get("errors") or not isinstance(response.get("parameters"), dict)
                            or str(response["parameters"].get("fixture")) != position["key"][0]
                            or statistics["received_at"] != outcome.get("settled_at")
                            or instant(statistics["requested_at"]) < instant(receipt["received_at"])):
                        raise ValueError("native_statistics_observation_binding_mismatch")
                    final_at = instant(outcome["final_observed_at"])
                else:
                    final_at = instant(outcome.get("finished_at"))
                if not position["kickoff"] < final_at <= instant(outcome.get("settled_at")) <= cutoff:
                    raise ValueError("native_result_outside_time_window")
            if "kickoff" in outcome and instant(outcome["kickoff"]) != position["kickoff"]:
                raise ValueError("settlement_kickoff_mismatch")
        except ValueError as exc:
            position["settlement_reason"] = str(exc)
            rejection = {"outcome_index": index, "reason": str(exc)}
            if rejection not in rejections:
                rejections.append(rejection)
            return
        position.update(state=outcome["outcome"], settlement=deepcopy(outcome), settlement_reason=None)

    groups = {name: [] for name in COHORTS}
    complete = {"original_top": isinstance(snapshot.get("top_positions"), list),
                "qualifying_api": declared_pool, "fouls_under": declared_pool}
    for position in positions:
        key, score = position["key"], position["score"]
        if key is None or score is None:
            complete["qualifying_api"] = complete["fouls_under"] = False
            continue
        for name, belongs, threshold in (
                ("qualifying_api", score >= 67, lambda price: price >= number("1.20")),
                ("fouls_under", key[1] == "fouls" and key[4] == "under" and key[6] == "regulation_time",
                 lambda price: number("1.50") <= price <= number("2.00"))):
            if not belongs:
                continue
            if position["population_errors"]:
                complete[name] = False
            if any(threshold(q[2]) for q in position["quotes"]):
                member = deepcopy(position)
                if member["frozen_key"] is not None and not threshold(member["frozen_key"][2]):
                    member["source_errors"].append("frozen_quote_outside_cohort_band")
                groups[name].append(member)
    top = native_top
    if isinstance(top, list):
        top_keys = []
        for raw in top:
            try:
                top_keys.append(_candidate_key(raw) if isinstance(raw, dict) else None)
            except ValueError:
                top_keys.append(None)
        duplicates = Counter(top_keys)
        for raw, key in zip(top, top_keys):
            if not isinstance(raw, dict):
                raw = {"invalid_native_top_value": deepcopy(raw)}
            originals = by_key.get(key, [])
            background_quotes = ((originals[0]["original_position"].get("market_data") or {}).get("quotes")
                                 if len(originals) == 1 else None)
            position = _position(raw, captured, day, independent_quotes=background_quotes)
            if key is not None and key[0] in fixture_conflicts:
                position["source_errors"].append("conflicting_native_fixture_facts")
                complete["original_top"] = False
            optional_ids_match = True
            if len(originals) == 1:
                for field in ("home_id", "away_id"):
                    if raw.get(field) is not None and originals[0]["original_position"].get(field) is not None:
                        try:
                            optional_ids_match = optional_ids_match and identifier(raw[field]) == identifier(originals[0]["original_position"][field])
                        except ValueError:
                            optional_ids_match = False
            if (len(originals) != 1 or duplicates[key] != 1 or any(
                    position["original_position"].get(field) != originals[0]["original_position"].get(field)
                    for field in ("home", "away", "kickoff", "final_assessment_pct"))
                    or not optional_ids_match
                    or position["frozen_key"] not in (originals[0]["quotes"] if originals else [])):
                position["source_errors"].append("original_top_pool_mismatch_or_duplicate")
            groups["original_top"].append(position)
    cohorts = {}
    for name, rows in groups.items():
        source_verified = external_top_ready if name == "original_top" else external_source_ready
        ready = complete[name] and not root_errors and source_verified and all(not row["source_errors"] for row in rows)
        for row in rows:
            resolve(row, source_verified=source_verified)
        metrics = _metrics(rows, population_complete=complete[name] and not root_errors, source_ready=ready)
        resolved = ready and all(row["state"] != "UNRESOLVED" for row in rows)
        output = []
        for row in rows:
            output.append({key: deepcopy(value) for key, value in row.items() if key not in (
                "key", "score", "kickoff", "quotes", "frozen_key")})
        cohorts[name] = {"status": "COMPLETE" if resolved else "AUDYT NIEPEŁNY",
                         "source_status": "READY" if ready else "SOURCE_BLOCKED",
                         "population_complete": complete[name] and not root_errors,
                         "blockers": sorted({error for row in rows for error in row["source_errors"]}
                                            | {row["settlement_reason"] for row in rows if row["settlement_reason"]}
                                            | (set() if complete[name] else {"cohort_population_not_verified"})),
                         "rows": output, "metrics": metrics}
    blockers = root_errors + pool_errors + ([] if external_source_ready else ["full_pool_source_verification_incomplete"])
    if not external_top_ready:
        blockers.append("original_top_source_verification_incomplete")
    if not declared_pool:
        blockers.append("full_pool_completeness_not_verified")
    if not isinstance(top, list):
        blockers.append("original_top_missing")
    return {"schema": "multimodel-v2-native-settlement-v1", "native_publication_id": native_id,
            "date": day, "as_of": as_of, "full_pool_declared_complete": declared_pool,
            "status": "READY" if all(c["status"] == "COMPLETE" for c in cohorts.values()) else "SOURCE_BLOCKED",
            "cohorts": cohorts, "source_blockers": sorted(set(blockers)), "rejections": rejections,
            "conflicting_fixture_ids": sorted(fixture_conflicts),
            "outcomes_received": len(outcomes), "register_writes": False, "n_effect": 0,
            "source_algorithms_called": False}
