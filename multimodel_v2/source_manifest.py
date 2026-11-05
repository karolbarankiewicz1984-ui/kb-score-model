"""Validate supplied run/artifact evidence without fetching or changing sources.

See docs/MULTIMODEL_V2_SOURCES.md for the input contract. All instants must
include a UTC offset; Warsaw dates are derived from instants, never filenames.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
API_WORKFLOWS = frozenset({
    ".github/workflows/api-market-scan.yml",
    ".github/workflows/api-market-multiday-experiment.yml",
})


def instant(value):
    """Parse an explicitly zoned ISO timestamp and compare only in UTC."""
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid_timestamp") from exc
    if result.utcoffset() is None:
        raise ValueError("timezone_required")
    try:
        return result.astimezone(timezone.utc)
    except OverflowError as exc:
        raise ValueError("invalid_timestamp") from exc


def local_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_local_date")
    return date.fromisoformat(value)


def number(value):
    """Exact finite numbers; booleans and implicit defaults are forbidden."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("invalid_number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid_number") from exc
    if not result.is_finite():
        raise ValueError("invalid_number")
    return result


def identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("missing_identity")
    return str(value).strip()


def market_identity(item):
    """No tolerance/rounding of exact lines, no inferred scope or settlement."""
    if not isinstance(item, dict):
        raise ValueError("incomplete_market_identity")
    scope = item.get("market_scope")
    if (scope not in ("team", "match") or item.get("direction") not in ("over", "under")
            or not isinstance(item.get("market"), str) or not item["market"].strip()
            or not isinstance(item.get("settlement_period"), str)
            or not item["settlement_period"].strip()):
        raise ValueError("incomplete_market_identity")
    team = identifier(item.get("team_id")) if scope == "team" else None
    if scope == "match" and item.get("team_id") is not None:
        raise ValueError("ambiguous_match_team")
    line = number(item.get("line"))
    if line < 0:
        raise ValueError("invalid_line")
    return (identifier(item.get("fixture_id")), item["market"], scope, team,
            item["direction"], line, item["settlement_period"])


def _utc(value):
    return value.isoformat().replace("+00:00", "Z")


def _identity_json(key):
    return dict(zip(("fixture_id", "market", "market_scope", "team_id", "direction",
                     "line", "settlement_period"), (*key[:5], str(key[5]), key[6])))


