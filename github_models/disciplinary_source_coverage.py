"""Read-only coverage of independent secondary foul/card totals.

The football-data.co.uk CSV has match total HF/AF (fouls) and HY/AY
(yellow cards), but not the event-level official OPTA records required for
Superbet settlement. This inventory never upgrades those aggregates into
official bookmaker-compatible stats.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path

from github_models.disciplinary_rules import review_football_data_schema

def utc(s):
    d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamp_timezone_required")
    return d.astimezone(timezone.utc)

def audit_events(rows, source_manifest, opta_scope, *, as_of_utc):
    cutoff=utc(as_of_utc)
    if not isinstance(rows,list) or not isinstance(source_manifest,dict):
        raise ValueError("source_rows_and_manifest_required")
    if opta_scope.get("schema")!="multimodel-non-pl-opta-evidence-scope-v1":
        raise ValueError("missing_exact_opta_evidence_inventory")
    if opta_scope.get("verified_non_pl_opta_per_team_fouls") != 0:
        # Require a new explicit cross-provider match-level proof, not a
        # simple edited counter in an unrelated source-inventory JSON.
        raise ValueError("new_opta_evidence_requires_independent_validation")
    grouped=defaultdict(list)
    excluded=Counter()
    for row in rows:
        try:
            if row["source_provider"]!="football-data.co.uk":
                excluded["different_source_not_opted_in"]+=1
                continue
            completed=utc(row["completed_at_utc"])
            published=utc(row["published_at_utc"])
            if not completed <= published <= cutoff:
                excluded["future_or_invalid_publication"]+=1
                continue
            league=row["league"]
            home=row["home"];away=row["away"]
            if not all(type(x) is str and x.strip() for x in (league,home,away)):
                excluded["invalid_fixture_identity"]+=1
                continue
            identity=(str(row.get("fixture_id") or row.get("match_date")),
                      str(row.get("country_code") or ""),league,home,away)
            grouped[identity].append(row)
        except (KeyError,ValueError,TypeError,AttributeError):
            excluded["incomplete_or_invalid_observation"]+=1
    leagues=defaultdict(Counter)
    totals=Counter()
    for (_,country,league,_,_),records in grouped.items():
        aggregate=leagues[(country,league)]
        aggregate["match_rows"]+=1
        for market in ("fouls","cards"):
            values=[]
            for record in records:
                candidate=record.get("events",{}).get(market)
                if (isinstance(candidate,(list,tuple)) and len(candidate)==2
                    and all(type(v) is int and v>=0 for v in candidate)):
                    values.append(tuple(candidate))
            if not values:
                aggregate[market+"_pair_missing"]+=1
            elif len(set(values))>1:
                aggregate[market+"_pair_conflict"]+=1
                excluded[market+"_duplicate_conflict"]+=1
            else:
                aggregate[market+"_aggregate_pairs"]+=1
                totals[market+"_aggregate_pairs"]+=1
    sorted_leagues=sorted(leagues.items(),key=lambda kv:(
        -kv[1]["fouls_aggregate_pairs"],-kv[1]["cards_aggregate_pairs"],
        kv[0][0],kv[0][1]))
    rule_gates=review_football_data_schema()
    return {
        "schema":"multimodel-disciplinary-source-coverage-v1",
        "as_of_utc":as_of_utc,
        "underlying_secondary_provider":"football-data.co.uk",
        "official_opta_event_level_source_observed":False,
        "opta_non_pl_verified_foul_matches":0,
        "opta_non_pl_evidence_required":opta_scope["promotion_gate"]["minimum_football_data_vs_independent_opta_non_pl_matches"],
        "fouls":dict(aggregate_pair_matches=totals["fouls_aggregate_pairs"],
                     stat_unit="HF+AF secondary total, referee advantage not independently verified",
                     compatible_with_official_superbet=False,
                     missing_event_source_fields=rule_gates["fouls"]["missing_required_fields"]),
        "cards":dict(aggregate_pair_matches=totals["cards_aggregate_pairs"],
                     stat_unit="HY+AY yellow-card secondary total; NOT total_cards nor Bookings",
                     compatible_with_official_superbet=False,
                     missing_event_source_fields=rule_gates["cards"]["missing_required_fields"]),
        "source_manifest_ok":sum(x.get("status")=="ok"
                                 for x in source_manifest.get("sources",[])),
        "unique_secondary_fixture_rows":len(grouped),
        "excluded_reasons":dict(sorted(excluded.items())),
        "league_coverage":[{"country_code":country,"league":league,**dict(ct)}
                           for (country,league),ct in sorted_leagues],
        "market_promotion_allowed":False,
        "paid_oddspapi_calls":0,
        "note":"Dataset coverage is not Superbet payout equivalence. A later, truly independent match-level OPTA comparison plus written OddsPapi Bookings semantics is required.",
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("events","source-manifest","opta-scope","as-of","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    get=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    report=audit_events(get(a.events),get(a.source_manifest),get(a.opta_scope),
                        as_of_utc=getattr(a,"as_of"))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print("DISCIPLINARY_SOURCE_LEAGUES="+str(len(report["league_coverage"])))
    print("DISCIPLINARY_VALIDATION_BLOCKED="+str(not report["market_promotion_allowed"]))
if __name__=="__main__":
    main()
