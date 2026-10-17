"""Attach *factual* pre-match history to KB21 analyst worksheets, not scores.

Independent of KB Score model calculations. Uses stored API-Football snapshots
only as labelled research context: goals ARE NOT xG, STR/QUAL/MATCH or P(model).
Only joins same competition, same named teams and kickoff within five minutes.
Every context field is optional; absent/mismatched data stays explicitly absent.
No fixture, score, historical N, freeze or Calendar Gate can be authorized here.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from tools.kb21_fixture_crosscheck import _canonical, _instant

ESPN_TO_API = {
    "eng.1": ("England", "Premier League"),
    "esp.1": ("Spain", "La Liga"),
    "ita.1": ("Italy", "Serie A"),
    "ger.1": ("Germany", "Bundesliga"),
    "fra.1": ("France", "Ligue 1"),
    "por.1": ("Portugal", "Primeira Liga"),
    "ned.1": ("Netherlands", "Eredivisie"),
    "bel.1": ("Belgium", "Jupiler Pro League"),
    "tur.1": ("Turkey", "Süper Lig"),
    "uefa.champions": (None, "UEFA Champions League"),
    "uefa.europa": (None, "UEFA Europa League"),
    "uefa.europa.conf": (None, "UEFA Conference League"),
    "uefa.nations": (None, "UEFA Nations League"),
    "fifa.worldq.uefa": (None, "World Cup - Qualification Europe"),
}


def _goal_history(side):
    if not isinstance(side, dict):
        return None
    count = side.get("sample_size")
    gf, ga = side.get("goals_for_per_match"), side.get("goals_against_per_match")
    if (isinstance(count, bool) or not isinstance(count, int)
            or not 5 <= count <= 10):
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or v < 0 for v in (gf, ga)):
        return None
    ids = side.get("fixture_ids")
    if not isinstance(ids, list) or len(ids) != count:
        return None
    return {"previous_completed_matches": count, "goals_for_per_match": gf,
            "goals_against_per_match": ga, "historical_fixture_ids": ids,
            "metric": "ACTUAL GOALS, NOT xG"}


def _match_fixture(espn, api_row):
    code = str(espn.get("fixture_id", "")).split(":")[0]
    scope = ESPN_TO_API.get(code)
    if not scope:
        return False
    if (api_row.get("league_country"), api_row.get("league")) != scope:
        return False
    parts = espn.get("fixture", "").split(" - ", 1)
    if len(parts) != 2:
        return False
    kickoff, other = _instant(espn.get("kickoff")), _instant(api_row.get("kickoff_utc"))
    return (kickoff is not None and other is not None
            and abs((kickoff - other).total_seconds()) <= 300
            and _canonical(parts[0]) == _canonical(api_row.get("home_team"))
            and _canonical(parts[1]) == _canonical(api_row.get("away_team")))


def enrich(queue, snapshots):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue with fixtures list")
    result = {**queue, "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY"}
    totals = Counter()
    fixtures = []
    for fixture in queue["fixtures"]:
        row = dict(fixture)
        day = row.get("date_warsaw")
        snapshot = snapshots.get(day)
        reason = "NO_API_SNAPSHOT"
        context = None
        if snapshot is not None:
            if (not isinstance(snapshot, dict) or snapshot.get("date") != day
                    or snapshot.get("source") != "API-Football"
                    or not isinstance(snapshot.get("candidates"), list)):
                reason = "INVALID_API_SNAPSHOT"
            else:
                candidates = [f for f in snapshot["candidates"]
                              if isinstance(f, dict) and _match_fixture(row, f)]
                if not candidates:
                    reason = "NO_UNAMBIGUOUS_NAME_LEAGUE_TIME_MATCH"
                elif len(candidates) > 1:
                    reason = "AMBIGUOUS_MATCH"
                else:
                    matched = candidates[0]
                    snapshot_time = _instant(matched.get("snapshot_utc") or snapshot.get("snapshot_utc"))
                    kickoff = _instant(row.get("kickoff"))
                    if snapshot_time is None or kickoff is None or snapshot_time >= kickoff:
                        reason = "SNAPSHOT_NOT_PREMATCH"
                    else:
                        rates = matched.get("api_goal_rates") or {}
                        home = _goal_history(rates.get("home"))
                        away = _goal_history(rates.get("away"))
                        context = {
                            "api_fixture_id": matched.get("fixture_id"),
                            "source": "API-Football historical completed matches",
                            "source_file": f"data/api_football/kb21_inputs/{day}.json",
                            "captured_at": snapshot_time.isoformat(),
                            "home": home, "away": away, "xg": None,
                            "note": ("Goals from previous completed matches only; "
                                     "not expected goals, not a reconstructed LIVE analyst score."),
                        }
                        reason = "PRIOR_GOAL_CONTEXT" if home or away else "MATCH_WITHOUT_RELIABLE_HISTORY"
        row["pre_match_research"] = {"status": reason, "context": context}
        # The original blank analyst form is immutable in this enrichment.
        fixtures.append(row)
        totals[reason] += 1
    result["fixtures"] = fixtures
    result["research_summary"] = dict(sorted(totals.items()))
    result["research_note"] = (
        "Research context is NOT scoring or a second official calendar. "
        "No scores, xG, P(model), calendar approval, or register/N writes.")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("--snapshots-dir", default="data/api_football/kb21_inputs")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    snapshots = {}
    for day in queue.get("days", []):
        file = Path(args.snapshots_dir) / (str(day) + ".json")
        if file.is_file():
            try:
                snapshots[day] = json.loads(file.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                snapshots[day] = {"date": day, "source": "INVALID", "candidates": []}
    result = enrich(queue, snapshots)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"KB21 pre-match factual context: {result['research_summary']}; NO PLAY")


if __name__ == "__main__":
    main()
