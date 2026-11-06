"""Independent fixture-coverage diagnostics; no invented probabilities."""
import argparse
import json
from collections import Counter
from pathlib import Path
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize
from github_models.elo_engine import train_elo

def audit(queue, history, *, as_of_utc):
    ratings, counts = train_elo(history, frozen_at_utc=as_of_utc)
    output = []
    for fixture in queue["fixtures"]:
        row = dict(fixture_id=fixture["fixture_id"], league=fixture["league"],
                   home=fixture["home"], away=fixture["away"])
        try:
            mapped = resolve(canonicalize(fixture), history)
            row["mapped_home"], row["mapped_away"] = mapped["home"], mapped["away"]
            row["home_training_matches"] = counts.get((mapped["league"], mapped["home"]), 0)
            row["away_training_matches"] = counts.get((mapped["league"], mapped["away"]), 0)
            row["elo_ready"] = min(row["home_training_matches"], row["away_training_matches"]) >= 5
            row["dixon_coles_league_history"] = sum(
                1 for h in history if h["league"] == mapped["league"])
            row["dixon_coles_history_ready"] = row["dixon_coles_league_history"] >= 30
            row["reason"] = "ready_for_model_attempt" if row["elo_ready"] else "insufficient_team_history"
        except (ValueError, KeyError, TypeError) as exc:
            row["elo_ready"] = False
            row["dixon_coles_history_ready"] = False
            row["reason"] = str(exc)
        output.append(row)
    return dict(schema="github-models-coverage-audit-v1", as_of_utc=as_of_utc,
                total=len(output), elo_ready=sum(r["elo_ready"] for r in output),
                dixon_coles_history_ready=sum(r["dixon_coles_history_ready"] for r in output),
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
