"""Third-source, pre-match evidence for unresolved KB Score calendar conflicts.

Compares only specific official-source disputed fixture against an already
captured API-Football snapshot. Does NOT edit the ESPN observation or
the original comparison result, award Calendar Gate PASS, or grant PLAY.
"""
import argparse
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team
from tools.kb21_context_enrich import ESPN_TO_API


def _api_match(league, official, row):
    mapping = ESPN_TO_API.get(league)
    if mapping is None or (row.get("league_country"), row.get("league")) != mapping:
        return False
    home = _team(league, official.get("home"))
    away = _team(league, official.get("away"))
    kickoff = _instant(official.get("kickoff"))
    other = _instant(row.get("kickoff_utc"))
    return (bool(home) and bool(away) and kickoff is not None and other is not None
            and _team(league, row.get("home_team")) == home
            and _team(league, row.get("away_team")) == away
            and abs((other - kickoff).total_seconds()) <= 300)


def annotate(comparison, snapshots):
    if not isinstance(comparison, dict) or not isinstance(comparison.get("days"), dict):
        raise ValueError("Expected official source comparison")
    if comparison.get("calendar_gate") != "BLOCKED":
        raise ValueError("This step cannot review a previously cleared calendar")
    result = {**comparison, "calendar_gate": "BLOCKED",
              "publication": "DIAGNOSTIC / NO PLAY", "days": {}}
    investigated = 0
    corroborated = 0
    for day, rows in comparison["days"].items():
        updated = []
        snap = snapshots.get(day)
        valid_snap = (isinstance(snap, dict) and snap.get("date") == day
                      and snap.get("source") == "API-Football"
                      and isinstance(snap.get("candidates"), list))
        for row in rows:
            r = dict(row)
            disputes = []
            for fixture in row.get("fixtures", []):
                f = dict(fixture)
                f["third_source_review"] = None
                if f.get("status") == "START_TIME_CONFLICT":
                    investigated += 1
                    status = "NO_CAPTURED_API_FOOTBALL_SNAPSHOT"
                    match_id = None
                    matches = []
                    official = f.get("official_fixture") or {}
                    if valid_snap:
                        matches = [candidate for candidate in snap["candidates"]
                                   if isinstance(candidate, dict)
                                   and _api_match(row["league_id"], official, candidate)]
                        if len(matches) > 1:
                            status = "AMBIGUOUS_API_MATCH"
                        elif not matches:
                            status = "NO_API_MATCH_FOR_OFFICIAL_KICKOFF"
                        else:
                            candidate = matches[0]
                            api_time = _instant(candidate.get("snapshot_utc") or snap.get("snapshot_utc"))
                            kickoff = _instant(official.get("kickoff"))
                            if api_time is None or kickoff is None or api_time >= kickoff:
                                status = "API_SNAPSHOT_NOT_PREMATCH"
                            else:
                                status = "OFFICIAL_AND_API_TIME_AGREE_ESPN_DIFFERS"
                                match_id = candidate.get("fixture_id")
                                corroborated += 1
                    f["third_source_review"] = {
                        "status": status,
                        "source": "API-Football pre-match snapshot" if valid_snap else None,
                        "snapshot_date": day,
                        "api_fixture_id": match_id,
                        "official_kickoff": official.get("kickoff"),
                        "original_espn_status": "START_TIME_CONFLICT",
                        "requires_manual_resolution": True,
                        "calendar_gate": "BLOCKED",
                    }
                    disputes.append(f["third_source_review"])
                updated_fixture = f
                # do not replace original fixture status or raw evidence
                disputes_entry = updated_fixture
                disputes.append(None) if False else None
                if "fixtures_new" not in r:
                    r["fixtures_new"] = []
                r["fixtures_new"].append(disputes_entry)
            r["fixtures"] = r.pop("fixtures_new", [])
            r["third_source_corrob_count"] = sum(
                f.get("third_source_review", {}).get("status") == "OFFICIAL_AND_API_TIME_AGREE_ESPN_DIFFERS"
                for f in r["fixtures"] if f.get("third_source_review")
            )
            updated.append(r)
        result["days"][day] = updated
    result["third_source_summary"] = {
        "disputes": investigated, "corroborated_with_pre_match_api": corroborated,
    }
    result["third_source_note"] = (
        "API-Football agreement with an unsigned official page supports a manual "
        "resolution of a conflicting ESPN kickoff, not a silent correction, "
        "automatic Calendar Gate PASS, or retroactive pre-match freeze."
    )
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("comparison")
    p.add_argument("--snapshots-dir", default="data/api_football/kb21_inputs")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    report = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    snaps = {}
    for day in report.get("days", {}):
        path = Path(args.snapshots_dir) / (day + ".json")
        if path.is_file():
            try:
                snaps[day] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                snaps[day] = {}
    result = annotate(report, snaps)
    a = Path(args.output_json)
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# KB21: weryfikacja rozbieżności trzecim źródłem",
        "**CALENDAR GATE BLOCKED / NO PLAY — kontrola pomocnicza, nie zatwierdzenie.**",
        f"Konflikty: {result['third_source_summary']['disputes']}; "
        f"potwierdzone czasem oficjalnym i API-Football: "
        f"{result['third_source_summary']['corroborated_with_pre_match_api']}.", "",
    ]
    for day, rows in result["days"].items():
        for row in rows:
            for f in row["fixtures"]:
                proof = f.get("third_source_review")
                if proof:
                    match = f["official_fixture"]
                    lines.append(
                        f"- {day}, {row['competition']}: {match.get('home')} – "
                        f"{match.get('away')}; oficjalny start {match.get('kickoff')}; "
                        f"kontrola API {proof['status']}; ręczne rozstrzygnięcie wymagane."
                    )
    b = Path(args.output_md)
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"KB21 third-source disputes: {investigated if False else result['third_source_summary']['disputes']} "
          f"checked, {corroborated if False else result['third_source_summary']['corroborated_with_pre_match_api']} corroborated; BLOCKED")


if __name__ == "__main__":
    main()
