"""Verify original KB21/Consensus freezes and record future native publications.

No network, model execution, Google writes, source archive repair or N writes.
The publisher only records a supplied native envelope; it never creates picks,
publication IDs, prices, exact markets or model values.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, time, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .adapters import adapt_sheet
from .source_manifest import WARSAW, identifier, instant, local_day, market_identity, number

SCHEMA = "multimodel-v2-formal-freeze-v1"
RECEIPT_SCHEMA = "multimodel-v2-forward-freeze-receipt-v1"
SYSTEMS = frozenset({"kb21", "consensus"})
REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 4 * 1024 * 1024


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _utc(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def _deadline(day, report_cutoff):
    deadline = datetime.combine(local_day(day), time(11, 30), tzinfo=WARSAW).astimezone(timezone.utc)
    if report_cutoff is None:
        return deadline
    supplied = instant(report_cutoff)
    if supplied > deadline:
        raise ValueError("report_cutoff_after_warsaw_deadline")
    return supplied


def verify_formal_freeze(capture, *, report_date, as_of, system=None, report_cutoff=None):
    """Read an authentic envelope without issuing a new historical prediction.

    READY means all supplied native fields passed the structural/time contract.
    Origin/authentication of source_reference must be verified by the collector;
    a hash is not a substitute for native publication identity. Inspection after
    kickoff remains historical replay, with current_ready=False.
    """
    target, observed = local_day(report_date), instant(as_of)
    cutoff = min(_deadline(report_date, report_cutoff), observed)
    payload = capture.get("payload") if isinstance(capture, dict) else None
    if not isinstance(payload, dict):
        raise ValueError("formal_freeze_payload_required")
    declared_system = payload.get("system")
    chosen = system if system is not None else declared_system
    if chosen not in SYSTEMS:
        raise ValueError("unknown_formal_freeze_system")
    missing, errors = set(), []

    def need(obj, field, path):
        value = obj.get(field) if isinstance(obj, dict) else None
        if value in (None, ""):
            missing.add(path)
        return value

    def reject(reason, **context):
        errors.append(dict(reason=reason, **context))

    locator = capture.get("locator")
    if not isinstance(locator, str) or not locator.strip():
        missing.add("capture.locator")
        reject("formal_capture_locator_missing_or_invalid", field="capture.locator")
    capture_digest = capture.get("capture_sha256")
    if not isinstance(capture_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", capture_digest):
        missing.add("capture.capture_sha256")
        reject("formal_capture_sha256_missing_or_invalid", field="capture.capture_sha256")
    if payload.get("schema") != SCHEMA:
        missing.add("schema")
        reject("not_a_formal_native_freeze")
    need(payload, "system", "system")
    need(payload, "date", "date")
    if declared_system != chosen:
        reject("formal_system_mismatch")
    if payload.get("date") != target.isoformat():
        reject("formal_report_date_mismatch")
    if payload.get("complete") is not True:
        missing.add("complete")
        reject("formal_selection_universe_incomplete")
    publication = payload.get("publication")
    if not isinstance(publication, dict):
        publication = {}
        missing.add("publication")
    native_id = need(publication, "id", "publication.id")
    try:
        identifier(native_id)
    except ValueError:
        reject("native_publication_id_missing")
    reference = need(publication, "source_reference", "publication.source_reference")
    if not isinstance(reference, str) or not reference.strip():
        reject("native_publication_source_missing")
    if publication.get("provenance") != "live_pre_match":
        missing.add("publication.provenance")
        reject("native_publication_not_prematch")
    captured = published = None
    for field in ("captured_at_utc", "published_at_utc"):
        value = need(publication, field, "publication." + field)
        try:
            parsed = instant(value)
            if field == "captured_at_utc":
                captured = parsed
            else:
                published = parsed
        except ValueError:
            reject("invalid_native_publication_timestamp", field=field)
    if captured is not None and published is not None and not captured <= published <= cutoff:
        reject("publication_after_report_cutoff_or_observation")
    picks = payload.get("picks")
    if not isinstance(picks, list) or any(not isinstance(p, dict) for p in picks):
        picks = []
        missing.add("picks")
        reject("formal_picks_required")
    count = payload.get("selection_count")
    if type(count) is not int or count != len(picks):
        missing.add("selection_count")
        reject("formal_selection_count_mismatch")
    native_keys, exact_keys, facts = [], [], {}
    verified, current = [], []
    for index, raw in enumerate(picks):
        before = len(errors)
        prefix = f"picks[{index}]."
        native_selection = need(raw, "native_selection_id", prefix + "native_selection_id")
        try:
            native_keys.append(identifier(native_selection))
        except ValueError:
            reject("native_selection_id_missing", index=index)
        for field in ("fixture_id", "event_date", "home", "away", "home_id", "away_id", "fixture_source_reference", "kickoff", "market_identity", "frozen_quote", "status"):
            need(raw, field, prefix + field)
        if raw.get("event_date") != report_date:
            reject("formal_event_date_mismatch", index=index)
        if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in ("home", "away", "status")):
            reject("formal_fixture_or_status_missing", index=index)
        key, kickoff = None, None
        try:
            key = market_identity(raw.get("market_identity"))
            if identifier(raw.get("fixture_id")) != key[0]:
                raise ValueError("formal_fixture_identity_mismatch")
            teams = {identifier(raw.get("home_id")), identifier(raw.get("away_id"))}
            if len(teams) != 2 or (key[2] == "team" and key[3] not in teams):
                raise ValueError("formal_fixture_team_mismatch")
            if not isinstance(raw.get("fixture_source_reference"), str) or not raw["fixture_source_reference"].strip():
                raise ValueError("formal_fixture_source_missing")
            exact_keys.append(key)
        except ValueError as exc:
            reject(str(exc), index=index)
        try:
            kickoff = instant(raw.get("kickoff"))
            if kickoff.astimezone(WARSAW).date() != target:
                raise ValueError("formal_kickoff_date_mismatch")
            if captured is None or published is None or not captured <= published < kickoff:
                raise ValueError("formal_publication_not_before_kickoff")
            if key:
                fact = (_utc(kickoff), raw.get("home"), raw.get("away"),
                        identifier(raw.get("home_id")), identifier(raw.get("away_id")))
                facts.setdefault(key[0], set()).add(fact)
        except ValueError as exc:
            reject(str(exc), index=index)
        quote = raw.get("frozen_quote")
        if not isinstance(quote, dict):
            quote = {}
        for field in ("market_identity", "bookmaker", "selected_odd", "provider_updated_at", "source_reference"):
            need(quote, field, prefix + "frozen_quote." + field)
        try:
            if key is None or market_identity(quote.get("market_identity")) != key:
                raise ValueError("formal_quote_market_mismatch")
            if not isinstance(quote.get("bookmaker"), str) or not quote["bookmaker"].strip():
                raise ValueError("formal_bookmaker_missing")
            if not isinstance(quote.get("source_reference"), str) or not quote["source_reference"].strip():
                raise ValueError("formal_quote_source_missing")
            if number(quote.get("selected_odd")) <= 1:
                raise ValueError("formal_invalid_odds")
            quoted = instant(quote.get("provider_updated_at"))
            if captured is None or kickoff is None or not quoted <= captured < kickoff:
                raise ValueError("formal_quote_lookahead")
            side_odd = quote.get(key[4] + "_odd")
            if side_odd is not None and number(side_odd) != number(quote["selected_odd"]):
                raise ValueError("formal_quote_price_conflict")
        except ValueError as exc:
            reject(str(exc), index=index)
        if len(errors) == before:
            verified.append(deepcopy(raw))
            if kickoff is not None and observed < kickoff:
                current.append(deepcopy(raw))
    if any(n > 1 for n in Counter(native_keys).values()):
        reject("duplicate_native_selection_id")
    if any(n > 1 for n in Counter(exact_keys).values()):
        reject("duplicate_formal_fixture_market")
    if any(len(values) > 1 for values in facts.values()):
        reject("conflicting_formal_fixture")
    ready = not missing and not errors
    current_ready = ready and target >= observed.astimezone(WARSAW).date() and len(current) == len(picks)
    return {"schema": "multimodel-v2-formal-freeze-verification-v1", "system": chosen,
            "date": report_date, "as_of": _utc(observed), "report_cutoff": _utc(cutoff),
            "status": "READY" if ready else "SOURCE_BLOCKED",
            "source_kind": "original_native_formal_freeze", "native_publication_id": native_id,
            "capture_sha256": capture.get("capture_sha256"), "payload_sha256": _digest(payload),
            "missing_fields": sorted(missing), "rejections": errors,
            "recorded_picks": len(picks), "verified_picks": verified if ready else [],
            "current_ready": current_ready,
            "eligible_for_current_report": current_ready,
            "eligible_as_new_prematch": False,
            "purpose": "current_formal_freeze" if current_ready else "historical_replay" if ready else "blocked",
            "original_payload": deepcopy(payload), "register_writes": False, "n_effect": 0}


def inspect_historical_register(capture, system, *, report_date, as_of):
    """A selection row never becomes a native fixture/freeze by renaming fields."""
    local_day(report_date)
    instant(as_of)
    bundle = adapt_sheet(capture, system)
    selected = [r for r in bundle["rows"] if r["has_recorded_selection"]]
    current = [r for r in selected if r.get("date") == report_date]
    paths = ["publication.id", "publication.captured_at_utc", "publication.published_at_utc",
             "publication.source_reference", "picks[].native_selection_id", "picks[].fixture_id",
             "picks[].kickoff", "picks[].market_identity", "picks[].frozen_quote.market_identity",
             "picks[].frozen_quote.bookmaker", "picks[].frozen_quote.provider_updated_at",
             "picks[].frozen_quote.source_reference"]
    if system == "consensus":
        paths.append("picks[].event_date")
    return {"schema": "multimodel-v2-register-freeze-inspection-v1", "system": system,
            "date": report_date, "status": "SOURCE_BLOCKED", "source_kind": "historical_register",
            "read_rows": len(bundle["rows"]), "recorded_selection_rows": len(selected),
            "non_selection_rows": bundle["non_selection_rows"], "latest_source_date": bundle["latest_date"],
            "source_dated_selection_rows": len(current), "current_formal_picks": [],
            "missing_fields": paths, "blockers": bundle["blockers"] + ["original_formal_publication_not_recorded"],
            "source": deepcopy(bundle["source"]), "source_url": bundle["spreadsheet_url"],
            "original_rows": deepcopy(bundle["rows"]), "register_writes": False,
            "historical_rows_promoted": 0, "n_effect": 0}


def record_forward_freeze(payload, output_dir, *, clock=None, report_cutoff=None):
    """Atomically record one supplied fresh native publication, never backfill.

    clock is a trusted collector clock dependency (UTC system time by default),
    not a value read from the publication. Tests may inject a fixed clock.
    Output must be outside the checkout. Existing native-ID addresses never
    overwrite, including replay of identical bytes.
    """
    now = instant((clock() if clock is not None else datetime.now(timezone.utc)).isoformat())
    if not isinstance(payload, dict):
        raise ValueError("formal_freeze_payload_required")
    pub = payload.get("publication") or {}
    published = instant(pub.get("published_at_utc"))
    captured = instant(pub.get("captured_at_utc"))
    if not 0 <= (now - published).total_seconds() <= 60 or not 0 <= (now - captured).total_seconds() <= 300:
        raise ValueError("forward_only_fresh_native_publication_required")
    capture = {"payload": deepcopy(payload), "capture_sha256": _digest(payload), "locator": "supplied-native-publisher"}
    checked = verify_formal_freeze(capture, report_date=payload.get("date"), as_of=_utc(now), report_cutoff=report_cutoff)
    if checked["status"] != "READY" or not checked["current_ready"]:
        raise ValueError("forward_formal_freeze_not_ready")
    root = Path(output_dir).resolve()
    if root == REPO_ROOT or root.is_relative_to(REPO_ROOT):
        raise ValueError("formal_output_must_be_outside_checkout")
    native_id = identifier(pub["id"])
    # The hash is a storage address, never a generated native publication ID.
    address = hashlib.sha256(native_id.encode("utf-8")).hexdigest()
    target_dir = root / payload["system"] / payload["date"]
    if not target_dir.resolve().is_relative_to(root):
        raise ValueError("formal_output_symlink_escape")
    target = target_dir / (address + ".json")
    receipt = {"schema": RECEIPT_SCHEMA, "recorded_at_utc": _utc(now),
               "report_cutoff": checked["report_cutoff"],
               "native_publication_id": deepcopy(pub["id"]), "native_payload_sha256": _digest(payload),
               "native_freeze": deepcopy(payload), "register_writes": False, "n_effect": 0}
    raw = _bytes(receipt)
    if len(raw) > MAX_BYTES:
        raise ValueError("formal_publication_size_limit")
    target_dir.mkdir(parents=True, exist_ok=True)
    descriptor, staging_name = tempfile.mkstemp(prefix=".pending-freeze-", dir=target_dir)
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Exclusive hard-link creation publishes the complete fsynced file.
        os.link(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    return {"path": str(target), "sha256": hashlib.sha256(raw).hexdigest(),
            "native_publication_id": deepcopy(pub["id"]), "status": "RECORDED_FORWARD_ONLY",
            "register_writes": False, "n_effect": 0}


def read_forward_freeze(path):
    """Read and verify our isolated receipt without assigning a new freeze time."""
    target = Path(path)
    if target.is_symlink():
        raise ValueError("formal_receipt_symlink_not_allowed")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(target, flags)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("formal_receipt_regular_file_required")
        if details.st_size > MAX_BYTES:
            raise ValueError("formal_publication_size_limit")
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        with stream:
            raw = stream.read(MAX_BYTES + 1)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > MAX_BYTES:
        raise ValueError("formal_publication_size_limit")
    receipt = json.loads(raw)
    if not isinstance(receipt, dict):
        raise ValueError("formal_receipt_integrity_mismatch")
    native = receipt.get("native_freeze")
    publication = native.get("publication") if isinstance(native, dict) else None
    if (receipt.get("schema") != RECEIPT_SCHEMA or not isinstance(native, dict)
            or not isinstance(publication, dict)
            or receipt.get("native_payload_sha256") != _digest(native)
            or receipt.get("native_publication_id") != publication.get("id")):
        raise ValueError("formal_receipt_integrity_mismatch")
    recorded = instant(receipt.get("recorded_at_utc"))
    published, captured = instant(publication.get("published_at_utc")), instant(publication.get("captured_at_utc"))
    if not 0 <= (recorded - published).total_seconds() <= 60 or not 0 <= (recorded - captured).total_seconds() <= 300:
        raise ValueError("formal_receipt_forward_time_mismatch")
    if not isinstance(receipt.get("report_cutoff"), str):
        raise ValueError("formal_receipt_report_cutoff_missing")
    capture = {"locator": str(target), "capture_sha256": hashlib.sha256(raw).hexdigest(),
               "payload": deepcopy(native), "receipt_recorded_at_utc": receipt["recorded_at_utc"]}
    checked = verify_formal_freeze(capture, report_date=native.get("date"), as_of=_utc(recorded),
                                  report_cutoff=receipt["report_cutoff"])
    if checked["status"] != "READY" or not checked["current_ready"]:
        raise ValueError("formal_receipt_native_freeze_not_ready_at_record_time")
    return capture


def main(argv=None):
    import argparse
    from .adapters import load_json
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="Read a native freeze, without publishing")
    history = commands.add_parser("inspect-register", help="Read source register; never promotes rows")
    for command in (verify, history):
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--date", required=True)
        command.add_argument("--as-of", required=True)
        command.add_argument("--system", choices=sorted(SYSTEMS), required=command is history)
    verify.add_argument("--report-cutoff")
    record = commands.add_parser("record", help="Record only a fresh original native publication")
    record.add_argument("--source", type=Path, required=True)
    record.add_argument("--output-dir", type=Path, required=True)
    record.add_argument("--report-cutoff")
    args = parser.parse_args(argv)
    source = load_json(args.source)
    if args.command == "record":
        result = record_forward_freeze(source["payload"], args.output_dir, report_cutoff=args.report_cutoff)
    elif args.command == "inspect-register":
        result = inspect_historical_register(source, args.system, report_date=args.date, as_of=args.as_of)
        result.pop("original_rows")
    else:
        result = verify_formal_freeze(source, system=args.system, report_date=args.date, as_of=args.as_of,
                                      report_cutoff=args.report_cutoff)
        result["verified_pick_count"] = len(result.pop("verified_picks"))
        result.pop("original_payload")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
