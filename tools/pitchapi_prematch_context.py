#!/usr/bin/env python3
"""PitchAPI pre-match xG context (NO SCORE MODIFICATION, NO future leakage).

Historical rolling xG / xGA for fixtures scheduled on a requested day.
Used for review alongside API Market and KB21, never as automatic scores.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import json
import os
from zoneinfo import ZoneInfo

try:
    from tools.pitchapi_xg_lab import collect_match, competition, field, norm, write_json
except ModuleNotFoundError as exc:
    if exc.name != "tools":
        raise
    # Also support legacy entrypoints executed as 'python tools/file.py'.
    from pitchapi_xg_lab import collect_match, competition, field, norm, write_json

PRIORITY = {
    "uefa champions league", "uefa europa league", "uefa conference league",
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "ekstraklasa", "primeira liga", "eredivisie", "jupiler pro league", "super lig"
}

def utc(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def eligible_past_match(m, team_id, cutoff):
    t = utc(field(m, "time_utc"))
    if not t or not t < cutoff:
        return False
    if str(field(m, "status", "")).lower() not in ("finished", "ft", "aet", "pen"):
        return False
    return team_id in (field(field(m, "home_team"), "id"), field(field(m, "away_team"), "id"))

def find_recent(league_games, team_id, cutoff, count=5):
    matching = [m for m in league_games if eligible_past_match(m, team_id, cutoff)]
    return sorted(matching, key=lambda m: utc(field(m, "time_utc")), reverse=True)[:count]

def build_team_sample(games, team_id, cache, collector, *, minimum=3):
    entries = []
    for match in games:
        mid = field(match, "id")
        if mid not in cache:
            try:
                cache[mid] = collector(match)
            except Exception:
                cache[mid] = None
        matchdata = cache[mid]
        if not matchdata:
            continue
        side = ("home" if matchdata["home_team_id"] == team_id else
                "away" if matchdata["away_team_id"] == team_id else None)
        if side is None:
            continue
        other = "away" if side == "home" else "home"
        own = matchdata["xg_" + side]
        conceded = matchdata["xg_" + other]
        if not (own["xg_complete"] and conceded["xg_complete"]):
            continue
        entries.append({"match_id": mid, "kickoff_utc": field(match, "time_utc"),
                        "xg_for": own["xg"], "xg_against": conceded["xg"]})
    n = len(entries)
    enough = n >= minimum
    return {"complete_samples": n, "requested_samples": len(games),
            "data_quality": ("sufficient" if enough else "insufficient"),
            "mean_xg_for": round(sum(x["xg_for"] for x in entries)/n, 3) if enough else None,
            "mean_xg_against": round(sum(x["xg_against"] for x in entries)/n, 3) if enough else None,
            "source_match_ids": [e["match_id"] for e in entries],
            "samples": entries}

def lookup_context(report, home, away, league=None, kickoff=None):
    """Safe one-to-one pairing for displaying xG alongside a separately verified fixture."""
    possibles = []
    for item in report.get("fixtures", []):
        if norm(item.get("home")) != norm(home) or norm(item.get("away")) != norm(away):
            continue
        if league and competition(item.get("league")) != competition(league):
            continue
        a, b = utc(item.get("kickoff_utc")), utc(kickoff)
        if a and b and abs((a-b).total_seconds()) > 6*3600:
            continue
        possibles.append(item)
    return possibles[0] if len(possibles) == 1 else None

def collect(target, client, now, maximum=45):
    assert target > now.astimezone(ZoneInfo("Europe/Warsaw")).date(), "Prematch-only requested day must be future"
    fixtures = list(client.date.get(target.isoformat(), status="upcoming").matches)
    fixtures = [m for m in fixtures if utc(field(m, "time_utc")) and utc(field(m, "time_utc")) > now]
    fixtures.sort(key=lambda m: (
        0 if competition(field(field(m, "league"), "name")) in PRIORITY else 1,
        str(field(m, "time_utc", "")), str(field(m, "id", ""))))
    fixture_limit = fixtures[:maximum]
    league_map = {}
    history_errors = []
    for m in fixture_limit:
        league_id = field(field(m, "league"), "id")
        if league_id in league_map:
            continue
        try:
            lg = client.leagues.matches(league_id, status="all")
            league_map[league_id] = list(lg.matches)
        except Exception as exc:
            league_map[league_id] = []
            history_errors.append({"league_id": league_id, "type": type(exc).__name__})
    league_country_codes = {}
    for league_id in league_map:
        try:
            detail = client.leagues.get(league_id)
            code = field(detail, "country_code")
            league_country_codes[league_id] = code.strip().upper() if isinstance(code, str) and code.strip() else None
        except Exception as exc:
            league_country_codes[league_id] = None
            history_errors.append({"league_id": league_id, "operation": "league_country_code", "type": type(exc).__name__})
    cache = {}
    records = []
    league_country_diagnostics = {}
    for m in fixture_limit:
        kickoff = utc(field(m, "time_utc"))
        cutoff = min(kickoff, now)
        lid = field(field(m, "league"), "id")
        country_code = league_country_codes.get(lid)
        league_country_diagnostics[str(lid)] = dict(
            league=field(field(m, "league"), "name"),
            country_code_present=country_code is not None,
            country_code=country_code)
        all_history = league_map.get(lid, [])
        samples = {}
        for side in ("home", "away"):
            team = field(m, side + "_team")
            tid = field(team, "id")
            recent = find_recent(all_history, tid, cutoff, count=5)
            samples[side] = build_team_sample(
                recent, tid, cache, lambda past: collect_match(past, client))
        records.append({
            "pitch_match_id": field(m, "id"), "league": field(field(m, "league"), "name"),
            "league_id": lid, "country_code": country_code,
            "home": field(field(m, "home_team"), "name"),
            "away": field(field(m, "away_team"), "name"), "kickoff_utc": field(m, "time_utc"),
            "home_recent": samples["home"], "away_recent": samples["away"],
            "both_sides_sufficient": (samples["home"]["data_quality"] == "sufficient" and
                                      samples["away"]["data_quality"] == "sufficient")})
    return {"schema": "pitchapi-prematch-context-v1", "target_date": target.isoformat(),
            "snapshot_utc": now.isoformat(), "source": "PitchAPI",
            "available_upcoming": len(fixtures), "fixtures_collected": len(records),
            "fixtures_with_both_sides_sufficient": sum(r["both_sides_sufficient"] for r in records),
            "league_errors": history_errors, "league_country_diagnostics": league_country_diagnostics,
            "fixtures": records,
            "model_effect": "NONE", "kb_n_effect": 0, "dev_n_effect": 0,
            "important": "Historic xG averages, not predicted goals or betting probabilities. "
                         "Only fixtures played BEFORE snapshot enter samples."}

def render(payload):
    d = payload["target_date"]
    out = [f"# PitchAPI — przedmeczowy kontekst xG: {d}", "",
           "**DODATKOWE DANE DLA API MARKET I KB SCORE 2.1 — BEZ ZMIANY PUNKTACJI**", "",
           f"Snapshot UTC: `{payload['snapshot_utc']}`",
           f"Mecze PitchAPI: {payload['fixtures_collected']} / {payload['available_upcoming']}; "
           f"obustronnie wystarczająca historia: {payload['fixtures_with_both_sides_sufficient']}.", "",
           "xG/xGA poniżej to średnie z maksymalnie **5 wcześniejszych meczów w tych samych rozgrywkach**. "
           "Nie są przewidywanymi golami, prawdopodobieństwami ani sygnałami do zmiany oceny 67/100.", "",
           "| Mecz | xG gospodarze | xGA gospodarze | xG goście | xGA goście | Próba (G/W) |",
           "|---|---:|---:|---:|---:|---:|"]
    for f in payload["fixtures"]:
        h,a=f["home_recent"],f["away_recent"]
        show=lambda v: "—" if v is None else f"{v:.2f}"
        out.append(f"| {f['home']} – {f['away']} ({f['league']}) | "
                   f"{show(h['mean_xg_for'])} | {show(h['mean_xg_against'])} | "
                   f"{show(a['mean_xg_for'])} | {show(a['mean_xg_against'])} | "
                   f"{h['complete_samples']}/{a['complete_samples']} |")
    out += ["", "Brak liczby oznacza zbyt małą próbę (poniżej 3 meczów), a nie xG=0.",
            "Brak gwarancji pełnej historii między rozgrywkami; ten raport nie zastępuje klasyfikacji KB Score.",
            "Nie używać danych rozegranych po chwili wykonania analizy.", ""]
    return "\n".join(out)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (default tomorrow in Warsaw)")
    parser.add_argument("--max-fixtures", type=int, default=45)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Europe/Warsaw")).date()
    target = date.fromisoformat(args.date) if args.date else today+timedelta(days=1)
    if not 1 <= args.max_fixtures <= 80:
        parser.error("max-fixtures range 1..80")
    if not os.getenv("PITCHAPI_API_KEY"):
        raise SystemExit("Missing PITCHAPI_API_KEY GitHub secret")
    from pitchapi import PitchAPI
    with PitchAPI() as client:
        payload = collect(target, client, now, maximum=args.max_fixtures)
    path = Path("data/pitchapi/prematch") / f"{target.isoformat()}.json"
    write_json(path, payload)
    doc = Path("reports/pitchapi/prematch") / f"{target.isoformat()}.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(render(payload), encoding="utf-8")
    print(json.dumps({"target": str(target), "available": payload["available_upcoming"],
                      "fixtures": payload["fixtures_collected"],
                      "both_sides_sufficient": payload["fixtures_with_both_sides_sufficient"],
                      "report": str(doc), "model_effect": "NONE"}, ensure_ascii=False))
if __name__ == "__main__":
    main()
