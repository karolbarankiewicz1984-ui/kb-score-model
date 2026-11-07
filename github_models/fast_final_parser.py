"""Strict interpretation of independently observed API-Football FT records.

Only final 90-minute outcomes are accepted. Observation timestamps must
never be represented as provider publication or real final-whistle times.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo
from github_models.elo_engine import utc
from github_models.competition_identity import country_code, league_for_label, LEAGUE_COUNTRIES
from github_models.reviewed_resolver import resolve_reviewed
from github_models.settlement import COUNTRY_ZONES


def parse_final(match, history, observed_at):
    fixture = match["fixture"]
    if fixture["status"]["short"] != "FT":
        raise ValueError("not_regulation_final")
    fid = fixture["id"]
    if type(fid) is not int or fid <= 0:
        raise ValueError("invalid_provider_fixture_id")
    league = match["league"]
    country = country_code(league["country"])
    canonical = league_for_label(league["name"], country)
    if country is None or LEAGUE_COUNTRIES.get(canonical) != country:
        raise ValueError("unreviewed_competition")
    kickoff = utc(fixture["date"])
    if kickoff >= utc(observed_at) - timedelta(minutes=70):
        raise ValueError("implausible_finished_time")
    scores = match.get("score") or {}
    fulltime = scores.get("fulltime") or {}
    goals = match.get("goals") or {}
    pair = (goals.get("home"), goals.get("away"))
    check = (fulltime.get("home"), fulltime.get("away"))
    if any(type(x) is not int or x < 0 for x in pair):
        pair = check
    if any(type(x) is not int or x < 0 for x in pair):
        raise ValueError("missing_final_score")
    if all(type(x) is int and x >= 0 for x in check) and pair != check:
        raise ValueError("conflicting_final_score")
    raw_home = match["teams"]["home"]["name"]
    raw_away = match["teams"]["away"]["name"]
    resolved = resolve_reviewed({"league":canonical,"country_code":country,
        "home":raw_home,"away":raw_away}, history)
    zone = ZoneInfo(COUNTRY_ZONES.get(country,"UTC"))
    return {"fixture_id":"apifb:"+str(fid),"league":canonical,
        "country_code":country,"home":resolved["home"],"away":resolved["away"],
        "home_goals":pair[0],"away_goals":pair[1],"match_date":kickoff.astimezone(zone).date().isoformat(),
        "kickoff_utc":kickoff.isoformat().replace("+00:00","Z"),
        "completed_at_utc":observed_at,"published_at_utc":observed_at,
        "status":"FINISHED","source_provider":"API-Football",
        "source_record_id":str(fid),"source_home":raw_home,"source_away":raw_away}


def parse_stats(response, match):
    if len(response) != 2:
        raise ValueError("stats_not_two_teams")
    home_id = match["teams"]["home"]["id"]
    away_id = match["teams"]["away"]["id"]
    if type(home_id) is not int or type(away_id) is not int or home_id == away_id:
        raise ValueError("invalid_team_identifiers")
    by_id = {row["team"]["id"]:row for row in response}
    if len(by_id) != 2 or set(by_id) != {home_id,away_id}:
        raise ValueError("stats_team_id_mismatch")
    def value(team_id,label):
        found = [x.get("value") for x in by_id[team_id].get("statistics",[])
                 if x.get("type") == label]
        return found[0] if len(found)==1 and type(found[0]) is int and found[0]>=0 else None
    events={}
    for market,label in (("corners","Corner Kicks"),("cards","Yellow Cards"),("fouls","Fouls")):
        vals=[value(home_id,label),value(away_id,label)]
        if all(type(v) is int for v in vals):
            events[market]=vals
    return events
