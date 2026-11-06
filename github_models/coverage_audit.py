"""Independent fixture-coverage diagnostics; no invented probabilities."""
import argparse
import json
from collections import Counter
from pathlib import Path
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize
from github_models.elo_engine import train_elo, eligible_history, utc
from github_models.settlement import fixture_index

def audit(queue, history, *, as_of_utc):
    cutoff = utc(as_of_utc)
    eligible = eligible_history(history, frozen_at_utc=as_of_utc)
    _, counts = train_elo(eligible, frozen_at_utc=as_of_utc)
    fixture_index(queue)
    output = []
    for fixture in queue["fixtures"]:
        row = dict(fixture_id=fixture["fixture_id"], league=fixture["league"],
                   home=fixture["home"], away=fixture["away"])
        try:
            if utc(fixture["kickoff_utc"]) <= cutoff:
                raise ValueError("prediction_not_prematch")
            mapped = resolve(canonicalize(fixture), eligible)
            row["canonical_league"] = mapped["league"]
            row["country_code"] = mapped.get("country_code")
            row["identity_ready"] = True
            row["mapped_home"], row["mapped_away"] = mapped["home"], mapped["away"]
            row["home_training_matches"] = counts.get((mapped["league"], mapped["home"]), 0)
            row["away_training_matches"] = counts.get((mapped["league"], mapped["away"]), 0)
            row["elo_ready"] = min(row["home_training_matches"], row["away_training_matches"]) >= 5
            row["dixon_coles_league_history"] = sum(
                1 for h in eligible if h["league"] == mapped["league"])
            row["dixon_coles_history_ready"] = row["dixon_coles_league_history"] >= 30
            row["reason"] = "ready_for_model_attempt" if row["elo_ready"] else "insufficient_team_history"
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            row["identity_ready"] = False
            row["elo_ready"] = False
            row["dixon_coles_history_ready"] = False
            row["reason"] = str(exc)
        output.append(row)
    by_league = {}
    for row in output:
        group = by_league.setdefault(row.get("canonical_league", row["league"]),
            dict(total=0, identity_ready=0, elo_ready=0, dixon_coles_history_ready=0, reasons={}))
        group["total"] += 1
        for key in ("identity_ready", "elo_ready", "dixon_coles_history_ready"):
            group[key] += int(row[key])
        reason = row["reason"]
        group["reasons"][reason] = group["reasons"].get(reason, 0) + 1
    return dict(schema="github-models-coverage-audit-v1", as_of_utc=as_of_utc,
                total=len(output), elo_ready=sum(r["elo_ready"] for r in output),
                dixon_coles_history_ready=sum(r["dixon_coles_history_ready"] for r in output),
                identity_ready=sum(r["identity_ready"] for r in output),
                verified_training_matches=len(eligible), by_league=by_league,
                reasons=dict(Counter(r["reason"] for r in output)), fixtures=output)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queue", required=True)
    p.add_argument("--history", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--as-of", required=True)
    args = p.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    result = audit(queue, history, as_of_utc=args.as_of)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Coverage: {result['total']} fixtures, Elo ready {result['elo_ready']}, "
          f"Dixon-Coles history ready {result['dixon_coles_history_ready']}")

if __name__ == "__main__":
    main()
