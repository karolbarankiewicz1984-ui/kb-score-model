"""Strict pre-match PitchAPI xG evidence for the SINGLE-source KB21 fixture list.

No network requests, no second fixture source, no prediction, no market odds.
Only previously saved PitchAPI snapshots can contribute; an xG sample must
come from a match well BEFORE the snapshot and CURRENT candidate kickoff.
Every match is identified by canonical API-Football fixture ID and matched
to exactly one PitchAPI fixture via league + both names + <=20-min kickoff.
No imputation, original KB21 P(model), rating, N or PLAY writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

from tools.kb21_single_source_calendar import (
    DAY_SCHEMA, SCHEMA as CALENDAR_SCHEMA, WARSAW, _iso_datetime,
)
from tools.pitchapi_xg_lab import competition, norm

SCHEMA = "kb21-preodds-pitchapi-xg-bridge-v1"
PITCH_SCHEMA = "pitchapi-prematch-context-v1"
MAX_TIME_DIFFERENCE = timedelta(minutes=20)
MAX_AGE = timedelta(days=3)
MIN_FINISHED_BUFFER = timedelta(hours=2)
MAX_ROWS = 1000


def _clock(now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware UTC clock is required")
    return now.astimezone(timezone.utc)


def _number(value):
    return (type(value) in (float, int) and math.isfinite(value)
            and 0 <= value <= 20)


def _validate_recent(recent, snapshot, pitch_fixture_id):
    """Return verified five-game xG, or no usable sample (never zero)."""
    if not isinstance(recent, dict) or recent.get("data_quality") != "sufficient":
        return None
    n, requested = recent.get("complete_samples"), recent.get("requested_samples")
    sample_rows = recent.get("samples")
    ids = recent.get("source_match_ids")
    if (type(n) is not int or not 3 <= n <= 5 or type(requested) is not int
            or not n <= requested <= 5 or not isinstance(sample_rows, list)
            or not isinstance(ids, list) or len(sample_rows) != n
            or len(ids) != n or len(set(map(str, ids))) != n):
        return None
    gf, ga = [], []
    for i, item in enumerate(sample_rows):
        if not isinstance(item, dict):
            return None
        match_id = item.get("match_id")
        when = _iso_datetime(item.get("kickoff_utc"))
        xg, xga = item.get("xg_for"), item.get("xg_against")
        if (not isinstance(match_id, str) or not match_id or match_id != ids[i]
                or match_id == pitch_fixture_id or when is None
                or when + MIN_FINISHED_BUFFER > snapshot
                or not _number(xg) or not _number(xga)):
            return None
        gf.append(float(xg))
        ga.append(float(xga))
    for key, values in (("mean_xg_for", gf), ("mean_xg_against", ga)):
        stated = recent.get(key)
        if not _number(stated) or abs(float(stated)-sum(values)/n) > .002:
            return None
    return {
        "sample_size": n, "mean_xg_for": round(sum(gf)/n, 3),
        "mean_xg_against": round(sum(ga)/n, 3),
        "samples": [
            {"pitch_match_id": r["match_id"], "kickoff_utc": r["kickoff_utc"],
             "xg_for": r["xg_for"], "xg_against": r["xg_against"]}
            for r in sample_rows
        ],
        "metric": "HISTORICAL_EXPECTED_GOALS_ACTUAL_PITCHAPI_NOT_PREDICTED",
    }


def _snapshot(doc, day, now):
    if not isinstance(doc, dict):
        return None, None, "INVALID_PREMATCH_SNAPSHOT"
    stamped = _iso_datetime(doc.get("snapshot_utc"))
    if (doc.get("schema") != PITCH_SCHEMA or doc.get("source") != "PitchAPI"
            or doc.get("target_date") != day or stamped is None
            or stamped > now or now-stamped > MAX_AGE
            or not isinstance(doc.get("fixtures"), list)
            or len(doc["fixtures"]) > MAX_ROWS
            or doc.get("fixtures_collected") != len(doc["fixtures"])
            or doc.get("model_effect") != "NONE" or doc.get("kb_n_effect") != 0):
        return None, None, "INVALID_PREMATCH_SNAPSHOT"
    valid = []
    seen = set()
    other_local_day = 0
    for match in doc["fixtures"]:
        if not isinstance(match, dict):
            return None, None, "INVALID_PREMATCH_SNAPSHOT"
        mid = match.get("pitch_match_id")
        kickoff = _iso_datetime(match.get("kickoff_utc"))
        if (not isinstance(mid, str) or not mid.strip() or mid in seen
                or kickoff is None
                or not isinstance(match.get("home"), str)
                or not isinstance(match.get("away"), str)
                or not isinstance(match.get("league"), str)
                or not norm(match["home"]) or not norm(match["away"])
                or not competition(match["league"])):
            return None, None, "INVALID_PREMATCH_SNAPSHOT"
        seen.add(mid)
        # PitchAPI's date boundary may differ from Europe/Warsaw. E.g.
        # 22:30 UTC on October 18 is already October 19 in Poland. This
        # valid out-of-day record cannot poison all same-day xG observations.
        if kickoff.astimezone(WARSAW).date().isoformat() != day:
            other_local_day += 1
            continue
        valid.append(match)
    reason = ("VALID_PREMATCH_ARCHIVE" if not other_local_day else
              f"VALID_PREMATCH_ARCHIVE_IGNORED_{other_local_day}_OTHER_WARSAW_DAY")
    return valid, stamped, reason


def _canonical(manifest, calendars):
    if (not isinstance(manifest, dict) or manifest.get("schema") != CALENDAR_SCHEMA
            or manifest.get("single_source_gate") != "PASS_SOURCE"
            or manifest.get("provider_count") != 1
            or manifest.get("authoritative_calendar_provider") != "API-Football"
            or manifest.get("safe_to_publish_play") is not False):
        raise ValueError("Only canonical API-Football two-day calendar is allowed")
    dates = manifest.get("dates")
    if (not isinstance(dates, list) or len(dates) != 2
            or len(set(dates)) != 2 or not isinstance(calendars, dict)
            or set(calendars) != set(dates)):
        raise ValueError("Expected exactly two canonical Warsaw dates")
    for day in dates:
        doc = calendars[day]
        if (not isinstance(doc, dict) or doc.get("schema") != DAY_SCHEMA
                or doc.get("date") != day or doc.get("source") != "API-Football"
                or doc.get("single_source_gate") != "PASS_SOURCE"
                or doc.get("safe_to_publish_play") is not False
                or not isinstance(doc.get("provider_events"), list)
                or not isinstance(doc.get("candidates"), list)
                or doc.get("pre_match_fixtures") != len(doc["candidates"])
                or doc.get("provider_total_events") != len(doc["provider_events"])
                or _iso_datetime(doc.get("snapshot_utc")) is None):
            raise ValueError("Malformed canonical calendar date")
        all_events = {}
        for event in doc["provider_events"]:
            if not isinstance(event, dict):
                raise ValueError("Invalid canonical provider event")
            fid = event.get("fixture_id")
            if (type(fid) is not int or fid <= 0 or fid in all_events):
                raise ValueError("Duplicate canonical event identity")
            all_events[fid] = event
        seen = set()
        for event in doc["candidates"]:
            fid = event.get("fixture_id") if isinstance(event, dict) else None
            kickoff = _iso_datetime(event.get("kickoff_utc")) if isinstance(event, dict) else None
            if (fid in seen or all_events.get(fid) != event or kickoff is None
                    or kickoff.astimezone(WARSAW).date().isoformat() != day
                    or event.get("provider") != "API-Football" or event.get("status") != "NS"
                    or event.get("eligible_for_prematch_research") is not True):
                raise ValueError("Noncanonical candidate in fixture universe")
            seen.add(fid)
    return dates


def build(manifest, calendars, pitch_docs, *, now=None):
    now = _clock(now)
    days = _canonical(manifest, calendars)
    if not isinstance(pitch_docs, dict) or not set(pitch_docs).issubset(set(days)):
        raise ValueError("Unexpected PitchAPI date / source")
    outputs = []
    usable = 0
    possible = 0
    for day in days:
        candidates = calendars[day]["candidates"]
        doc = pitch_docs.get(day)
        archive, captured, source_status = (
            _snapshot(doc, day, now) if doc is not None
            else (None, None, "NO_SAVED_PITCHAPI_PREMATCH_ARCHIVE")
        )
        choices = {}
        matched_to = {}
        if archive is not None:
            for source in candidates:
                sid = source["fixture_id"]
                kickoff = _iso_datetime(source["kickoff_utc"])
                possibles = [
                    p for p in archive
                    if norm(source["home"]) == norm(p["home"])
                    and norm(source["away"]) == norm(p["away"])
                    and competition(source["league"]) == competition(p["league"])
                    and abs(kickoff-_iso_datetime(p["kickoff_utc"])) <= MAX_TIME_DIFFERENCE
                ]
                choices[sid] = possibles
                if len(possibles) == 1:
                    matched_to.setdefault(possibles[0]["pitch_match_id"], []).append(sid)
        rows = []
        for source in candidates:
            sid = source["fixture_id"]
            kickoff = _iso_datetime(source["kickoff_utc"])
            result = {
                "fixture_id": sid,
                "fixture": source["home"] + " – " + source["away"],
                "league": source["league"], "date_warsaw": day,
                "kickoff_utc": source["kickoff_utc"],
                "calendar_source": "API-Football",
                "xg_source": "PitchAPI" if archive is not None else None,
                "snapshot_utc": captured.isoformat() if captured else None,
                "pitch_match_id": None,
                "status": source_status if archive is None else "NOT_MATCHED_IN_PITCHAPI_SNAPSHOT",
                "home_xg": None, "away_xg": None,
                "original_kb21_p_model": None, "str_35": None,
                "qual_35": None, "match_30": None, "odds": None,
                "selection": None, "ev": None, "safe_to_publish_play": False,
            }
            if archive is not None:
                links = choices[sid]
                if len(links) > 1:
                    result["status"] = "AMBIGUOUS_PITCHAPI_FIXTURE_MATCH"
                elif len(links) == 1:
                    match = links[0]
                    mid = match["pitch_match_id"]
                    result["pitch_match_id"] = mid
                    if len(matched_to[mid]) != 1:
                        result["status"] = "PITCHAPI_FIXTURE_SHARED_BY_MULTIPLE_CANONICAL_IDS"
                    elif captured >= kickoff or kickoff <= now:
                        result["status"] = "NOT_VERIFIABLY_PREMATCH_AT_BRIDGE"
                    else:
                        h = _validate_recent(match.get("home_recent"), captured, mid)
                        a = _validate_recent(match.get("away_recent"), captured, mid)
                        if h is None or a is None or match.get("both_sides_sufficient") is not True:
                            result["status"] = "INSUFFICIENT_OR_UNVERIFIED_HISTORICAL_XG"
                        else:
                            result.update(home_xg=h, away_xg=a,
                                          status="VERIFIED_PREMATCH_HISTORICAL_XG")
                            usable += 1
                    possible += 1
            rows.append(result)
        outputs.append({
            "date": day, "source_status": source_status,
            "canonical_candidates": len(candidates),
            "verified_xg_matches": sum(
                r["status"] == "VERIFIED_PREMATCH_HISTORICAL_XG" for r in rows),
            "records": rows,
        })
    return {
        "schema": SCHEMA, "dates": days, "generated_at_utc": now.isoformat(),
        "authoritative_fixture_calendar": "API-Football",
        "optional_xg_archive_provider": "PitchAPI",
        "external_api_calls": 0,
        "calendar_candidates": sum(x["canonical_candidates"] for x in outputs),
        "matches_with_verified_prematch_xg": usable,
        "uniquely_matched_candidates": possible,
        "days": outputs, "automatic_str_qual_match_count": 0,
        "automatic_p_model_count": 0, "original_kb21_n_effect": 0,
        "register_writes": False, "safe_to_publish_play": False,
        "note": "PitchAPI archive is historical xG ONLY, not modelled expected goals for the target game. "
                "Missing or late archive cannot produce values; any ambiguous join is rejected. "
                "No bookmaker recommendation, CORE score or P(model) is generated.",
    }


def render_day(day):
    lines = [
        "# KB Score 2.1 – zweryfikowane wcześniejsze xG / " + day["date"], "",
        "**DANE BADAWCZE PITCHAPI, NIE P(model), ELO, KURS LUB TYP.**",
        f"Archiwum: {day['source_status']}. "
        f"Rzeczywiste wcześniejsze xG dla {day['verified_xg_matches']} "
        f"z {day['canonical_candidates']} meczów.", "",
        "| Godzina UTC | Mecz z terminarza API-Football | xG / xGA G | xG / xGA W | Stan |",
        "|---|---|---:|---:|---|",
    ]
    for row in day["records"]:
        h,a = row["home_xg"],row["away_xg"]
        fmt = lambda x: f"{x['mean_xg_for']:.2f} / {x['mean_xg_against']:.2f} ({x['sample_size']} FT)" if x else "brak"
        lines.append(
            f"| {row['kickoff_utc'][11:16]} | {row['fixture']} | "
            f"{fmt(h)} | {fmt(a)} | {row['status']} |")
    if not day["records"]:
        lines.append("| – | Brak kandydatów API-Football | – | – | – |")
    lines.extend([
        "", "Średnie z wcześniejszych meczów, nie prognoza xG przyszłego meczu. "
        "Ręczna ocena STR/35, QUAL/35, MATCH/30 oraz P(model) pozostaje pusta. "
        "Nie używać do automatycznego PLAY, nie dopisywać do historycznego N.", "",
    ])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--calendar-dir", required=True)
    p.add_argument("--pitch-dir", default="data/pitchapi/prematch")
    p.add_argument("--output-dir", required=True)
    a = p.parse_args()
    root = Path(a.calendar_dir)
    m = json.loads((root/"SINGLE_SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    c = {d: json.loads((root/("KB21_API_CALENDAR_"+d+".json")).read_text(encoding="utf-8"))
         for d in m["dates"]}
    snapshots={}
    for d in m["dates"]:
        file=Path(a.pitch_dir)/(d+".json")
        if file.is_file():
            snapshots[d]=json.loads(file.read_text(encoding="utf-8"))
    report=build(m,c,snapshots)
    out=Path(a.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    (out/"KB21_PREODDS_XG_MANIFEST.json").write_text(
        json.dumps({k:v for k,v in report.items() if k!="days"},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    for day in report["days"]:
        title="KB21_PREODDS_XG_"+day["date"]
        (out/(title+".json")).write_text(
            json.dumps(day,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (out/(title+".md")).write_text(render_day(day),encoding="utf-8")
    print("KB21 pregame PitchAPI xG",report["matches_with_verified_prematch_xg"],
          "/",report["calendar_candidates"],"canonical games",
          "; API calls:",report["external_api_calls"],
          "; original P(model): NULL; PLAY: NO")


if __name__=="__main__":
    main()
