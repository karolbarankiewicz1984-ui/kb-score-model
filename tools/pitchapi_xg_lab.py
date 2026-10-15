#!/usr/bin/env python3
"""Isolated post-match PitchAPI xG collector and conservative API-Football join.

Historical data only. NEVER modify KB Score, predictions, parameters, or N counters.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import unicodedata

ISOLATION = "POSTMATCH_DATA_ONLY_NO_KB_OR_DEV_WRITES"

def field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

def valid_xg(v):
    return type(v) in (float, int) and 0 <= v <= 1

def collect_match(match, client):
    home, away = field(match, "home_team"), field(match, "away_team")
    h_id, a_id = field(home, "id"), field(away, "id")
    b = {h_id: {"n": 0, "xg": [], "xgot": []}, a_id: {"n": 0, "xg": [], "xgot": []}}
    error = None
    if not h_id or not a_id or h_id == a_id:
        error = "invalid_team_ids"
    else:
        try:
            response = client.matches.shots(field(match, "id"))
            seen = set()
            for period in field(response, "periods", []) or []:
                for s in field(period, "shots", []) or []:
                    sid = field(s, "id")
                    if sid and sid in seen:
                        continue
                    if sid:
                        seen.add(sid)
                    team = field(s, "team_id")
                    if team not in b:
                        error = "unrecognized_shot_team"
                        continue
                    bucket = b[team]
                    bucket["n"] += 1
                    if valid_xg(field(s, "expected_goals")):
                        bucket["xg"].append(float(field(s, "expected_goals")))
                    if valid_xg(field(s, "expected_goals_on_target")):
                        bucket["xgot"].append(float(field(s, "expected_goals_on_target")))
        except Exception as exc:
            # Log no API exception contents: these may contain auth metadata.
            error = type(exc).__name__

    def summary(team):
        row = b.get(team, {"n": 0, "xg": [], "xgot": []})
        complete = error is None and row["n"] > 0 and row["n"] == len(row["xg"])
        return {"shot_count": row["n"], "shots_with_xg": len(row["xg"]),
                "xg": round(sum(row["xg"]), 5) if complete else None,
                "xg_complete": complete,
                "xgot": round(sum(row["xgot"]), 5) if row["xgot"] else None,
                "shots_with_xgot": len(row["xgot"])}
    league = field(match, "league")
    return {"pitch_match_id": field(match, "id"), "date": field(match, "date"),
            "kickoff_utc": field(match, "time_utc"), "league": field(league, "name"),
            "league_id": field(league, "id"), "home": field(home, "name"),
            "away": field(away, "name"), "home_team_id": h_id, "away_team_id": a_id,
            "goals_home": field(match, "score_home"), "goals_away": field(match, "score_away"),
            "status": field(match, "status"), "xg_home": summary(h_id),
            "xg_away": summary(a_id), "shots_error": error}

def norm(v):
    x = str(v or "").casefold().replace("ø", "o").replace("ł", "l").replace("ß", "ss")
    x = "".join(c for c in unicodedata.normalize("NFKD", x) if not unicodedata.combining(c))
    x = re.sub(r"[^a-z0-9]+", " ", x).strip()
    aliases = {"psg": "paris saint germain", "paris sg": "paris saint germain",
               "as roma": "roma", "fc porto": "porto",
               "lask linz": "lask", "aek athens fc": "aek athens",
               "coventry city": "coventry", "newcastle united": "newcastle",
               "club brugge kv": "club brugge", "sabah fa": "sabah",
               "sabah fk": "sabah", "slavia praha": "slavia prague",
               "bayern munchen": "bayern munich", "man utd": "manchester united",
               "man city": "manchester city", "inter milan": "internazionale",
               "inter": "internazionale", "sporting cp": "sporting lisbon",
               "sporting": "sporting lisbon"}
    return aliases.get(x, x)

def competition(name):
    x = norm(name)
    groups = {
        "uefa champions league": ("champions league", "uefa champions league"),
        "uefa europa league": ("europa league", "uefa europa league"),
        "uefa conference league": ("conference league", "uefa conference league", "uefa europa conference league"),
        "la liga": ("la liga", "laliga"),
        "primeira liga": ("primeira liga", "liga portugal"),
    }
    for canonical, variants in groups.items():
        if x in variants:
            return canonical
    return x

def confidence(p, a):
    if competition(p.get("league")) != competition(a.get("league")):
        return None
    hp, ap = norm(p.get("home")), norm(p.get("away"))
    ha, aa = norm(a.get("home")), norm(a.get("away"))
    if not hp or not ap or not ha or not aa:
        return None
    if hp == ha and ap == aa:
        score = 1.0
    else:
        score = min(SequenceMatcher(None, hp, ha).ratio(),
                    SequenceMatcher(None, ap, aa).ratio())
        if score < 0.90:
            return None
    try:
        dt_p = datetime.fromisoformat(p["kickoff_utc"].replace("Z", "+00:00"))
        dt_a = datetime.fromisoformat(a["date"].replace("Z", "+00:00"))
        if dt_p.tzinfo and dt_a.tzinfo and abs((dt_p - dt_a).total_seconds()) > 6 * 3600:
            return None
    except (TypeError, ValueError, KeyError, AttributeError):
        pass
    return score

def compare(pitch_rows, api_rows):
    joined, unresolved, used = [], [], set()
    for a in api_rows:
        candidates = sorted([(s, p) for p in pitch_rows
                             if (s := confidence(p, a)) is not None],
                            key=lambda pair: pair[0], reverse=True)
        if not candidates:
            unresolved.append({"api_fixture_id": a.get("fixture_id"), "reason": "no_high_confidence_match",
                               "home": a.get("home"), "away": a.get("away")})
            continue
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.07:
            unresolved.append({"api_fixture_id": a.get("fixture_id"), "reason": "ambiguous_match"})
            continue
        score, p = candidates[0]
        mid = p["pitch_match_id"]
        if mid in used:
            unresolved.append({"api_fixture_id": a.get("fixture_id"), "reason": "duplicate_pitch_match"})
            continue
        used.add(mid)
        ag = a.get("goals") or {}
        score_equal = p.get("goals_home") == ag.get("home") and p.get("goals_away") == ag.get("away")
        complete = p["xg_home"]["xg_complete"] and p["xg_away"]["xg_complete"]
        usable = score_equal and complete
        home_shots = next((t.get("shots") for t in a.get("teams", [])
                          if t.get("team_id") == a.get("home_id")), None)
        away_shots = next((t.get("shots") for t in a.get("teams", [])
                          if t.get("team_id") == a.get("away_id")), None)
        joined.append({"api_fixture_id": a.get("fixture_id"), "pitch_match_id": mid,
                       "home": a.get("home"), "away": a.get("away"), "league": a.get("league"),
                       "confidence": round(score, 3), "score_agrees": score_equal,
                       "api_goals": ag, "pitch_goals": {"home": p.get("goals_home"), "away": p.get("goals_away")},
                       "api_home_shots": home_shots, "api_away_shots": away_shots,
                       "pitch_home_shots": p["xg_home"]["shot_count"],
                       "pitch_away_shots": p["xg_away"]["shot_count"],
                       "xg_home": p["xg_home"]["xg"] if usable else None,
                       "xg_away": p["xg_away"]["xg"] if usable else None,
                       "usable_for_historical_calibration": usable,
                       "issue": None if usable else ("score_mismatch" if not score_equal else "xg_incomplete")})
    return {"api_football_fixtures": len(api_rows), "pitchapi_fixtures": len(pitch_rows),
            "matched": len(joined), "usable_for_historical_calibration": sum(r["usable_for_historical_calibration"] for r in joined),
            "score_mismatches": sum(r["issue"] == "score_mismatch" for r in joined),
            "unmatched_api_football": len(unresolved), "matched_rows": joined,
            "unresolved": unresolved,
            "unmatched_pitchapi_ids": [p["pitch_match_id"] for p in pitch_rows if p["pitch_match_id"] not in used]}

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Independent post-match PitchAPI xG audit")
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to yesterday Europe/Warsaw")
    parser.add_argument("--max-matches", type=int, default=75)
    args = parser.parse_args()
    from zoneinfo import ZoneInfo
    day = args.date or (datetime.now(ZoneInfo("Europe/Warsaw")).date() - timedelta(days=1)).isoformat()
    date.fromisoformat(day)
    if not 1 <= args.max_matches <= 100:
        parser.error("--max-matches must be 1..100")
    if not os.getenv("PITCHAPI_API_KEY"):
        raise SystemExit("Missing PITCHAPI_API_KEY; use GitHub Actions secret")

    from pitchapi import PitchAPI
    with PitchAPI() as client:
        fixture_list = list(client.date.get(day).matches)
        priority_leagues = {
            "uefa europa league", "uefa conference league", "uefa champions league",
            "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
            "ekstraklasa", "primeira liga", "eredivisie", "jupiler pro league", "super lig"
        }
        # On busy days, don't fill the daily cap with minor early fixtures.
        # All prioritization happens before collecting results, without looking at scores.
        fixture_list.sort(key=lambda m: (
            0 if competition(field(field(m, "league"), "name")) in priority_leagues else 1,
            str(field(m, "time_utc", "")), str(field(m, "id", ""))))
        rows = [collect_match(m, client) for m in fixture_list[:args.max_matches]]
    complete = sum(p["xg_home"]["xg_complete"] and p["xg_away"]["xg_complete"] for p in rows)
    payload = {"schema": "pitchapi-postmatch-xg-v1", "date": day,
               "observed_at_utc": datetime.now(timezone.utc).isoformat(),
               "source": "PitchAPI", "fixtures_available": len(fixture_list),
               "matches_collected": len(rows), "match_limit": args.max_matches,
               "matches_with_complete_xg": complete, "rows": rows,
               "isolation": ISOLATION, "model_effect": "NONE", "kb_n_effect": 0, "dev_n_effect": 0,
               "notice": "Observed post-match xG, NOT predicted pre-match xG."}
    write_json(Path("data/pitchapi/daily") / (day + ".json"), payload)
    api_path = Path("data/api_football/daily") / (day + ".json")
    api_available = api_path.is_file()
    api_rows = json.loads(api_path.read_text(encoding="utf-8")).get("rows", []) if api_available else []
    result = compare(rows, api_rows)
    result.update({"schema": "pitchapi-api-football-comparison-v1", "date": day,
                   "api_football_snapshot_present": api_available,
                   "model_effect": "NONE", "kb_n_effect": 0, "dev_n_effect": 0,
                   "notice": "Historical audit ONLY: never use this match's outcomes to predict the same match."})
    report_path = Path("reports/pitchapi") / (day + ".json")
    write_json(report_path, result)
    md = [f"# PitchAPI / API-Football comparison: {day}", "",
          f"- PitchAPI matches obtained: **{len(rows)} / {len(fixture_list)}**",
          f"- Two-sided complete shot xG: **{complete}**",
          f"- API-Football daily file: **{'yes' if api_available else 'no'}**, matches: **{len(api_rows)}**",
          f"- Unique fixture matches: **{result['matched']}**",
          f"- Usable for historical calibration: **{result['usable_for_historical_calibration']}**",
          f"- Score mismatches: **{result['score_mismatches']}**",
          f"- Unmatched API-Football fixtures: **{result['unmatched_api_football']}**",
          "", "## Matched fixtures", "",
          "| API-F ID | Pitch ID | Match | Home xG | Away xG | Status |",
          "|---|---|---|---:|---:|---|"]
    for r in result["matched_rows"]:
        h = r["xg_home"] if r["xg_home"] is not None else "n/a"
        a = r["xg_away"] if r["xg_away"] is not None else "n/a"
        status = "Historical only" if r["usable_for_historical_calibration"] else r["issue"]
        md.append(f"| {r['api_fixture_id']} | {r['pitch_match_id']} | {r['home']} - {r['away']} | {h} | {a} | {status} |")
    md.extend(["", "## Isolation and caveats", "",
               "- No model/parameter/KB N/DEV N/prediction writes.",
               "- Do not mix xG from different providers without independent calibration.",
               "- Shot definitions and shot totals can differ between data suppliers.",
               "- Unmatched, ambiguous and score-conflicting games are not calibrated.", ""])
    path = Path("reports/pitchapi") / (day + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"date": day, "pitch_matches": len(rows), "xg_complete": complete,
                      "api_matches": len(api_rows), "matched": result["matched"],
                      "usable": result["usable_for_historical_calibration"],
                      "report": str(path), "model_effect": "NONE"}))

if __name__ == "__main__":
    main()
