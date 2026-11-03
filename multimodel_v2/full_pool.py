"""Optional immutable copies of native API candidate pools, without scanning.

Native payloads and TOP order stay intact except explicit secret redaction.
Copying a historical file is distinct from capturing a new prematch publication.
The only decision hook calls a supplied unchanged pure evaluator on fresh data.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .source_manifest import API_WORKFLOWS, WARSAW, identifier, instant, local_day, market_identity, number

SCHEMA = "multimodel-v2-full-pool-v1"
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
FRESH_SECONDS = 300
REDACTED = "[REDACTED]"
SOURCE_KEYS = ("run_id", "workflow_path", "workflow_head_sha", "code_checkout_sha", "raw_quote_receipts")
SECRET_KEYS = {"apikey", "apifootballkey", "pitchapiapikey", "xrapidapikey", "xapisportskey", "authorization",
               "accesstoken", "refreshtoken", "token", "password", "secret", "clientsecret"}
SECRET_ASSIGNMENT = re.compile(
    r"(?i)((?:api[_-]?key|api[_-]?football[_-]?key|pitchapi[_-]?api[_-]?key|access[_-]?token|refresh[_-]?token|token|authorization|x[-_]rapidapi[-_]key|x[-_]apisports[-_]key|secret|password)\s*[=:]\s*(?:(?:Bearer|Basic)\s+)?)([^\s&;,]+)")


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _forward_clock_guard(native, recorded_at, clock):
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("trusted_clock_timezone_required")
    observed = instant(now.isoformat())
    recorded = instant(recorded_at)
    publication = native.get("publication") if isinstance(native, dict) else None
    captured = instant(publication.get("captured_at_utc") if isinstance(publication, dict) else None)
    if not (0 <= (observed - recorded).total_seconds() <= FRESH_SECONDS
            and 0 <= (observed - captured).total_seconds() <= FRESH_SECONDS):
        raise ValueError("forward_capture_outside_trusted_clock_window")
    for row in native.get("background_candidates", []):
        if instant(row.get("kickoff")) <= observed:
            raise ValueError("forward_capture_after_kickoff")
    return observed.isoformat()


def _redact(value, *, secret_values=()):
    paths = []
    secrets = tuple(secret_values)
    if any(not isinstance(s, str) or len(s) < 8 for s in secrets):
        raise ValueError("secret_redaction_values_require_eight_characters")
    def visit(item, path):
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("non_string_native_key")
                name = re.sub(r"[^a-z0-9]", "", key.casefold())
                if name in SECRET_KEYS or name.endswith("token"):
                    result[key] = REDACTED
                    paths.append(path + "." + key)
                else:
                    result[key] = visit(child, path + "." + key)
            return result
        if isinstance(item, list):
            return [visit(child, f"{path}[{i}]") for i, child in enumerate(item)]
        if isinstance(item, str):
            result = SECRET_ASSIGNMENT.sub(lambda match: match[1] + REDACTED, item)
            result = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+", "Bearer " + REDACTED, result)
            for secret in secrets:
                result = result.replace(secret, REDACTED)
            if result != item:
                paths.append(path)
            return result
        return deepcopy(item)
    return visit(value, "native_payload"), sorted(set(paths))


def _candidate_key(row):
    canonical = deepcopy(row)
    if canonical.get("market_scope") == "match":
        canonical["team_id"] = None  # Native history anchor stays in stored raw row.
    return market_identity(canonical)


def _quote_key(quote):
    if not isinstance(quote, dict):
        raise ValueError("independent_native_quote_invalid")
    identity = market_identity(quote.get("market_identity") or {})
    bookmaker = quote.get("bookmaker")
    if not isinstance(bookmaker, str) or not bookmaker.strip():
        raise ValueError("quote_bookmaker_missing")
    price = number(quote.get("selected_odd"))
    if price <= 1:
        raise ValueError("invalid_quote_price")
    if "direction" in quote and quote["direction"] != identity[4]:
        raise ValueError("quote_direction_mismatch")
    side = identity[4] + "_odd"
    if side in quote and number(quote[side]) != price:
        raise ValueError("conflicting_quote_price")
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
    return (identity, bookmaker.strip(), price,
            instant(quote.get("provider_updated_at")), tuple(references))


def _counts(native, trace):
    bands = Counter()
    for row in native["background_candidates"]:
        try:
            bands["below_67" if number(row.get("final_assessment_pct")) < 67 else "at_least_67"] += 1
        except ValueError:
            bands["unknown"] += 1
    decisions = Counter()
    entries = trace.get("records") if isinstance(trace, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            decision = entry.get("decision")
            decisions[decision if isinstance(decision, str) and decision in ("ACCEPTED", "REJECTED") else "UNKNOWN"] += 1
    tops = native.get("top_positions")
    return {"captured_candidates": len(native["background_candidates"]),
            "native_top_positions": len(tops) if isinstance(tops, list) else None,
            "native_score_bands": dict(bands), "recorded_decisions": dict(decisions)}


def _verify(native, source, recorded_at, trace, *, mode):
    day = local_day(native.get("date"))
    recorded = instant(recorded_at)
    rows = native.get("background_candidates")
    if native.get("schema") != "api-market-scan-v3" or not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("full_candidate_pool_not_recorded")
    blockers, row_results = [], []
    def reject(reason):
        blockers.append(reason)
    declared = native.get("candidate_count", len(rows))
    full_pool = type(declared) is int and declared == len(rows)
    try:
        identifier(source.get("run_id"))
    except ValueError:
        reject("source_run_id_missing")
    if source.get("workflow_path") not in API_WORKFLOWS:
        reject("source_workflow_missing_or_wrong")
    for field in ("workflow_head_sha", "code_checkout_sha"):
        if not isinstance(source.get(field), str) or not re.fullmatch(r"[0-9a-f]{40}", source[field]):
            reject("source_" + field + "_missing_or_invalid")
    publication = native.get("publication")
    if not isinstance(publication, dict):
        publication = {}
    try:
        if publication.get("id") == REDACTED:
            raise ValueError("redacted_native_id")
        identifier(publication.get("id"))
    except ValueError:
        reject("native_publication_id_missing")
    if publication.get("provenance") != "live_pre_match":
        reject("original_prematch_provenance_missing")
    if publication.get("code_revision") != source.get("code_checkout_sha"):
        reject("native_publication_checkout_mismatch")
    try:
        captured = instant(publication.get("captured_at_utc"))
        generated = instant(native.get("generated_at_utc"))
        if not generated <= captured <= recorded:
            raise ValueError("publication_outside_capture_order")
    except ValueError as exc:
        captured = None
        reject(str(exc))
    receipts = source.get("raw_quote_receipts")
    if receipts is not None:
        if not isinstance(receipts, list) or any(not isinstance(r, dict) for r in receipts):
            reject("raw_quote_receipt_references_invalid")
        else:
            for receipt in receipts:
                try:
                    for digest in (receipt.get("envelope_sha256", receipt.get("capture_sha256")), receipt.get("response_sha256")):
                        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
                            raise ValueError("raw_quote_receipt_digest_missing")
                    if captured is None or instant(receipt.get("received_at")) > captured:
                        raise ValueError("raw_quote_receipt_after_publication")
                except ValueError as exc:
                    reject(str(exc))
    # Publication binding is shared by TOP and pool cohorts. Decisions, global
    # pool counts and unrelated rejected-row gaps must not erase original TOP.
    top_binding_blockers = list(blockers)
    if not full_pool:
        reject("declared_full_pool_count_mismatch")
    if mode == "forward":
        if captured is None or not 0 <= (recorded - captured).total_seconds() <= FRESH_SECONDS:
            raise ValueError("forward_capture_requires_fresh_original_publication")
        if day < recorded.astimezone(WARSAW).date():
            raise ValueError("forward_capture_cannot_backfill_past_report_date")
    indexed_trace = {}
    trace_stamp = None
    if isinstance(trace, dict) and isinstance(trace.get("records"), list):
        try:
            trace_stamp = instant(trace.get("recorded_at_utc"))
            if trace_stamp > recorded:
                raise ValueError("original_decision_trace_not_yet_available")
            if trace.get("origin") not in ("native_original_decision_trace", "forward_runtime_unchanged_native_evaluate"):
                raise ValueError("original_decision_trace_origin_missing")
            if not re.fullmatch(r"[0-9a-f]{64}", str(trace.get("config_sha256"))):
                raise ValueError("original_filter_config_digest_missing")
        except ValueError as exc:
            reject(str(exc))
        for entry in trace["records"]:
            if not isinstance(entry, dict) or type(entry.get("native_index")) is not int:
                reject("invalid_original_decision_trace")
                continue
            i = entry["native_index"]
            if i in indexed_trace or not 0 <= i < len(rows):
                reject("duplicate_or_outside_decision_index")
            else:
                indexed_trace[i] = entry
    else:
        reject("original_decision_trace_missing")
    identities = Counter()
    keys = []
    fixture_facts = defaultdict(lambda: defaultdict(set))
    for row in rows:
        try:
            fixture_id = identifier(row.get("fixture_id"))
        except ValueError:
            continue
        for field in ("kickoff", "home", "away", "home_id", "away_id"):
            if field not in row or row[field] is None:
                continue
            try:
                value = instant(row[field]) if field == "kickoff" else identifier(row[field])
                fixture_facts[fixture_id][field].add(value)
            except ValueError:
                pass  # The row's exact validation below supplies the gap.
    contradictory_fixtures = {fixture_id for fixture_id, facts in fixture_facts.items()
                              if any(len(values) > 1 for values in facts.values())}
    for row in rows:
        try:
            key = _candidate_key(row)
            keys.append(key)
            identities[key] += 1
        except ValueError:
            keys.append(None)
    for index, (raw, key) in enumerate(zip(rows, keys)):
        gaps, verified_quotes = [], []
        if key is None:
            gaps.append("exact_market_identity_missing")
        elif identities[key] != 1:
            gaps.append("duplicate_exact_candidate")
        if str(raw.get("fixture_id")) in contradictory_fixtures:
            gaps.append("conflicting_native_fixture_facts")
        for field in ("home_id", "away_id"):
            if field in raw:
                try:
                    identifier(raw[field])
                except ValueError:
                    gaps.append("invalid_native_" + field)
        if raw.get("settlement_period") != "regulation_time":
            gaps.append("regulation_time_missing")
        if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in ("home", "away")):
            gaps.append("native_teams_missing")
        try:
            ko = instant(raw.get("kickoff"))
            if ko.astimezone(WARSAW).date() != day:
                gaps.append("kickoff_warsaw_date_mismatch")
            if captured is None or captured >= ko:
                gaps.append("original_freeze_not_prematch")
            if mode == "forward" and recorded >= ko:
                raise ValueError("forward_capture_after_kickoff")
        except ValueError as exc:
            if str(exc) == "forward_capture_after_kickoff":
                raise
            ko = None
            gaps.append("native_kickoff_missing_or_invalid")
        try:
            score = number(raw.get("final_assessment_pct"))
            if not 0 <= score <= 100:
                raise ValueError("score_outside_range")
        except ValueError:
            gaps.append("native_api_assessment_missing_or_invalid")
        market_data = raw.get("market_data")
        quotes = market_data.get("quotes") if isinstance(market_data, dict) else None
        decision = indexed_trace.get(index)
        reasons = decision.get("rejection_reasons") if isinstance(decision, dict) else None
        known_no_offer = (quotes == [] and isinstance(decision, dict) and decision.get("decision") == "REJECTED"
                          and isinstance(reasons, list) and bool(reasons)
                          and all(isinstance(reason, str) and reason.strip() for reason in reasons))
        if not isinstance(quotes, list) or (not quotes and not known_no_offer):
            gaps.append("independent_native_quotes_missing")
        else:
            for quote in quotes:
                try:
                    if not isinstance(quote, dict):
                        raise ValueError("invalid_quote")
                    quote_key = _quote_key(quote)
                    if quote_key[0] != key:
                        raise ValueError("quote_exact_market_mismatch")
                    if quote_key[2] <= 1:
                        raise ValueError("invalid_quote_price")
                    if captured is None or ko is None or not quote_key[3] <= captured < ko:
                        raise ValueError("quote_or_freeze_lookahead")
                    if "direction" in quote and quote["direction"] != raw.get("direction"):
                        raise ValueError("quote_direction_mismatch")
                    verified_quotes.append(quote_key)
                except ValueError as exc:
                    gaps.append(str(exc))
        if decision is None:
            gaps.append("original_candidate_decision_missing")
        else:
            if trace_stamp is None or ko is None or trace_stamp >= ko:
                gaps.append("original_decision_trace_not_prematch")
            reasons = decision.get("rejection_reasons")
            if (decision.get("decision") not in ("ACCEPTED", "REJECTED")
                    or not isinstance(reasons, list) or any(not isinstance(x, str) or not x.strip() for x in reasons)
                    or (decision["decision"] == "REJECTED" and not reasons)
                    or (decision["decision"] == "ACCEPTED" and reasons)):
                gaps.append("original_candidate_decision_invalid")
            if decision.get("retained_row_sha256", decision.get("row_sha256")) != _sha(raw):
                gaps.append("decision_row_digest_mismatch")
        row_results.append({"native_index": index, "row_sha256": _sha(raw),
                            "blockers": sorted(set(gaps)), "verified_quotes": len(verified_quotes),
                            "known_no_offer": known_no_offer})
    tops = native.get("top_positions")
    top_blockers = list(top_binding_blockers)
    def reject_top(reason):
        top_blockers.append(reason)
        reject(reason)
    if not isinstance(tops, list) or any(not isinstance(t, dict) for t in tops):
        reject_top("original_top_missing")
    else:
        seen = set()
        for top in tops:
            try:
                key = _candidate_key(top)
                matching = [r for r, candidate_key in zip(rows, keys) if candidate_key == key]
                if key in seen or len(matching) != 1:
                    raise ValueError("top_candidate_missing_or_ambiguous")
                seen.add(key)
                row = matching[0]
                if key[0] in contradictory_fixtures:
                    raise ValueError("conflicting_native_fixture_facts")
                if top.get("settlement_period") != "regulation_time":
                    raise ValueError("top_regulation_time_missing")
                if any(not isinstance(top.get(k), str) or not top[k].strip() for k in ("home", "away")):
                    raise ValueError("top_native_teams_missing")
                for field in ("home_id", "away_id"):
                    if top.get(field) is not None:
                        identifier(top[field])
                    if row.get(field) is not None:
                        identifier(row[field])
                side = top.get("team_side")
                if top.get("market_scope") == "team" and side is not None:
                    if side not in ("home", "away"):
                        raise ValueError("top_native_team_side_invalid")
                    if top.get(side + "_id") is not None and identifier(top["team_id"]) != identifier(top[side + "_id"]):
                        raise ValueError("top_native_team_side_identity_mismatch")
                kickoff = instant(top.get("kickoff"))
                if kickoff.astimezone(WARSAW).date() != day or captured is None or captured >= kickoff:
                    raise ValueError("top_native_freeze_or_date_invalid")
                if not 0 <= number(top.get("final_assessment_pct")) <= 100:
                    raise ValueError("top_native_api_assessment_invalid")
                if any(row.get(k) != top.get(k) for k in ("kickoff", "home", "away", "final_assessment_pct")):
                    raise ValueError("top_candidate_facts_mismatch")
                if any(k in row and k in top and row[k] != top[k] for k in ("home_id", "away_id")):
                    raise ValueError("top_candidate_native_team_id_mismatch")
                frozen = top.get("frozen_quote")
                if not isinstance(frozen, dict):
                    raise ValueError("original_top_frozen_quote_missing")
                frozen_key = _quote_key(frozen)
                if frozen_key[0] != key or frozen_key[2] <= 1 or not frozen_key[3] <= captured < kickoff:
                    raise ValueError("original_top_frozen_quote_invalid")
                background_quotes = row.get("market_data")
                background_quotes = background_quotes.get("quotes") if isinstance(background_quotes, dict) else None
                if not isinstance(background_quotes, list):
                    raise ValueError("original_top_independent_background_quotes_missing")
                matching_quotes = []
                for quote in background_quotes:
                    try:
                        candidate_quote = _quote_key(quote)
                    except ValueError:
                        continue
                    if candidate_quote == frozen_key:
                        matching_quotes.append(candidate_quote)
                if len(matching_quotes) != 1:
                    raise ValueError("original_top_frozen_quote_mismatch")
                own_quotes = top.get("market_data")
                own_quotes = own_quotes.get("quotes") if isinstance(own_quotes, dict) else None
                if own_quotes is not None:
                    if not isinstance(own_quotes, list) or sum(_quote_key(q) == frozen_key for q in own_quotes) != 1:
                        raise ValueError("original_top_own_quote_mismatch")
            except (ValueError, AttributeError) as exc:
                reject_top(str(exc))
    blockers.extend(g for r in row_results for g in r["blockers"])
    return {"status": "COMPLETE" if full_pool and not blockers else "INCOMPLETE",
            "full_pool_complete": full_pool, "source_eligible": full_pool and not blockers,
            "original_top_eligible": not top_blockers, "original_top_blockers": sorted(set(top_blockers)),
            "blockers": sorted(set(blockers)), "rows": row_results,
            "verified_candidate_rows": sum(not r["blockers"] for r in row_results)}


def build_full_pool(capture, source, *, recorded_at, mode="copy_original", candidate_decisions=None,
                    retention_days=30, max_bytes=DEFAULT_MAX_BYTES, secret_values=(), clock=None):
    """Copy native evidence; historical copies never acquire new decision traces.

    source records workflow head and actual code checkout separately. FULL pool
    preservation and strict source eligibility are independent verification flags.
    """
    if mode not in ("copy_original", "forward"):
        raise ValueError("unknown_full_pool_capture_mode")
    if not isinstance(source, dict):
        raise ValueError("source_metadata_required")
    if type(retention_days) is not int or not 1 <= retention_days <= 90:
        raise ValueError("retention_days_outside_1_90")
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("full_pool_size_limit_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(capture.get("capture_sha256"))):
        raise ValueError("original_capture_digest_required")
    original = capture.get("payload")
    if not isinstance(original, dict):
        raise ValueError("native_payload_required")
    if len(_bytes(original)) > max_bytes:
        raise ValueError("full_pool_size_limit_exceeded")
    observed = _forward_clock_guard(original, recorded_at, clock) if mode == "forward" else None
    if mode == "copy_original" and candidate_decisions is not None:
        raise ValueError("no_new_historical_decision_trace")
    trace = deepcopy(original.get("candidate_decisions") if candidate_decisions is None else candidate_decisions)
    if isinstance(trace, dict) and isinstance(trace.get("records"), list):
        for entry in trace["records"]:
            index = entry.get("native_index") if isinstance(entry, dict) else None
            if (type(index) is int and 0 <= index < len(original.get("background_candidates", []))
                    and entry.get("row_sha256") != _sha(original["background_candidates"][index])):
                raise ValueError("original_decision_row_digest_mismatch")
    native, redactions = _redact(original, secret_values=secret_values)
    clean_trace, trace_redactions = _redact(trace, secret_values=secret_values)
    # Keep original trace hashes intact; a separate technical retained digest
    # binds any secret-redacted row bytes without changing native decisions.
    if isinstance(clean_trace, dict) and isinstance(clean_trace.get("records"), list):
        for entry in clean_trace["records"]:
            i = entry.get("native_index") if isinstance(entry, dict) else None
            if type(i) is int and 0 <= i < len(native.get("background_candidates", [])):
                entry["retained_row_sha256"] = _sha(native["background_candidates"][i])
    clean_source, source_redactions = _redact({k: deepcopy(source.get(k)) for k in SOURCE_KEYS}, secret_values=secret_values)
    verification = _verify(native, clean_source, recorded_at, clean_trace, mode=mode)
    envelope = {"schema": SCHEMA, "date": native["date"], "capture_mode": mode,
                "recorded_at_utc": recorded_at,
                "trusted_clock_observed_at_utc": observed,
                "expires_at_utc": (instant(recorded_at) + timedelta(days=retention_days)).isoformat(),
                "retention_days": retention_days, "max_bytes": max_bytes,
                "source": clean_source, "native_payload": native, "candidate_decisions": clean_trace,
                "verification": verification,
                "counts": _counts(native, clean_trace),
                "preservation": {"original_capture_sha256": capture["capture_sha256"],
                                 "original_payload_sha256": _sha(original), "retained_payload_sha256": _sha(native),
                                 "top_order_preserved": True, "native_fields_synthesized": False,
                                 "secret_redaction_paths": redactions + ["decision_trace:" + p for p in trace_redactions]
                                 + ["source:" + p for p in source_redactions]},
                "fresh_predictions_created": 0, "register_writes": False, "n_effect": 0}
    envelope["content_sha256"] = _sha(envelope)
    if len(_bytes(envelope)) > max_bytes:
        raise ValueError("full_pool_size_limit_exceeded")
    return envelope


def capture_full_pool(capture, source, *, recorded_at, evaluator, decision_config, clock=None, **options):
    """Future scan hook: trace the unchanged pure filter while still prematch.

    The supplied callable must have the native evaluate(payload, cfg) signature.
    It receives copies and never triggers scanner/provider calls in this module.
    """
    if not callable(evaluator) or not isinstance(decision_config, dict):
        raise ValueError("original_pure_evaluator_and_config_required")
    native = capture.get("payload") or {}
    _forward_clock_guard(native, recorded_at, clock)
    # Fail before invoking the filter if somebody tries to reconstruct old
    # decisions from an historical file or invokes it after any kickoff.
    _verify(native, {k: source.get(k) for k in SOURCE_KEYS}, recorded_at, None, mode="forward")
    records = []
    for i, row in enumerate(native["background_candidates"]):
        accepted, reasons = evaluator({"background_candidates": [deepcopy(row)]}, deepcopy(decision_config))
        if not isinstance(accepted, list) or not isinstance(reasons, dict):
            raise ValueError("original_evaluator_result_invalid")
        if len(accepted) == 1 and not reasons:
            state, codes = "ACCEPTED", []
        elif not accepted and len(reasons) == 1 and list(reasons.values()) == [1]:
            state, codes = "REJECTED", list(reasons)
        else:
            raise ValueError("original_evaluator_decision_ambiguous")
        records.append({"native_index": i, "row_sha256": _sha(row), "decision": state, "rejection_reasons": codes})
    trace = {"origin": "forward_runtime_unchanged_native_evaluate", "recorded_at_utc": recorded_at,
             "config_sha256": _sha(decision_config),
             "filter_callable": getattr(evaluator, "__module__", type(evaluator).__module__) + "."
                                + getattr(evaluator, "__qualname__", type(evaluator).__qualname__),
             "records": records}
    return build_full_pool(capture, source, recorded_at=recorded_at, mode="forward",
                           candidate_decisions=trace, clock=clock, **options)


def verify_full_pool(envelope, *, as_of):
    """Recompute digests and evidence; never trust stored COMPLETE flags."""
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA:
        raise ValueError("unsupported_full_pool_schema")
    body = {k: v for k, v in envelope.items() if k != "content_sha256"}
    if _sha(body) != envelope.get("content_sha256"):
        raise ValueError("full_pool_digest_mismatch")
    limit = envelope.get("max_bytes")
    if type(limit) is not int or not 1 <= limit <= MAX_BYTES or len(_bytes(envelope)) > limit:
        raise ValueError("full_pool_size_limit_exceeded")
    recorded, now = instant(envelope.get("recorded_at_utc")), instant(as_of)
    retention = envelope.get("retention_days")
    if type(retention) is not int or not 1 <= retention <= 90:
        raise ValueError("retention_days_outside_1_90")
    if instant(envelope.get("expires_at_utc")) != recorded + timedelta(days=retention):
        raise ValueError("full_pool_retention_tampered")
    if envelope.get("capture_mode") not in ("copy_original", "forward"):
        raise ValueError("unknown_full_pool_capture_mode")
    if envelope["capture_mode"] == "forward":
        _forward_clock_guard(envelope.get("native_payload"), envelope["recorded_at_utc"],
                             lambda: instant(envelope.get("trusted_clock_observed_at_utc")))
    if not recorded <= now <= instant(envelope.get("expires_at_utc")):
        raise ValueError("full_pool_not_available_or_expired")
    if envelope.get("date") != envelope.get("native_payload", {}).get("date"):
        raise ValueError("full_pool_date_mismatch")
    if _sha(envelope["native_payload"]) != envelope.get("preservation", {}).get("retained_payload_sha256"):
        raise ValueError("full_pool_retained_payload_mismatch")
    preservation = envelope.get("preservation", {})
    if (preservation.get("native_fields_synthesized") is not False or preservation.get("top_order_preserved") is not True
            or (not preservation.get("secret_redaction_paths") and preservation.get("original_payload_sha256") != preservation.get("retained_payload_sha256"))):
        raise ValueError("full_pool_preservation_claim_invalid")
    verified = _verify(envelope["native_payload"], envelope["source"], envelope["recorded_at_utc"],
                       envelope.get("candidate_decisions"), mode=envelope["capture_mode"])
    if verified != envelope.get("verification"):
        raise ValueError("full_pool_verification_tampered")
    if _counts(envelope["native_payload"], envelope.get("candidate_decisions")) != envelope.get("counts"):
        raise ValueError("full_pool_counts_tampered")
    return verified


def write_full_pool(envelope, output_root):
    """Publish once to a new isolated date/native-ID partition; never prune."""
    verify_full_pool(envelope, as_of=envelope["recorded_at_utc"])
    output = Path(output_root).resolve()
    root = Path(__file__).resolve().parents[1]
    protected = [(root / name).resolve() for name in (".git", "archive", "data", "reports", "model", "config", "tools", ".github")]
    if output == root or root in output.parents or any(output == path or path in output.parents for path in protected):
        raise ValueError("protected_production_output_path")
    native_id = (envelope["native_payload"].get("publication") or {}).get("id")
    filename = native_id if isinstance(native_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", native_id) else "unidentified-" + envelope["preservation"]["original_capture_sha256"]
    directory = output / envelope["date"]
    if directory.is_symlink() or not directory.resolve().is_relative_to(output):
        raise ValueError("symlinked_full_pool_date_partition")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (filename + ".json")
    raw = _bytes(envelope)
    with tempfile.NamedTemporaryFile(prefix=".pool-", dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, target)  # Atomic and refuses existing targets.
        finally:
            temporary.unlink(missing_ok=True)
    return target


def read_full_pool(path, *, as_of):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("full_pool_size_limit_exceeded")
    envelope = json.loads(path.read_bytes())
    verify_full_pool(envelope, as_of=as_of)
    return envelope
