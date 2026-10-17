"""Audit football fixture scope; never silently equate data-provider coverage to official completeness.

Works only on stored ESPN candidate queue, independent football-data snapshots
and crosscheck evidence. A lack of a provider fixture means UNKNOWN, not no
match. NO Calendar Gate PASS, LIVE publication, or Sheet writes.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from tools.kb21_fixture_crosscheck import ESPN_TO_FDO

CORE = {
    "eng.1": "Premier League", "esp.1": "La Liga", "ita.1": "Serie A",
    "ger.1": "Bundesliga", "fra.1": "Ligue 1",
}
EXTENDED = {
    "por.1": "Portugalia", "ned.1": "Holandia", "bel.1": "Belgia",
    "tur.1": "Turcja", "uefa.champions": "Liga Mistrzow",
    "uefa.europa": "Liga Europy", "uefa.europa.conf": "Liga Konferencji",
    "uefa.nations": "Liga Narodow", "fifa.worldq.uefa": "Eliminacje MŚ UEFA",
}
SCOPE = {**CORE, **EXTENDED}


def summarize(queue, snapshots):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected crosschecked KB21 queue")
    days = sorted(set(queue.get("days", [])))
    result = {"status": "REVIEW_REQUIRED", "calendar_gate": "BLOCKED",
              "official_organizer_verified": False,
              "publication": "DIAGNOSTIC / NO PLAY", "days": {}}
    for day in days:
        rows = [f for f in queue["fixtures"] if f.get("date_warsaw") == day]
        snapshot = snapshots.get(day)
        trusted_second_source = (isinstance(snapshot, dict)
                                 and snapshot.get("provider") == "football-data.org"
                                 and snapshot.get("date") == day
                                 and isinstance(snapshot.get("fixtures"), list))
        source_status = queue.get("source_status", {}).get(day, [])
        statuses = {x.get("league"): x for x in source_status
                    if isinstance(x, dict) and x.get("league")}
        per_league = []
        for code, name in SCOPE.items():
            left = [f for f in rows if f.get("fixture_id", "").split(":")[0] == code]
            lookup = ESPN_TO_FDO.get(code)
            is_in_scope = (trusted_second_source and lookup is not None
                           and (not snapshot.get("requested_competitions")
                                or lookup in snapshot["requested_competitions"]))
            right = ([f for f in snapshot["fixtures"]
                      if isinstance(f, dict) and f.get("competition_code") == lookup]
                     if is_in_scope else [])
            matched = sum(f.get("independent_crosscheck", {}).get("status") == "MATCHED_FOR_REVIEW"
                          for f in left)
            source = statuses.get(code)
            if source and source.get("status") == "ERROR":
                state = "ESPN_SOURCE_ERROR"
            elif source is None:
                state = "ESPN_SOURCE_STATUS_UNKNOWN"
            elif not trusted_second_source:
                state = "SECOND_SOURCE_ABSENT"
            elif lookup is None:
                state = "SECOND_PROVIDER_NO_VERIFIED_MAPPING"
            elif not is_in_scope:
                state = "SECOND_PROVIDER_OUT_OF_SCOPE"
            elif len(left) == 0 and len(right) == 0:
                state = "BOTH_PROVIDERS_EMPTY_OFFICIAL_REVIEW_NEEDED"
            elif len(left) != len(right) or matched != len(left):
                state = "COUNT_OR_IDENTITY_DIFFERENCE_REVIEW"
            else:
                state = "TWO_PROVIDER_CANDIDATE_AGREEMENT_REVIEW"
            per_league.append({
                "league_id": code, "competition": name,
                "mandatory_core": code in CORE,
                "espn_candidates": len(left),
                "independent_provider_candidates": len(right) if is_in_scope else None,
                "crossmatched": matched,
                "status": state, "official_verified": False,
                "full_coverage_verified": False,
            })
        totals = Counter(row["status"] for row in per_league)
        result["days"][day] = {
            "candidate_fixtures": len(rows),
            "independent_provider_available": trusted_second_source,
            "core_leagues": [row for row in per_league if row["mandatory_core"]],
            "other_competitions": [row for row in per_league if not row["mandatory_core"]],
            "issue_counts": dict(sorted(totals.items())),
            "official_full_card_verified": False,
        }
    result["note"] = (
        "Both data providers are unofficial relative to competition organizers. "
        "A source returning zero games never proves a competition has no games; "
        "check official schedules and international scope. No automatic Calendar Gate PASS."
    )
    return result


def render(summary):
    out = ["# KB Score 2.1 — kontrola kompletności terminarza", "",
           "**CALENDAR GATE BLOCKED — zestawienie dwóch dostawców, NIE oficjalna weryfikacja.**",
           "Dane pomocnicze nie dowodzą braku meczów przy pustej odpowiedzi.", ""]
    for day, data in sorted(summary["days"].items()):
        out.extend([f"## {day}", "",
                    f"Kandydaci ESPN: {data['candidate_fixtures']}; "
                    f"football-data.org dostępny: {'TAK' if data['independent_provider_available'] else 'NIE'}", "",
                    "| Rozgrywki | ESPN | Drugie źródło | Zgodne | Ocena kompletności |",
                    "|---|---:|---:|---:|---|"])
        for row in data["core_leagues"] + data["other_competitions"]:
            other = (str(row["independent_provider_candidates"])
                     if row["independent_provider_candidates"] is not None else "BRAK ZAKRESU")
            out.append(f"| {row['competition']} | {row['espn_candidates']} | {other} | "
                       f"{row['crossmatched']} | {row['status']} |")
        out.extend(["", "**Obowiązkowe następne sprawdzenie:** oficjalne terminarze i pełna "
                    "karta rozgrywek, niezależnie od zgodności obu dostawców.", ""])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("--snapshots-dir", default="data/football_data_org")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    snapshots = {}
    for day in queue.get("days", []):
        path = Path(args.snapshots_dir) / (str(day) + ".json")
        if path.is_file():
            try:
                snapshots[day] = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                snapshots[day] = {}
    result = summarize(queue, snapshots)
    for target, body in [(Path(args.output_json), json.dumps(result, indent=2, ensure_ascii=False) + "\n"),
                         (Path(args.output_md), render(result))]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    print(f"Calendar coverage audited for {len(result['days'])} days; official gate BLOCKED")


if __name__ == "__main__":
    main()
