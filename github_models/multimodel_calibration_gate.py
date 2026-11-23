"""Conservative cross-model settlement inventory and calibration decision.

Uses independent *distinct fixtures*, never correlated bets as the sample size.
This is a diagnostic, not training, model selection or automatic weight update.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA="multimodel-calibration-readiness-v1"
DIAGNOSTIC_MIN_GAMES=20
RECALIBRATION_MIN_GAMES=100

def report(replay, shadow, opta_scope=None):
    if (replay.get("schema")!="github-models-oddspapi-frozen-audit-v1"
        or shadow.get("schema")!="multimodel-priced-shadow-outcomes-v1"):
        raise ValueError("unsupported_audit_schema")
    priced=[r for r in shadow.get("entries",[])
            if r.get("status")=="settled"]
    groups=defaultdict(list)
    for r in priced:
        if (r.get("market") not in ("btts","handicap")
            or r.get("bookmaker")!="superbet.pl"
            or r.get("official_bookmaker_settlement_verified") is not False
            or type(r.get("price")) not in (int,float) or r["price"]<1.2
            or type(r.get("p_model")) not in (int,float)
            or not 0<=r["p_model"]<=1
            or type(r.get("hit")) is not bool):
            raise ValueError("invalid_settled_research_quote")
        groups[r["market"]].append(r)
    stats={}
    for market in ("btts","handicap"):
        rows=groups[market]
        distinct=len({r["fixture_id"] for r in rows})
        hit_rate=sum(r["hit"] for r in rows)/len(rows) if rows else None
        brier=sum((r["p_model"]-int(r["hit"]))**2 for r in rows)/len(rows) if rows else None
        log_loss=(
            sum(-(math.log(max(r["p_model"],1e-12)) if r["hit"] else
                  math.log(max(1-r["p_model"],1e-12))) for r in rows)/len(rows)
            if rows else None)
        stats[market]={
            "settled_quotes":len(rows),"distinct_settled_fixtures":distinct,
            "exploratory_hit_rate":round(hit_rate,6) if rows else None,
            "exploratory_brier":round(brier,6) if rows else None,
            "exploratory_log_loss":round(log_loss,6) if rows else None,
            "diagnostic_20_fixtures_reached":distinct>=DIAGNOSTIC_MIN_GAMES,
            "review_100_fixtures_reached":distinct>=RECALIBRATION_MIN_GAMES,
        }
    shadow_unique=len({r["fixture_id"] for r in priced})
    abc_unique=replay.get("unique_settled_fixtures")
    if type(abc_unique) is not int or abc_unique<0:
        raise ValueError("invalid_abc_settled_count")
    conservative_max=max(shadow_unique,abc_unique) # Can't assert A/B/C and SHADOW are disjoint.
    status_count=replay.get("status_counts",{})
    unresolved=replay.get("unresolved_reasons",{})
    opta_scope=opta_scope or {}
    return {
        "schema":SCHEMA,
        "source_replay_as_of_utc":replay["as_of_utc"],
        "source_shadow_as_of_utc":shadow["as_of_utc"],
        "shadow_settled_quotes":len(priced),
        "shadow_distinct_settled_fixtures":shadow_unique,
        "abc_settled_quotes":replay.get("settled_selection_quotes",0),
        "abc_distinct_settled_fixtures":abc_unique,
        "conservative_max_distinct_fixtures":conservative_max,
        "abc_status_counts":status_count,
        "abc_unresolved_reasons":unresolved,
        "abc_unsettled_market_rules_not_yet_verified":unresolved.get("market_settlement_not_verified",0),
        "abc_unsettled_source_final_missing":unresolved.get("no_verified_final_yet",0),
        "abc_unsettled_other_exact_outcome_missing":unresolved.get("no_exact_verified_outcome",0),
        "shadow_status_counts":shadow.get("status",{}),
        "shadow_unresolved_reason_counts":shadow.get("status_reason_counts",{}),
        "market_summaries":stats,
        "opta_outside_premier_league_verified_matches":opta_scope.get("verified_non_pl_opta_per_team_fouls",0),
        "opta_non_pl_production_equivalence":False,
        "diagnostic_threshold_met":conservative_max>=DIAGNOSTIC_MIN_GAMES,
        "minimum_100_distinct_match_review":conservative_max>=RECALIBRATION_MIN_GAMES,
        "holdout_evidence_available":False, # neither output supplies separate out-of-sample validation
        "bookmaker_payout_confirmed":False,
        "calibration_authorized":False,
        "model_weights_changed":False,
        "reason":("only_independent_fixture_count_below_100"
                  if conservative_max<RECALIBRATION_MIN_GAMES
                  else "holdout_and_bookmaker_equivalence_not_verified"),
        "note":"No automatic tuning. Same-fixture correlated selections must not be counted as independent validation matches."
    }

def main():
    a=argparse.ArgumentParser()
    for x in ("replay","shadow","out"):
        a.add_argument("--"+x,required=True)
    a.add_argument("--opta-scope")
    v=a.parse_args()
    get=lambda p:json.loads(Path(p).read_text(encoding="utf-8"))
    result=report(get(v.replay),get(v.shadow),
                  get(v.opta_scope) if v.opta_scope else None)
    o=Path(v.out);o.parent.mkdir(parents=True,exist_ok=True)
    o.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                 encoding="utf-8")
    print("CALIBRATION_DISTINCT_MATCHES_UPPER_BOUND="+str(result["conservative_max_distinct_fixtures"]))
    print("CALIBRATION_GO=false")

if __name__=="__main__":
    main()
