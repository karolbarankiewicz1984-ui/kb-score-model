"""Auditable PRE-PRICE sports evidence from existing API-Football history.

This module uses ONLY actual, earlier full-time scores already returned by
the team's bounded `fixtures?team=..&last=12` request. It does not make
network calls, fetch market prices, generate expected goals or rate KB Score.

It deliberately does not convert actual past scores into STR/35, QUAL/35,
MATCH/30, or historical analyst P(model). Those require different evidence
(ELO/strength, opponent adjustment, lineups, xG where available) and an
independent forward-validated decision process.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

SCHEMA = "kb21-verified-sports-evidence-v1"
FULL_TIME = "FT"


def _clock(value):
    if not isinstance(value, str):
        raise ValueError("Historical kickoff must be an ISO timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Historical kickoff is malformed") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Historical kickoff must include timezone")
    return stamp.astimezone(timezone.utc)


def _goals(value):
    if type(value) is not int or not 0 <= value <= 30:
        return None
    return value


def _summarize(events):
    if not events:
        return None
    n = len(events)
    gf = sum(x["goals_for"] for x in events)
    ga = sum(x["goals_against"] for x in events)
    wins = sum(x["result"] == "W" for x in events)
    draws = sum(x["result"] == "D" for x in events)
    losses = sum(x["result"] == "L" for x in events)
    return {
        "games": n, "wins": wins, "draws": draws, "losses": losses,
        "goals_for_per_game": round(gf / n, 3),
        "goals_against_per_game": round(ga / n, 3),
        "points_per_game": round((3*wins + draws) / n, 3),
    }


def evidence(rows, team_id, asof_utc):
    """Return factual team evidence only, with per-fixture provenance.

    Only FT regulation scores are used for these new statistics. AET/PEN
    matches are explicitly excluded to avoid misleading 90-minute rates.
    Historical goal rates in the separate old diagnostic are unchanged.
    """
    if (not isinstance(rows, list) or len(rows) > 12
            or type(team_id) is not int or team_id <= 0
            or not isinstance(asof_utc, datetime) or asof_utc.tzinfo is None
            or asof_utc.utcoffset() is None):
        raise ValueError("Need <=12 factual rows, a genuine team ID and aware cutoff")
    cutoff = asof_utc.astimezone(timezone.utc)
    seen = set()
    played = []
    skipped = {"not_ft": 0, "missing_goals": 0, "missing_team": 0}
    for match in rows:
        if not isinstance(match, dict) or not isinstance(match.get("fixture"), dict):
            raise ValueError("Incomplete historical fixture structure")
        fixture = match["fixture"]
        ident = fixture.get("id")
        if type(ident) is not int or ident <= 0 or ident in seen:
            raise ValueError("Missing or duplicated historical fixture ID")
        seen.add(ident)
        kickoff = _clock(fixture.get("date"))
        status = (fixture.get("status") or {}).get("short")
        if status == FULL_TIME and kickoff >= cutoff:
            raise ValueError("Refuse FT match at/after evidence capture time")
        if status != FULL_TIME:
            skipped["not_ft"] += 1
            continue
        teams = match.get("teams") or {}
        home = (teams.get("home") or {}).get("id")
        away = (teams.get("away") or {}).get("id")
        if type(home) is not int or type(away) is not int or home == away:
            raise ValueError("Historical fixture with invalid team identity")
        if team_id not in (home, away):
            skipped["missing_team"] += 1
            continue
        goals = match.get("goals") or {}
        hg, ag = _goals(goals.get("home")), _goals(goals.get("away"))
        if hg is None or ag is None:
            skipped["missing_goals"] += 1
            continue
        side = "home" if home == team_id else "away"
        gf, ga = (hg, ag) if side == "home" else (ag, hg)
        opponent_id = away if side == "home" else home
        competition = match.get("league") or {}
        league_id = competition.get("id")
        season = competition.get("season")
        played.append({
            "fixture_id": ident, "kickoff_utc": kickoff.isoformat(),
            "opponent_team_id": opponent_id,
            "history_league_id": league_id if type(league_id) is int and league_id > 0 else None,
            "history_season": season if type(season) is int and season > 2000 else None,
            "venue": side, "goals_for": gf, "goals_against": ga,
            "result": "W" if gf > ga else "D" if gf == ga else "L",
            "metric": "ACTUAL_REGULATION_GOALS_NOT_XG",
        })
    played.sort(key=lambda x: (x["kickoff_utc"], x["fixture_id"]), reverse=True)
    selected = played[:10]
    venue = {side: [x for x in selected if x["venue"] == side]
             for side in ("home", "away")}
    recent = selected[:5]
    latest = _clock(selected[0]["kickoff_utc"]) if selected else None
    time_since = round((cutoff-latest).total_seconds()/86400, 2) if latest else None
    if time_since is not None and (time_since < 0 or not isfinite(time_since)):
        raise ValueError("Invalid historical recency")
    return {
        "schema": SCHEMA, "provider": "API-Football",
        "evidence_asof_utc": cutoff.isoformat(), "team_id": team_id,
        "source_endpoint": "/fixtures?team=ID&last=12",
        "source_rows": len(rows),
        "ft_rows_used": len(selected), "excluded": skipped,
        "last_10_ft": _summarize(selected),
        "last_5_ft": _summarize(recent),
        "home_ft": _summarize(venue["home"]),
        "away_ft": _summarize(venue["away"]),
        "venue_split_minimum_three": {
            side: len(venue[side]) >= 3 for side in ("home", "away")
        },
        "days_since_previous_kickoff": time_since,
        "previous_fixture_utc": selected[0]["kickoff_utc"] if selected else None,
        "previous_ft_matches": selected,
        "independent_opponent_strength_available": False,
        "verified_xg_available": False,
        "lineup_injury_data_available": False,
        "structural_strength_0_35": None,
        "current_quality_0_35": None,
        "matchup_context_0_30": None,
        "original_p_model": None,
        "sample_is_full_season": False,
        "data_is_pre_market": True,
        "safe_to_publish_play": False,
        "note": ("Raw historical results, segmented by venue and last five; "
                 "recent kickoff is NOT proof of actual rest hours. "
                 "Opponent quality, xG, structural strength, absence risk and "
                 "original P(model) remain unknown."),
    }


def side_note(info, venue):
    """Compact human-readable factual insight, without recommendation."""
    if not isinstance(info, dict) or info.get("schema") != SCHEMA:
        return "Brak danych o wynikach FT."
    v = info.get(venue + "_ft")
    last = info.get("last_5_ft")
    venue_text = (
        f"{venue}: {v['games']} gier, gole {v['goals_for_per_game']:.2f}/"
        f"{v['goals_against_per_game']:.2f}"
        if v and info["venue_split_minimum_three"][venue]
        else f"{venue}: próbka zbyt mała (<3 FT)"
    )
    last_text = (f"ostatnie {last['games']} FT: {last['wins']}W/"
                 f"{last['draws']}D/{last['losses']}L, "
                 f"pkt/mecz {last['points_per_game']:.2f}"
                 if last else "brak zakończonych meczów FT")
    clock = info.get("days_since_previous_kickoff")
    return (last_text + "; " + venue_text
            + (f"; {clock:.1f} dnia od ostatniego rozpoczęcia meczu"
               if clock is not None else ""))
