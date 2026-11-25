"""Conservative read-only joins for the panel, independent of model training."""
from collections import defaultdict, Counter
from datetime import datetime
import math

def stamp(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive_timestamp")
    return d

def key(r):
    m = r["market"]
    line = r.get("line")
    if m in ("1X2", "double_chance"):
        if line is not None and (type(line) not in (int, float) or line != 0):
            raise ValueError("invalid_categorical_line")
        line = None
    elif m == "btts":
        if line is not None:
            raise ValueError("invalid_btts_line")
    elif type(line) not in (int,float) or not math.isfinite(line):
        raise ValueError("invalid_numeric_line")
    return (r["fixture_id"], m, r["selection"], line)

def panel_links(fixtures, forecasts, odds, results):
    by_fixture = {r["fixture_id"]:r for r in fixtures["fixtures"]}
    abc_index, shadow_index = defaultdict(list), defaultdict(list)
    for r in odds["abc_comparisons"]["comparisons"]:
        abc_index[key(r)].append(r)
    for r in odds["shadow_comparisons"]["rows"]:
        shadow_index[key(r)].append(r)
    links = []
    seen = set()
    for lane, rows, index in (
        ("ABC", forecasts["abc"]["candidates"], abc_index),
        ("SHADOW", forecasts["shadow"]["candidates"], shadow_index)):
        for r in rows:
            k = key(r)
            fid = k[0]
            p = r.get("probability", r.get("probability_min"))
            model = (r.get("model") or "elo-and-dixon-min-consensus") if lane == "ABC" else r["model_id"]
            variant = r.get("variant") if lane == "ABC" else None
            frozen = fixtures["generated_at_utc"]
            identity = [lane, *k, model, variant, frozen]
            if tuple(identity) in seen:
                raise ValueError("duplicate_forecast_identity")
            seen.add(tuple(identity))
            found = []
            for quote in index[k]:
                if lane == "ABC":
                    price, qp, captured, qfreeze = (quote.get(x) for x in ("price","p_model","odds_captured_at_utc","forecast_frozen_at_utc"))
                    if quote.get("model_id") != model or quote.get("settlement_verified") is not True:
                        continue
                    if not quote.get("source_market_id") or not quote.get("source_outcome_id"):
                        continue
                else:
                    price, qp, captured, qfreeze = (quote.get(x) for x in ("odds","probability","price_captured_at_utc","frozen_at_utc"))
                    if quote.get("status") != "quoted_research" or model != "shadow-goals-independent-poisson-v1":
                        continue
                if (quote.get("bookmaker") != "superbet.pl" or
                    type(price) not in (int,float) or not math.isfinite(price) or price <= 1 or
                    type(qp) not in (int,float) or not math.isfinite(qp) or abs(p-qp)>0.00001 or
                    stamp(qfreeze)!=stamp(frozen) or not captured or
                    not stamp(frozen)<=stamp(captured)<stamp(by_fixture[fid]["kickoff_utc"])):
                    continue
                found.append({"price":price,"captured_at_utc":captured,
                    "bookmaker":"superbet.pl","source_market_id":quote.get("source_market_id"),
                    "source_outcome_id":quote.get("source_outcome_id"),
                    "source_odds_fixture_id":quote.get("odds_fixture_id")})
            unique = {tuple(sorted(q.items())):q for q in found}
            price = next(iter(unique.values())) if len(unique)==1 else None
            status = "ambiguous_quote" if len(unique)>1 else "missing_verified_quote"
            if price is not None:
                status = "archived_research_quote" if price["price"]>=1.2 else "below_minimum_odds"
            links.append({"forecast_identity":identity,"fixture_id":fid,"market":k[1],
                "selection":k[2],"line":k[3],"model":model,"variant":variant,"lane":lane,
                "probability":p,"quality_score":None,"probability_status":"uncalibrated_research",
                "quote":price,"quote_status":status,"top_eligible":False})
    # Use only already-resolved, independently settled SHADOW evidence. No name matching.
    evidence = []
    for row in results["exact_shadow_outcomes"]:
        if row.get("status")!="settled" or not row.get("source_fixture_id"):
            continue
        if row.get("market_identity")!="exact_quote_research_only" or type(row.get("hit")) is not bool:
            continue
        if row.get("official_bookmaker_settlement_verified") is not False:
            continue
        evidence.append({"identity":[*key(row),row["frozen_at_utc"]],
            "source_fixture_id":row["source_fixture_id"],"hit":row["hit"],
            "actual_goals":row.get("actual_goals"),"official_payout_verified":False})
    return {"schema":"multimodel-panel-links-v1","rows":links,
        "quote_status_counts":dict(Counter(r["quote_status"] for r in links)),
        "historical_shadow_evidence":evidence,
        "abc_individual_settlement_status":"not_exposed_by_source_audit",
        "quality_score_status":"not_computed","research_view_only":True}
