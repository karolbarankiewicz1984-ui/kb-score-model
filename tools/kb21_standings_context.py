"""Current-season league-table and prior-opponent evidence for KB21 research.

The TWO-DAY fixture universe stays strictly API-Football only.
Standings are an optional contextual endpoint, not a second calendar.
Current-season table rank/PPG is NOT Elo, xG, strength-adjusted P(model)
or a bookmaker bet. Teams are joined ONLY by exact provider IDs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

from tools.api_market_http import ApiClient
from tools.kb21_api_prematch import DOMESTIC
from tools.kb21_single_source_calendar import BASE, DAY_SCHEMA, SCHEMA as CALENDAR_SCHEMA, _iso_datetime
from tools.kb21_single_source_form import OUT_SCHEMA as FORM_SCHEMA

SCHEMA = "kb21-league-opponent-context-v1"
MAX_STANDINGS_CALLS = 16
DAILY_RESERVE = 25


def _positive(value):
    return type(value) is int and value > 0


def _nonnegative(value):
    return type(value) is int and value >= 0


def _clock(now):
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("Capture requires timezone-aware UTC time")
    return now.astimezone(timezone.utc)


def parse_standings(payload, league_id, season):
    """Reject malformed or ambiguous table structures; never invent missing rows."""
    if not isinstance(payload, dict):
        return None, "MALFORMED_PROVIDER_RESPONSE"
    if payload.get("errors") not in ([], {}):
        return None, "PROVIDER_ERROR"
    if payload.get("get") != "standings":
        return None, "WRONG_PROVIDER_ENDPOINT"
    params = payload.get("parameters")
    if not isinstance(params, dict) or str(params.get("league")) != str(league_id) or str(params.get("season")) != str(season):
        return None, "WRONG_LEAGUE_OR_SEASON"
    items = payload.get("response")
    if not isinstance(items, list) or len(items) > 3:
        return None, "MALFORMED_PROVIDER_RESPONSE"
    if not items:
        return None, "STANDINGS_NOT_AVAILABLE"
    tables = {}
    for response in items:
        league = response.get("league") if isinstance(response, dict) else None
        if (not isinstance(league, dict) or league.get("id") != league_id
                or league.get("season") != season):
            return None, "WRONG_LEAGUE_OR_SEASON"
        groups = league.get("standings")
        if not isinstance(groups, list) or len(groups) > 40:
            return None, "MALFORMED_PROVIDER_RESPONSE"
        for group_index, group in enumerate(groups):
            if not isinstance(group, list) or len(group) > 50:
                return None, "MALFORMED_PROVIDER_RESPONSE"
            for item in group:
                if not isinstance(item, dict) or not isinstance(item.get("team"), dict):
                    return None, "MALFORMED_PROVIDER_RESPONSE"
                team_id = item["team"].get("id")
                rank, points = item.get("rank"), item.get("points")
                totals = item.get("all")
                if not isinstance(totals, dict):
                    return None, "MALFORMED_PROVIDER_RESPONSE"
                played = totals.get("played")
                w, d, l = totals.get("win"), totals.get("draw"), totals.get("lose")
                gd = item.get("goalsDiff")
                if (not _positive(team_id) or team_id in tables
                        or not _positive(rank)
                        or not _nonnegative(played) or not _nonnegative(points)
                        or not all(_nonnegative(v) for v in (w,d,l))
                        or w+d+l != played or points > 3*played
                        or type(gd) is not int):
                    return None, "MALFORMED_PROVIDER_RESPONSE"
                home, away = {}, {}
                for side, into in (("home", home), ("away", away)):
                    section = item.get(side)
                    if not isinstance(section, dict):
                        continue
                    games = section.get("played")
                    wins, draws, losses = section.get("win"), section.get("draw"), section.get("lose")
                    if (_nonnegative(games) and all(_nonnegative(x) for x in (wins,draws,losses))
                            and games == wins+draws+losses and games <= played):
                        into.update(played=games,wins=wins,draws=draws,losses=losses,
                                    points_per_game=round((3*wins+draws)/games,3) if games else None)
                tables[team_id] = {
                    "team_id": team_id, "team_name": item["team"].get("name"),
                    "group_index": group_index, "rank": rank,
                    "points": points, "played": played,
                    "points_per_game": round(points/played, 3) if played else None,
                    "goal_difference": gd,
                    "home": home or None, "away": away or None,
                    "source": "API-Football current-season standings snapshot",
                }
    if not tables:
        return None, "STANDINGS_NOT_AVAILABLE"
    return tables, "OK"


def _opponents(side, league_id, season, table, group):
    """Current strength of KNOWN same-league opponents; NOT strength at past kickoff."""
    e = side.get("sport_evidence") if isinstance(side, dict) else None
    history = e.get("previous_ft_matches") if isinstance(e, dict) else None
    if not isinstance(history, list):
        return {"qualified_last_five": 0, "sampled_last_five": 0,
                "mean_current_opponent_ppg": None, "matches": []}
    selected = history[:5]
    found = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        if item.get("history_league_id") != league_id or item.get("history_season") != season:
            continue
        rival = table.get(item.get("opponent_team_id"))
        if (rival is None or rival["group_index"] != group
                or rival.get("points_per_game") is None):
            continue
        found.append({"fixture_id": item["fixture_id"],
                      "opponent_team_id": rival["team_id"],
                      "opponent_current_rank": rival["rank"],
                      "opponent_current_ppg": rival["points_per_game"]})
    return {
        "qualified_last_five": len(found),
        "sampled_last_five": len(selected),
        "mean_current_opponent_ppg": round(sum(x["opponent_current_ppg"] for x in found)/len(found),3) if found else None,
        "matches": found,
        "warning": "Current-season opponent PPG at present snapshot, NOT their rating at historical fixture kickoff",
    }


def build(calendar_manifest, calendars, form_manifest, forms, client, key,
          now=None, max_calls=MAX_STANDINGS_CALLS, reserve=DAILY_RESERVE):
    now = _clock(now or datetime.now(timezone.utc))
    if (not key or type(max_calls) is not int or not 1 <= max_calls <= MAX_STANDINGS_CALLS
            or type(reserve) is not int or not 0 <= reserve <= 1000):
        raise ValueError("Valid key and strict capped standings budget required")
    if (not isinstance(calendar_manifest, dict)
            or calendar_manifest.get("schema") != CALENDAR_SCHEMA
            or calendar_manifest.get("source_of_truth_rule") is None
            or calendar_manifest.get("provider_count") != 1
            or calendar_manifest.get("single_source_gate") != "PASS_SOURCE"
            or calendar_manifest.get("safe_to_publish_play") is not False
            or calendar_manifest.get("authoritative_calendar_provider") != "API-Football"):
        raise ValueError("Invalid canonical calendar")
    days = calendar_manifest.get("dates")
    if (not isinstance(days, list) or len(days) != 2 or len(set(days)) != 2
            or not isinstance(form_manifest, dict)
            or form_manifest.get("schema") != FORM_SCHEMA
            or form_manifest.get("source") != "API-Football"
            or form_manifest.get("safe_to_publish_play") is not False
            or form_manifest.get("scoring_fields_filled_automatically") != 0
            or form_manifest.get("dates") != days
            or set(calendars) != set(days) or set(forms) != set(days)):
        raise ValueError("Invalid saved forms/calendar provenance")
    src_time = _iso_datetime(calendar_manifest.get("generated_at_utc"))
    form_time = _iso_datetime(form_manifest.get("generated_at_utc"))
    if not src_time or not form_time or not src_time <= form_time <= now:
        raise ValueError("Never join a future-dated evidence snapshot")
    fixtures = []
    for day in days:
        cal, form = calendars[day], forms[day]
        if (cal.get("schema") != DAY_SCHEMA or cal.get("date") != day
                or cal.get("source") != "API-Football"
                or cal.get("single_source_gate") != "PASS_SOURCE"
                or cal.get("safe_to_publish_play") is not False
                or cal.get("pre_match_fixtures") != len(cal.get("candidates", []))
                or form.get("day") != day or not isinstance(form.get("matches"), list)):
            raise ValueError("Invalid same-day calendar/form")
        src = {}
        for row in cal["candidates"]:
            ident = row.get("fixture_id") if isinstance(row, dict) else None
            if not _positive(ident) or ident in src:
                raise ValueError("Invalid/duplicate match in provider calendar")
            src[ident] = row
        seen = set()
        for item in form["matches"]:
            ident = item.get("fixture_id") if isinstance(item, dict) else None
            canonical = src.get(ident)
            if (not _positive(ident) or ident in seen or canonical is None
                    or item.get("home_team_id") != canonical.get("home_team_id")
                    or item.get("away_team_id") != canonical.get("away_team_id")
                    or item.get("event") != canonical.get("home") + " – " + canonical.get("away")
                    or item.get("kickoff_utc") != canonical.get("kickoff_utc")
                    or item.get("odds") is not None or item.get("selection") is not None
                    or item.get("safe_to_publish_play") is not False
                    or item.get("analyst_assessment",{}).get("P_model_pre_odds") is not None):
                raise ValueError("Form fixture not identical to canonical provider calendar")
            seen.add(ident)
        for ident, fixture in src.items():
            attached = next((f for f in form["matches"] if f["fixture_id"] == ident), None)
            fixtures.append((day, fixture, attached))
    needed = {}
    for _, fixture, _ in fixtures:
        key_pair = fixture.get("country"), fixture.get("league")
        lid, season = fixture.get("league_id"), fixture.get("season")
        if (key_pair in DOMESTIC and _positive(lid) and type(season) is int
                and 2000 <= season <= 2100):
            needed[(lid,season)] = key_pair
    fetched, requests, status, remain = {}, 0, {}, None
    stop = None
    for pair in sorted(needed):
        if requests >= max_calls:
            status[pair] = "CALL_BUDGET_EXCEEDED"
            continue
        if stop:
            status[pair] = stop
            continue
        try:
            payload, headers = client.get(BASE, key, "standings", league=pair[0], season=pair[1])
            requests += 1
            result, state = parse_standings(payload,*pair)
            fetched[pair] = result
            status[pair] = state
            raw = headers.get("x-ratelimit-requests-remaining") if isinstance(headers,dict) else None
            if raw is not None:
                try:
                    remain = int(raw)
                except (TypeError, ValueError):
                    stop = "QUOTA_HEADER_INVALID"
                else:
                    if remain <= reserve:
                        stop = "DAILY_QUOTA_RESERVE_REACHED"
        except Exception:
            # Optional enrichment failure cannot block the canonical fixture
            # source. Do not expose auth headers or fabricate standings.
            requests += 1
            status[pair] = "STANDINGS_REQUEST_FAILED"
            fetched[pair] = None
            stop = "STOP_AFTER_PROVIDER_REQUEST_FAILURE"
    outputs = []
    for day in days:
        matches = []
        for _, fixture, form in (x for x in fixtures if x[0] == day):
            ident = fixture["fixture_id"]
            kickoff = _iso_datetime(fixture.get("kickoff_utc"))
            entry = {
                "fixture_id":ident, "fixture":fixture["home"]+" – "+fixture["away"],
                "kickoff_utc":fixture["kickoff_utc"], "competition":fixture["league"],
                "season":fixture.get("season"), "source": "API-Football",
                "standings_snapshot_utc": now.isoformat(),
                "status": "NO_LEAGUE_TABLE",
                "home": None, "away": None, "current_rank_gap": None,
                "current_ppg_gap_home_minus_away": None,
                "recent_opponent_context": None,
                "elo": None, "xg": None, "str_35": None, "qual_35": None,
                "match_30": None, "original_p_model": None,
                "odds": None, "decision": None, "safe_to_publish_play": False,
            }
            pair=(fixture.get("league_id"), fixture.get("season"))
            if (fixture.get("country"), fixture.get("league")) not in DOMESTIC:
                entry["status"]="NOT_A_DOMESTIC_TABLE_MATCH"
            elif kickoff is None or kickoff <= now:
                entry["status"]="NO_LATE_SNAPSHOT_AFTER_KICKOFF"
            elif pair not in fetched or fetched[pair] is None:
                entry["status"]=status.get(pair, "STANDINGS_NOT_AVAILABLE")
            else:
                table = fetched[pair]
                home = table.get(fixture.get("home_team_id"))
                away = table.get(fixture.get("away_team_id"))
                if not home or not away:
                    entry["status"]="ONE_OR_BOTH_TEAMS_MISSING_FROM_STANDINGS"
                elif home["group_index"] != away["group_index"]:
                    entry["status"]="TEAMS_IN_DIFFERENT_GROUPS"
                elif home["points_per_game"] is None or away["points_per_game"] is None:
                    entry["status"]="INSUFFICIENT_LEAGUE_GAMES"
                else:
                    entry.update(status="CURRENT_SEASON_TABLE_CONTEXT",
                                 home=home, away=away,
                                 current_rank_gap=away["rank"]-home["rank"],
                                 current_ppg_gap_home_minus_away=round(
                                     home["points_per_game"]-away["points_per_game"],3))
                    if form:
                        entry["recent_opponent_context"] = {
                            side: _opponents(form["history"][side],pair[0],pair[1],
                                             table,home["group_index"])
                            for side in ("home","away")
                        }
            matches.append(entry)
        outputs.append({"date":day, "matches":matches})
    return {
        "schema":SCHEMA, "dates":days, "generated_at_utc":now.isoformat(),
        "calendar_provider":"API-Football", "standings_provider":"API-Football",
        "standings_endpoint":"/standings?league=ID&season=YEAR",
        "source_of_truth_for_fixtures":"UNCHANGED_SINGLE_PROVIDER",
        "standings_calls":requests, "standings_calls_limit":max_calls,
        "daily_api_reserve":reserve, "daily_api_remaining":remain,
        "standings_groups_status":{
            f"{lid}:{season}":status.get((lid,season),"NOT_QUERIED")
            for lid,season in sorted(needed)
        }, "days_output":outputs,
        "candidate_matches":len(fixtures),
        "verified_table_pairs":sum(m["status"]=="CURRENT_SEASON_TABLE_CONTEXT"
                                   for d in outputs for m in d["matches"]),
        "automatic_str_qual_match_count":0, "automatic_p_model_count":0,
        "kb21_n_effect":0,"register_writes":False,
        "safe_to_publish_play":False,
        "note":"League table points/PPG are not ClubElo, xG or historical KB21 ratings. "
               "All comparisons are snapshot-time current-season context; "
               "opponent PPG is NOT point-in-time at the historical match.",
    }


def render_day(day):
    lines=["# KB21 / kontekst siły w bieżącej lidze / "+day["date"],"",
           "**FAKTY Z TABELI, NIE ELO / xG / P(model) / TYP.**","",
           "| Mecz | Tabela | Dom (poz.; pkt/mecz) | Wyjazd (poz.; pkt/mecz) |",
           "|---|---|---|---|"]
    for m in day["matches"]:
        h,a=m["home"],m["away"]
        desc=lambda x: f"{x['rank']}; {x['points_per_game']:.2f}" if x else "—"
        lines.append(f"| {m['fixture']} | {m['status']} | {desc(h)} | {desc(a)} |")
    lines += ["", "Pozycje w bieżącym sezonie nie są ELO. "
              "Ocena dawnych rywali to ich OBECNY pkt/mecz, nie historyczna "
              "siła z dnia wcześniejszego spotkania. "
              "Puste pola nie są zerem; oceny KB Score pozostają nieustalone.", ""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--calendar-dir",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--max-calls",type=int,default=MAX_STANDINGS_CALLS)
    p.add_argument("--reserve-daily",type=int,default=DAILY_RESERVE)
    args=p.parse_args()
    root=Path(args.calendar_dir)
    m=json.loads((root/"SINGLE_SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    fm=json.loads((root/"KB21_FORM_MANIFEST.json").read_text(encoding="utf-8"))
    calendars={d:json.loads((root/("KB21_API_CALENDAR_"+d+".json")).read_text(encoding="utf-8")) for d in m["dates"]}
    forms={d:json.loads((root/("KB21_FORM_"+d+".json")).read_text(encoding="utf-8")) for d in m["dates"]}
    key=os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("API_FOOTBALL_KEY missing; cannot capture actual league standings")
    doc=build(m,calendars,fm,forms,ApiClient(),key,
              max_calls=args.max_calls,reserve=args.reserve_daily)
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"KB21_STANDINGS_CONTEXT_MANIFEST.json").write_text(
        json.dumps({k:v for k,v in doc.items() if k!="days_output"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for day in doc["days_output"]:
        name="KB21_STANDINGS_CONTEXT_"+day["date"]
        (out/(name+".json")).write_text(json.dumps(day,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (out/(name+".md")).write_text(render_day(day),encoding="utf-8")
    print("KB21 current-season tables:",doc["verified_table_pairs"],"/",doc["candidate_matches"],
          "fixtures; calls",doc["standings_calls"],"/",doc["standings_calls_limit"],
          "; provider daily remaining",doc["daily_api_remaining"],"; original P(model)=null; PLAY=NO")


if __name__=="__main__":
    main()