def _verified_run(run, target, cutoff):
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("run_not_successful")
    identifier(run.get("id"))
    if not isinstance(run.get("path"), str) or run["path"] not in API_WORKFLOWS:
        raise ValueError("wrong_workflow")
    if not isinstance(run.get("head_sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]):
        raise ValueError("invalid_sha")
    started, completed = instant(run.get("run_started_at")), instant(run.get("updated_at"))
    if not started <= completed <= cutoff:
        raise ValueError("run_outside_cutoff")
    if started.astimezone(WARSAW).date() > target:
        raise ValueError("run_after_report_date")
    if run.get("source_kind") == "git_publication":
        from .git_publication import validate_receipt
        receipts = run.get("git_publications")
        if not isinstance(receipts, list) or not receipts or any(not isinstance(r, dict) for r in receipts):
            raise ValueError("missing_git_publications")
        refs = [validate_receipt(r, run) for r in receipts]
        if len(refs) != len(set(refs)):
            raise ValueError("ambiguous_git_publications")
        live = {r["source_ref"] for r in receipts if r["date"] == target.isoformat()}
        if not live:
            raise ValueError("date_not_covered")
        return started, completed, live
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, list) or any(not isinstance(a, dict) for a in artifacts):
        raise ValueError("missing_artifacts")
    names = [a.get("name") for a in artifacts]
    if (any(not isinstance(n, str) or not n.strip() for n in names)
            or len(names) != len(set(names))):
        raise ValueError("ambiguous_artifacts")
    for artifact in artifacts:
        if "workflow_run" in artifact:
            origin = artifact["workflow_run"]
            if (not isinstance(origin, dict) or identifier(origin.get("id")) != identifier(run["id"])
                    or origin.get("head_sha") != run["head_sha"]):
                raise ValueError("artifact_run_mismatch")
    live = {a["name"] for a in artifacts if a.get("expired") is False}
    statuses = run.get("date_statuses")
    if not isinstance(statuses, list) or any(not isinstance(s, dict) for s in statuses):
        raise ValueError("missing_date_status")
    matches = [s for s in statuses if s.get("date") == target.isoformat()]
    if (len(matches) != 1 or matches[0].get("status") != "ok"
            or not isinstance(matches[0].get("artifact_name"), str)
            or matches[0]["artifact_name"] not in live):
        raise ValueError("date_not_covered")
    return started, completed, live


def _quote(quote, key, snapshot_at, kickoff):
    if market_identity(quote.get("market_identity") or {}) != key:
        raise ValueError("quote_market_mismatch")
    if "direction" in quote and quote["direction"] != key[4]:
        raise ValueError("quote_market_mismatch")
    if not isinstance(quote.get("bookmaker"), str) or not quote["bookmaker"].strip():
        raise ValueError("missing_bookmaker")
    odd = number(quote.get("selected_odd"))
    if odd <= 1:
        raise ValueError("invalid_odds")
    # A supplied side-specific price must agree with selected_odd as well.
    side_odd = quote.get(key[4] + "_odd")
    if side_odd is not None and number(side_odd) != odd:
        raise ValueError("conflicting_odds")
    stamp = instant(quote.get("provider_updated_at"))
    if stamp > snapshot_at or stamp >= kickoff:
        raise ValueError("quote_lookahead")
    return {"bookmaker": quote["bookmaker"], "selected_odd": str(odd),
            "provider_updated_at": _utc(stamp), "market_identity": _identity_json(key)}


def build_source_manifest(report_date, runs, snapshots, *, as_of):
    """Return dated coverage, verified rows and explicit rejection reasons.

    A completed run alone never establishes coverage: require a dated artifact
    or an independently linked native Git publication from the same run.
    Historical frozen rows may be audited; the watchlist separately refuses to
    issue observations at/after kickoff. Inputs are never modified.
    """
    target, cutoff = local_day(report_date), instant(as_of)
    if not isinstance(runs, list) or not isinstance(snapshots, list):
        raise ValueError("source_lists_required")
    result = {"schema": "multimodel-v2-source-manifest-v1", "date": report_date,
              "as_of": _utc(cutoff), "status": "blocked", "sources": [],
              "records": [], "rejections": []}

    def reject(reason, **context):
        result["rejections"].append(dict(reason=reason, **deepcopy(context)))

    indexed = defaultdict(list)
    for run in runs:
        try:
            if not isinstance(run, dict):
                raise ValueError("invalid_run")
            indexed[identifier(run.get("id"))].append(run)
        except ValueError as exc:
            reject(str(exc))
    usable = {}
    for rid, copies in indexed.items():
        try:
            if len(copies) != 1:
                raise ValueError("duplicate_run_id")
            usable[rid] = (copies[0], *_verified_run(copies[0], target, cutoff))
        except ValueError as exc:
            reject(str(exc), run_id=rid)

    chosen, all_fixture_facts = {}, defaultdict(set)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            reject("invalid_snapshot")
            continue
        # Wrong-day snapshots cannot fill this date or be reassigned to it.
        if snapshot.get("date") != report_date:
            reject("snapshot_date_mismatch", date=snapshot.get("date"))
            continue
        try:
            rid = identifier(snapshot.get("run_id"))
            if rid not in usable:
                raise ValueError("no_verified_run")
            run, started, completed, artifacts = usable[rid]
            if snapshot.get("head_sha") != run["head_sha"]:
                raise ValueError("snapshot_sha_mismatch")
            git_source = run.get("source_kind") == "git_publication"
            if git_source:
                from .git_publication import validate_receipt
                if snapshot.get("source_kind") != "git_publication" or snapshot.get("source_ref") not in artifacts:
                    raise ValueError("snapshot_git_publication_unavailable")
                receipt = next(r for r in run["git_publications"] if r["source_ref"] == snapshot["source_ref"])
                validate_receipt(receipt, run, payload=snapshot)
            elif (not isinstance(snapshot.get("artifact_name"), str)
                    or snapshot["artifact_name"] not in artifacts):
                raise ValueError("snapshot_artifact_unavailable")
            captured = instant(snapshot.get("generated_at_utc"))
            if not started <= captured <= completed:
                raise ValueError("snapshot_outside_run")
            rows = snapshot.get("background_candidates")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("missing_snapshot_rows")
        except ValueError as exc:
            reject(str(exc), run_id=snapshot.get("run_id"))
            continue

        source = {"run_id": rid, "conclusion": run["conclusion"],
                  "head_sha": run["head_sha"], "artifact_names": [] if git_source else sorted(artifacts),
                  "snapshot_artifact": None if git_source else snapshot["artifact_name"],
                  "snapshot_at": _utc(captured), "date": report_date}
        if git_source:
            source.update(source_kind="git_publication", source_ref=snapshot["source_ref"])
        if source not in result["sources"]:
            result["sources"].append(source)

        # Multiple different markets on a fixture are valid. Repeated exact
        # identities or contradictory fixture facts are ambiguous, not extra N.
        identities, facts = Counter(), defaultdict(set)
        for row in rows:
            try:
                key = market_identity(row)
                identities[key] += 1
                if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("home", "away")):
                    raise ValueError("missing_teams")
                fact = (_utc(instant(row.get("kickoff"))), row["home"], row["away"])
                facts[key[0]].add(fact)
                all_fixture_facts[key[0]].add(fact)
            except ValueError:
                pass  # Detailed reason is emitted in the validating pass.
        for row in rows:
            try:
                key = market_identity(row)
                if identities[key] > 1:
                    raise ValueError("duplicate_fixture_market")
                if len(facts[key[0]]) > 1:
                    raise ValueError("conflicting_fixture")
                kickoff = instant(row.get("kickoff"))
                if kickoff.astimezone(WARSAW).date() != target:
                    raise ValueError("kickoff_date_mismatch")
                if captured >= kickoff:
                    raise ValueError("snapshot_lookahead")
                if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("home", "away")):
                    raise ValueError("missing_teams")
                market_data = row.get("market_data")
                quotes = market_data.get("quotes") if isinstance(market_data, dict) else None
                if not isinstance(quotes, list) or not quotes:
                    raise ValueError("missing_odds")
                valid_quotes = []
                for quote in quotes:
                    try:
                        if not isinstance(quote, dict):
                            raise ValueError("invalid_quote")
                        verified = _quote(quote, key, captured, kickoff)
                        if verified not in valid_quotes:
                            valid_quotes.append(verified)
                    except ValueError as exc:
                        reject(str(exc), run_id=rid, fixture_id=key[0])
                if not valid_quotes:
                    raise ValueError("no_verified_quote")
                try:
                    score = number(row.get("final_assessment_pct"))
                    if not 0 <= score <= 100:
                        raise ValueError("invalid_api_assessment")
                    score = str(score)
                except ValueError:
                    score = None
                record = {"market_identity": _identity_json(key), "kickoff": _utc(kickoff),
                          "home": row["home"], "away": row["away"],
                          "final_assessment_pct": score,
                          "quotes": valid_quotes, "source": deepcopy(source)}
                # Earliest authenticated freeze wins; reruns do not inflate N.
                order = (captured, rid, snapshot.get("source_ref") if git_source else snapshot["artifact_name"])
                if key in chosen and order == chosen[key][0] and record != chosen[key][1]:
                    # Conflicting copies of the same freeze cannot be resolved
                    # by input order. Keep the ambiguity until the final pass.
                    chosen[key] = (order, None)
                    reject("conflicting_snapshot_copy", run_id=rid, fixture_id=key[0])
                elif key not in chosen or order < chosen[key][0]:
                    chosen[key] = (order, record)
            except ValueError as exc:
                reject(str(exc), run_id=rid, fixture_id=row.get("fixture_id"))

    if result["sources"]:
        result["status"] = "covered"
    else:
        reject("no_verified_snapshot_for_date")
    result["sources"].sort(key=lambda s: (s["snapshot_at"], s["run_id"], s.get("source_ref", s["snapshot_artifact"])))
    for key, (_, record) in sorted(chosen.items(), key=lambda pair: str(pair[0])):
        if len(all_fixture_facts[key[0]]) > 1:
            reject("conflicting_fixture", fixture_id=key[0])
        elif record is not None:
            result["records"].append(record)
    return result
