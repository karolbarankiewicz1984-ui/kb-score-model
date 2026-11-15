"""OddsPapi market identity, strict fixture joins, research-only comparisons.

No bookmaker outside user's Polish whitelist is allowed here. No odds are
used as features in or changes to the existing sports forecasting engine.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from github_models.oddspapi_market import normalize_snapshot, utc

BOOKMAKERS = ("superbet.pl", "sts.pl")
ACTUALLY_AVAILABLE = ("superbet.pl",)
COUNTRY_CODES = {"spain": "ESP", "germany": "DEU", "france": "FRA",
                 "england": "ENG", "italy": "ITA", "poland": "POL",
                 "netherlands": "NLD", "portugal": "PRT",
                 "scotland": "SCO", "belgium": "BEL", "austria": "AUT"}
ALIASES = {
    "albacete balompie": "albacete",
    "rc celta fortuna": "celta fortuna",
    "sv darmstadt 98": "darmstadt",
    "1 fc heidenheim": "heidenheim",
    "ea guingamp": "guingamp",
    "rodez aveyron football": "rodez",
    "arminia bielefeld": "arminia bielefeld",
    "1 fc koln": "koln",
    "fc bayern munchen": "bayern munchen",
    "bayern munich": "bayern munchen",
}
LEAGUE_ALIASES = {
    "laliga 2": "laliga2", "laliga2": "laliga2",
    "la liga 2": "laliga2", "segunda division": "laliga2",
    "2 bundesliga": "bundesliga2", "bundesliga 2": "bundesliga2",
    "ligue 2": "ligue2", "ligue2": "ligue2",
    "1 bundesliga": "bundesliga", "bundesliga": "bundesliga",
}


def fold(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def team(value):
    raw = fold(value)
    raw = ALIASES.get(raw, raw)
    bits = raw.split()
    # Prefix football-club abbreviations and terminal equivalents only.
    while bits and bits[0] in {"fc", "cf", "afc", "sc"}:
        bits = bits[1:]
    while bits and bits[-1] in {"fc", "cf", "afc"}:
        bits = bits[:-1]
    return " ".join(bits)


def league(value):
    raw = fold(value)
    return LEAGUE_ALIASES.get(raw, raw.replace(" ", ""))


def _time_equal(a, b, max_seconds=900):
    try:
        return abs((utc(a) - utc(b)).total_seconds()) <= max_seconds
    except (ValueError, TypeError):
        return False


def join_fixtures(pitch_queue, odds_fixtures, *, as_of_utc):
    """Fail closed on country, competition, kickoff, aliases and duplicate candidates."""
    as_of = utc(as_of_utc)
    candidates = []
    verified = []
    for f in pitch_queue.get("fixtures", []):
        reason = None
        if f.get("identity_blockers"):
            reason = "pitch_identity_blocked"
        try:
            kickoff = utc(f["kickoff_utc"])
            snapshot = utc(f["snapshot_utc"])
            if kickoff <= as_of or snapshot > as_of or snapshot >= kickoff:
                reason = "pitch_not_verified_prematch"
        except (KeyError, ValueError, TypeError):
            reason = "pitch_time_invalid"
        if reason:
            verified.append({"fixture_id": f.get("fixture_id"), "status": "blocked", "reason": reason})
            continue
        h,a,lg = team(f.get("home")), team(f.get("away")), league(f.get("league"))
        cc = (f.get("country_code") or "").upper()
        if not h or not a or h == a or not lg or not cc:
            verified.append({"fixture_id":f.get("fixture_id"), "status":"blocked",
                             "reason":"incomplete_pitch_identity"})
            continue
        valid = []
        for odd in odds_fixtures:
            if odd.get("sportId") != 10 or odd.get("statusId") != 0 or not odd.get("fixtureId"):
                continue
            country = COUNTRY_CODES.get(fold(odd.get("categorySlug")))
            if country != cc:
                continue
            if league(odd.get("tournamentName")) != lg:
                continue
            if not _time_equal(f["kickoff_utc"], odd.get("startTime")):
                continue
            if (team(odd.get("participant1Name")) == h and
                team(odd.get("participant2Name")) == a):
                valid.append(odd)
        if len(valid) == 1:
            odd = valid[0]
            candidates.append((str(f["fixture_id"]), str(odd["fixtureId"])))
            verified.append({"fixture_id":str(f["fixture_id"]), "odds_fixture_id":str(odd["fixtureId"]),
                             "tournament_id":odd["tournamentId"], "status":"matched",
                             "match_rule":"verified_country_league_teams_kickoff",
                             "home":f["home"], "away":f["away"], "league":f["league"],
                             "kickoff_utc":f["kickoff_utc"],
                             "pitch_snapshot_utc":f["snapshot_utc"]})
        else:
            verified.append({"fixture_id":str(f["fixture_id"]), "status":"ambiguous" if len(valid)>1 else "unmatched",
                             "reason":"candidate_count_" + str(len(valid))})
    by_odd = Counter(o for _,o in candidates)
    for row in verified:
        if row.get("odds_fixture_id") and by_odd[row["odds_fixture_id"]]>1:
            row["status"]="ambiguous"
            row["reason"]="multiple_pitch_fixtures_one_odds_fixture"
            row.pop("odds_fixture_id",None)
            row.pop("tournament_id",None)
    return {"schema":"github-models-odds-fixture-links-v1","as_of_utc":as_of_utc,
            "source_provider":"PitchAPI","odds_provider":"OddsPapi",
            "links":verified,"match_count":sum(x["status"]=="matched" for x in verified)}


def classify_market(item):
    """Mutually exclusive category, no fuzzy name intersection or invented line."""
    name = fold(item.get("market_name"))
    period = fold(item.get("period"))
    line = item.get("handicap")
    player = bool(item.get("player_prop")) or str(item.get("player_id", "0")) != "0"
    family,scope = "other","match"
    if player or "player" in name:
        family,scope = "player_prop","player"
    elif name == "full time result" and period == "fulltime":
        family = "1X2"
    elif name == "both teams to score" and period == "fulltime":
        family = "btts"
    elif name == "over under full time" and period == "fulltime":
        family = "goals"
    elif name == "corners over under full time" and period == "fulltime":
        family = "corners"
    elif name == "bookings over under full time" and period == "fulltime":
        family = "cards_bookings"
    elif name in {"fouls over under full time","total fouls over under full time"} and period == "fulltime":
        family = "fouls_match"
    elif "corner" in name:
        family = "corners_other"
    elif "booking" in name or "card" in name:
        family = "cards_other"
    elif "foul" in name:
        family = "fouls_other"
    elif "shot" in name:
        family = "shots_other"
    elif "offside" in name:
        family = "offsides_other"
    elif "handicap" in name:
        family = "handicap"
    elif "goal" in name or "both teams" in name:
        family = "goals_other"
    elif "first half" in name or period != "fulltime":
        family = "other_period"
    if family in {"goals","corners","cards_bookings","fouls_match"}:
        if type(line) not in (float,int) or not math.isfinite(line) or line < 0:
            family = "unverified_line"
    # Bookings market settlement is not verified to match independently sourced
    # yellow-card event totals. Do not allow a probabilistic join yet.
    playable_family = {"1X2":"1X2","goals":"goals","corners":"corners",
                       "fouls_match":"fouls"}.get(family)
    return {"family":family,"scope":scope,"period":period,"line":line,
            "model_market":playable_family,
            "settlement_compatible":playable_family is not None}


def _selection(quote, ident):
    o=fold(quote.get("outcome_name"))
    if ident["model_market"]=="1X2":
        return {"1":"1","x":"X","2":"2"}.get(o)
    if ident["model_market"] in {"goals","corners","fouls"}:
        return {"over":"over","under":"under"}.get(o)
    return None


def market_overlay(links, normalized_odds, frozen_markets=None, *, as_of_utc):
    """Exact-match model-vs-Superbet layer; never create forecasts from odds."""
    as_of = utc(as_of_utc)
    originals = defaultdict(list)
    for row in (frozen_markets or {}).get("markets", []):
        if row.get("market") not in {"goals","corners","cards","fouls"}:
            continue
        try:
            if utc(row["frozen_at_utc"]) >= utc(row["kickoff_utc"]):
                continue
        except (KeyError,TypeError,ValueError):
            # Frozen forecasts do not always embed kickoff: verify through link below.
            pass
        originals[str(row.get("fixture_id"))].append(row)
    output=[]
    counters=Counter()
    quote_ids = {}
    for snapshot in normalized_odds:
        if snapshot.get("provider") != "oddspapi-v4":
            raise ValueError("foreign_odds_source")
        if utc(snapshot["captured_at_utc"]) > as_of:
            raise ValueError("odds_from_future")
        fid = str(snapshot["fixture_id"])
        if fid in quote_ids:
            raise ValueError("duplicate_odds_snapshot_per_fixture")
        quote_ids[fid]=snapshot
    for link in links["links"]:
        if link.get("status")!="matched":
            counters[link.get("status","unknown")] += 1
            continue
        fid = str(link["fixture_id"])
        odd = quote_ids.get(link["odds_fixture_id"])
        if odd is None:
            counters["missing_odds"] += 1
            continue
        if not _time_equal(link["kickoff_utc"],odd["kickoff_utc"]):
            counters["kickoff_disagrees"] += 1
            continue
        if utc(odd["captured_at_utc"]) >= utc(link["kickoff_utc"]):
            counters["late_odds"] += 1
            continue
        grouped={}
        for q in odd.get("quotes",[]):
            if q.get("bookmaker") not in BOOKMAKERS:
                raise ValueError("non_polish_bookmaker_in_overlay")
            ident=classify_market(q)
            sel=_selection(q,ident)
            if sel is None:
                continue
            key=(ident["model_market"],ident["line"],sel)
            if ident["model_market"]=="1X2":
                continue  # Existing 1X2 is model-consensus dependent; link via dedicated forecasts later.
            if key not in grouped or grouped[key]["odds"] < q["odds"]:
                grouped[key]=q
        for p in originals.get(fid,[]):
            try:
                frozen = utc(p["frozen_at_utc"])
                prob = p["probability"]
                if (frozen >= utc(link["kickoff_utc"]) or frozen>as_of or
                    type(prob) not in (int,float) or not math.isfinite(prob) or not 0<=prob<=1):
                    counters["invalid_frozen_forecast"]+=1;continue
            except (KeyError,ValueError,TypeError):
                counters["invalid_frozen_forecast"]+=1;continue
            key=(p["market"],p["line"],p["selection"])
            offer=grouped.get(key)
            if offer is None:
                counters["no_exact_market_offer"]+=1
                continue
            no_vig=offer.get("no_vig_probability")
            output.append({
                "fixture_id":fid,"odds_fixture_id":link["odds_fixture_id"],
                "league":link["league"],"home":link["home"],"away":link["away"],
                "kickoff_utc":link["kickoff_utc"],"market":p["market"],
                "selection":p["selection"],"line":p["line"],
                "model_id":p.get("model_id"),"p_model":prob,
                "probability_status":p.get("probability_status","uncalibrated_research"),
                "price":offer["odds"],"bookmaker":offer["bookmaker"],
                "eligible_min_odds_1_20":bool(offer["eligible_min_odd"]),
                "market_no_vig_probability":no_vig,
                "market_edge_unvalidated":round(prob-no_vig,6) if no_vig is not None else None,
                "odds_captured_at_utc":odd["captured_at_utc"],
                "forecast_frozen_at_utc":p["frozen_at_utc"],
                "source_market_id":offer["market_id"],
                "source_outcome_id":offer["outcome_id"],
                "calibration_verified":False,"settlement_verified":p["market"] in {"goals","corners"},
                "not_an_ev_claim":True})
            counters["matched_exact_market"]+=1
    return {"schema":"github-models-oddspapi-market-comparison-v1",
            "research_only":True, "as_of_utc":as_of_utc,
            "bookmakers":["superbet.pl"],"sts_status":"unavailable_in_subscription",
            "counters":dict(counters),"comparisons":output}


def compare_variants(comparison, settlements):
    """Only evaluate independent, already-settled pre-match forecasts.

    Market-assisted variants are experiments, NOT independent model consensus.
    No fitted parameters or in-sample performance claims.
    """
    settled={}
    for row in settlements.get("settlements",[]):
        if row.get("status")!="settled" or type(row.get("hit")) is not bool:
            continue
        key=(str(row["fixture_id"]),row["market"],row["line"],row["selection"])
        if key in settled and settled[key] != row["hit"]:
            raise ValueError("contradictory_settlement")
        settled[key]=row["hit"]
    buckets=defaultdict(list)
    for p in comparison["comparisons"]:
        if not p.get("eligible_min_odds_1_20") or not p.get("settlement_verified"):
            continue
        y=settled.get((str(p["fixture_id"]),p["market"],p["line"],p["selection"]))
        if y is None:
            continue
        base = p["p_model"]
        market = p.get("market_no_vig_probability")
        variants={"frozen_model":base}
        if market is not None:
            variants["market_filter_only"]=base if abs(base-market) <= .10 else None
            variants["shadow_50_50_blend"]=.5*base+.5*market
        for name,value in variants.items():
            if value is not None:
                buckets[name].append((value,float(y),p["price"],
                                      (p["fixture_id"],p["market"],p["line"],p["selection"])))
    metrics=[]
    for name,rows in sorted(buckets.items()):
        unique={}
        for value,y,price,key in rows:
            if key not in unique:
                unique[key]=(value,y,price)
        vals=list(unique.values())
        if not vals: continue
        metrics.append({"variant":name,"n":len(vals),
                        "unique_matches":len({k[0] for k in unique}),
                        "hit_rate":round(mean(y for _,y,_ in vals),6),
                        "brier":round(mean((p-y)**2 for p,y,_ in vals),6),
                        "log_loss":round(mean(-(y*math.log(max(p,1e-12))+
                                        (1-y)*math.log(max(1-p,1e-12))) for p,y,_ in vals),6),
                        "simulated_unit_stake_roi":round(mean(odd*y-1 for _,y,odd in vals),6)})
    return {"schema":"github-models-oddspapi-shadow-audit-v1",
            "settled_samples_only":True,"models_unchanged":True,
            "market_assisted_shadow_not_validated":True,
            "conclusion":"insufficient_evidence" if not metrics else "retrospective_descriptive_only",
            "metrics":metrics,
            "warning":"Compare variants on identical sample keys before drawing conclusions; no prospective validation yet."}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("join","overlay","audit"))
    p.add_argument("--queue");p.add_argument("--fixtures");p.add_argument("--links")
    p.add_argument("--odds");p.add_argument("--markets");p.add_argument("--settlements")
    p.add_argument("--as-of",required=True);p.add_argument("--out",required=True)
    a=p.parse_args(argv)
    load=lambda name:json.loads(Path(name).read_text(encoding="utf-8"))
    if a.mode=="join":
        result=join_fixtures(load(a.queue),load(a.fixtures),as_of_utc=a.as_of)
    elif a.mode=="overlay":
        payload=load(a.odds)
        snapshots = payload["snapshots"] if isinstance(payload,dict) else payload
        result=market_overlay(load(a.links),snapshots,load(a.markets) if a.markets else None,as_of_utc=a.as_of)
    else:
        result=compare_variants(load(a.odds),load(a.settlements))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"mode":a.mode,"out":str(dest),"entries":len(result.get("comparisons",result.get("links",result.get("metrics",[]))))}))


if __name__=="__main__":
    main()
