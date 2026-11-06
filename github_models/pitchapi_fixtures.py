"""Uncapped, fixture-only PitchAPI collection for isolated research.

At most four UTC date requests and one metadata request per unique league are made.
No xG, history, scores, odds, model probabilities or production files are used.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from github_models.competition_identity import canonicalize, country_code, LABEL_TO_LEAGUE, _key

SCHEMA = "pitchapi-research-fixtures-v1"
WARSAW = ZoneInfo("Europe/Warsaw")


def _field(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _id(value):
    if type(value) not in (str, int) or not str(value).strip():
        raise ValueError("provider_identifier_missing_or_invalid")
    return str(value).strip()


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("provider_name_missing_or_invalid")
    return value.strip()


def _instant(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise ValueError("provider_time_missing_or_timezone_invalid")
    return stamp.astimezone(timezone.utc)


def _stamp(clock):
    return _instant(clock()).isoformat().replace("+00:00", "Z")


def _country(value):
    raw = _field(value, "country_code")
    if raw is None:
        country = _field(value, "country")
        if isinstance(country, str):
            raw = country
        elif country is not None:
            raw = _field(country, "code") or _field(country, "name")
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def _metadata(client, league_id, clock):
    try:
        detail = client.leagues.get(league_id)
        received = _stamp(clock)  # response observation, never a backdated timestamp
        if detail is None or isinstance(detail, (str, int, float, bool, list)):
            raise TypeError("invalid_league_metadata")
        detail_id, detail_name = _field(detail, "id"), _field(detail, "name")
        return dict(status="ok", requested_league_id=league_id,
                    provider_league_id=_id(detail_id) if detail_id is not None else None,
                    provider_league_name=_text(detail_name) if detail_name is not None else None,
                    country_code=_country(detail), received_at_utc=received)
    except Exception as exc:
        return dict(status="error", requested_league_id=league_id,
                    error_type=type(exc).__name__, received_at_utc=_stamp(clock))


def _names_agree(left, right):
    return LABEL_TO_LEAGUE.get(_key(left), _key(left)) == LABEL_TO_LEAGUE.get(_key(right), _key(right))


def _fixture(match, metadata, snapshot, target):
    league, home, away = (_field(match, key) for key in ("league", "home_team", "away_team"))
    kickoff = _instant(_field(match, "time_utc"))
    if kickoff <= _instant(snapshot):
        return None, "not_future_at_observation"
    if kickoff.astimezone(WARSAW).date() != target:
        return None, "outside_target_warsaw_day"
    lid = _id(_field(league, "id"))
    row = dict(pitch_match_id=_id(_field(match, "id")), league=_text(_field(league, "name")),
               league_id=lid, home=_text(_field(home, "name")), away=_text(_field(away, "name")),
               home_team_id=_id(_field(home, "id")), away_team_id=_id(_field(away, "id")),
               kickoff_utc=kickoff.isoformat().replace("+00:00", "Z"),
               source_provider="PitchAPI", identity_blockers=[])
    row["raw_league"], row["raw_home"], row["raw_away"] = row["league"], row["home"], row["away"]
    embedded_country = _country(league)
    detailed_country = metadata.get("country_code")
    row.update(country_code=detailed_country or embedded_country,
               embedded_country_code=embedded_country,
               league_metadata_status=metadata["status"],
               country_identity_source=("league_metadata" if detailed_country else
                                        "embedded_league" if embedded_country else "missing_provider_metadata"))
    blockers = row["identity_blockers"]
    if row["home_team_id"] == row["away_team_id"]:
        blockers.append("fixture_team_ids_not_distinct")
    if metadata.get("provider_league_id") is not None and str(metadata["provider_league_id"]).strip() != lid:
        blockers.append("league_metadata_id_conflict")
    metadata_name = metadata.get("provider_league_name")
    if metadata_name is not None and not _names_agree(row["league"], metadata_name):
        blockers.append("league_metadata_name_conflict")
    if detailed_country and embedded_country:
        detail_code, embedded_code = country_code(detailed_country), country_code(embedded_country)
        if (detail_code or _key(detailed_country)) != (embedded_code or _key(embedded_country)):
            blockers.append("league_metadata_country_conflict")
    try:
        canonicalize(row)  # assess contradictions; keep raw names and metadata intact
    except ValueError as exc:
        blockers.append(str(exc))
    row["identity_blockers"] = sorted(set(blockers))
    return row, None


def collect(client, *, start_date=None, days=3, clock=None):
    """Observe UTC provider date lists, then group by actual Warsaw kickoff day.

    Three Warsaw days can span four UTC dates near local midnight. Source errors
    fail all requested calendar days closed; metadata failures remain explicit
    and may use only the resolver's reviewed competition-ID evidence later.
    """
    if type(days) is not int or not 1 <= days <= 3:
        raise ValueError("research_collection_days_must_be_1_to_3")
    clock = clock or (lambda: datetime.now(timezone.utc))
    initial = _instant(clock())
    today = initial.astimezone(WARSAW).date()
    start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date or today
    if not today <= start <= today + timedelta(days=2) or start + timedelta(days=days-1) > today + timedelta(days=2):
        raise ValueError("research_collection_requires_current_three_warsaw_days")
    targets = [start + timedelta(days=offset) for offset in range(days)]
    payloads = {target.isoformat(): dict(
        schema=SCHEMA, source="PitchAPI", target_date=target.isoformat(), source_status="ok",
        fixtures=[], available_upcoming=0, fixtures_collected=0, league_metadata={},
        errors=[], exclusions={}, no_fixture_cap=True, xg_context_collected=False,
        model_effect="NONE", kb_n_effect=0, dev_n_effect=0) for target in targets}
    first_local = datetime.combine(start, datetime.min.time(), tzinfo=WARSAW).astimezone(timezone.utc)
    end_local = datetime.combine(targets[-1] + timedelta(days=1), datetime.min.time(), tzinfo=WARSAW).astimezone(timezone.utc)
    query_start = max(initial, first_local).date()
    query_end = (end_local - timedelta(microseconds=1)).date()
    cache, batches, queries = {}, [], []
    query = query_start
    while query <= query_end:
        requested = _stamp(clock)
        try:
            response = client.date.get(query.isoformat(), status="upcoming")
            matches = list(_field(response, "matches"))
            received = _stamp(clock)
            queries.append(dict(date=query.isoformat(), status="ok", requested_at_utc=requested,
                                received_at_utc=received, available_upcoming=len(matches)))
            batches.append((query.isoformat(), matches))
        except Exception as exc:
            queries.append(dict(date=query.isoformat(), status="error", requested_at_utc=requested,
                                received_at_utc=_stamp(clock), error_type=type(exc).__name__))
            query += timedelta(days=1)
            continue
        for match in matches:
            try:
                lid = _id(_field(_field(match, "league"), "id"))
            except ValueError:
                continue
            if lid not in cache:
                cache[lid] = _metadata(client, lid, clock)
        query += timedelta(days=1)
    # One conservative observation cutoff follows every response and precedes
    # rebucketing. A game starting during collection cannot become prematch.
    snapshot = _stamp(clock)
    clock_valid = all(_instant(item["requested_at_utc"]) <= _instant(item["received_at_utc"]) <= _instant(snapshot)
                      for item in queries) and all(_instant(item["received_at_utc"]) <= _instant(snapshot) for item in cache.values())
    errors = [dict(operation="date_fixtures", query_date=item["date"], error_type=item["error_type"])
              for item in queries if item["status"] == "error"]
    if not clock_valid:
        errors.append(dict(operation="observation_clock_order", error_type="ValueError"))
    for payload in payloads.values():
        payload.update(snapshot_utc=snapshot, requested_at_utc=queries[0]["requested_at_utc"],
                       source_queries=queries, fixtures_received_at_utc=max(item["received_at_utc"] for item in queries))
        if errors:
            payload.update(source_status="source_error", available_upcoming=None, errors=list(errors))
    seen, conflicting_ids = {}, set()
    for query_date, matches in batches:
        for match in matches:
            try:
                kickoff = _instant(_field(match, "time_utc"))
                target = kickoff.astimezone(WARSAW).date()
                payload = payloads.get(target.isoformat())
                if payload is None:
                    continue  # observed provider row is outside the requested local horizon
                if payload["available_upcoming"] is not None:
                    payload["available_upcoming"] += 1
                lid = _id(_field(_field(match, "league"), "id"))
                payload["league_metadata"][lid] = cache[lid]
                row, exclusion = _fixture(match, cache[lid], snapshot, target)
                if exclusion:
                    payload["exclusions"][exclusion] = payload["exclusions"].get(exclusion, 0) + 1
                    continue
                row.update(provider_query_date=query_date,
                           provider_response_received_at_utc=next(item["received_at_utc"] for item in queries if item["date"] == query_date))
                identity = row["pitch_match_id"]
                if identity in conflicting_ids:
                    continue
                if identity in seen:
                    previous, previous_payload = seen[identity]
                    facts = lambda item: {key:value for key,value in item.items() if key not in ("provider_query_date", "provider_response_received_at_utc")}
                    if facts(previous) == facts(row):
                        payload["exclusions"]["duplicate_consistent_provider_fixture"] = payload["exclusions"].get("duplicate_consistent_provider_fixture", 0) + 1
                        if payload["available_upcoming"] is not None:
                            payload["available_upcoming"] -= 1
                        continue
                    conflicting_ids.add(identity)
                    previous_payload["fixtures"] = [item for item in previous_payload["fixtures"] if item["pitch_match_id"] != identity]
                    raise ValueError("contradictory_provider_fixture_id")
                seen[identity] = (row, payload)
                if clock_valid:
                    payload["fixtures"].append(row)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                for payload in payloads.values():
                    if payload["source_status"] != "source_error":
                        payload["source_status"] = "partial"
                    payload["errors"].append(dict(operation="fixture_validation", error_type=type(exc).__name__))
    for payload in payloads.values():
        payload["fixtures"].sort(key=lambda row: (row["kickoff_utc"], row["pitch_match_id"]))
        payload["fixtures_collected"] = len(payload["fixtures"])
    return list(payloads.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/github_models/pitchapi_fixtures")
    parser.add_argument("--start-date", help="Current Warsaw date by default")
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    if not os.environ.get("PITCHAPI_API_KEY"):
        raise SystemExit("Missing PITCHAPI_API_KEY")
    from pitchapi import PitchAPI
    with PitchAPI() as client:
        snapshots = collect(client, start_date=args.start_date, days=args.days)
    target = Path(args.output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for payload in snapshots:
        (target / (payload["target_date"] + ".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(dict(date=payload["target_date"], status=payload["source_status"],
                             available=payload["available_upcoming"], collected=payload["fixtures_collected"],
                             metadata_errors=sum(x["status"] == "error" for x in payload["league_metadata"].values()))))
    if any(payload["source_status"] != "ok" for payload in snapshots):
        raise SystemExit("PitchAPI research collection incomplete; diagnostic snapshots written")


if __name__ == "__main__":
    main()
