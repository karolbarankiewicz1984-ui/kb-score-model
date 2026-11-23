"""One-shot 3-football-fixture market-coverage probe. Up to 5 billable calls.

No key, raw response, or customer payload gets stored or printed.
"""
from __future__ import annotations
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from github_models.oddspapi_market import api_get, normalize_snapshot, subscription_budget

MARKET_WORDS = {
    "fouls": ("foul",),
    "cards": ("card", "booking"),
    "corners": ("corner",),
    "goals": ("goal", "over under full time", "both teams"),
    "shots": ("shot",),
    "offsides": ("offside",),
    "handicaps": ("handicap",),
}
FEATURED = [
    ("bayern", "köln"), ("bayern", "koln"), ("bayern", "cologne"),
    ("nancy", "dijon"), ("guingamp", "rodez"),
    ("darmstadt", "heidenheim"), ("red star", "pau"),
    ("arminia", "magdeburg"), ("albacete", "celta fortuna"),
]


def kind(market_name):
    name = str(market_name or "").lower()
    return [label for label, keys in MARKET_WORDS.items() if any(key in name for key in keys)]


def live():
    if not os.environ.get("ODDSPAPI_API_KEY"):
        print("COVERAGE=NO_SECRET")
        return 2
    account = api_get("account")
    quota = subscription_budget(account, requested=5, reserve=10)
    print("COVERAGE_AUTH=OK")
    print("COVERAGE_LIMIT=" + str(quota["request_limit"]))
    print("COVERAGE_USED_BEFORE=" + str(quota["request_count"]))
    catalog = api_get("markets", params={"language": "en"})
    if not isinstance(catalog, list):
        raise ValueError("market_catalog_unexpected")
    now = datetime.now(timezone.utc)
    fixtures = api_get("fixtures", params={
        "sportId": 10, "from": (now + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "statusId": 0, "hasOdds": "true", "language": "en"})
    if not isinstance(fixtures, list):
        raise ValueError("fixture_catalog_unexpected")
    candidates = [f for f in fixtures
                  if f.get("sportId") == 10 and f.get("statusId") == 0
                  and f.get("hasOdds") and f.get("fixtureId")]
    def score(f):
        h=str(f.get("participant1Name") or "").lower()
        a=str(f.get("participant2Name") or "").lower()
        desired=any((p in h and q in a) or (p in a and q in h) for p,q in FEATURED)
        league=str(f.get("tournamentName") or "").lower()
        elite=any(x in league for x in (
            "bundesliga", "ligue 1", "ligue 2", "championship",
            "serie a", "serie b", "la liga", "ekstraklasa",
            "segunda", "eredivisie", "premier league"))
        return (0 if desired else 1 if elite else 2,
                str(f.get("startTime") or ""), str(f.get("fixtureId")))
    unique=[]
    used_leagues=set()
    for f in sorted(candidates, key=score):
        league = str(f.get("tournamentId"))
        if league in used_leagues: continue
        unique.append(f)
        used_leagues.add(league)
        if len(unique) >= 3: break
    print("COVERAGE_CANDIDATES=" + str(len(candidates)))
    print("COVERAGE_SELECTED=" + str(len(unique)))
    print("COVERAGE_CATALOG_FOUL_MARKETS=" + str(sum("foul" in str(m.get("marketName") or "").lower() and m.get("sportId") == 10 for m in catalog)))
    print("COVERAGE_CATALOG_CARD_MARKETS=" + str(sum("card" in str(m.get("marketName") or "").lower() and m.get("sportId") == 10 for m in catalog)))
    print("COVERAGE_CATALOG_CORNER_MARKETS=" + str(sum("corner" in str(m.get("marketName") or "").lower() and m.get("sportId") == 10 for m in catalog)))
    for index,f in enumerate(unique,1):
        fixture_id=f["fixtureId"]
        print("MATCH_" + str(index) + "=" + json.dumps({
            "home":f.get("participant1Name"), "away":f.get("participant2Name"),
            "competition":f.get("tournamentName"), "kickoff":f.get("startTime"),
            "fixture_id":fixture_id},ensure_ascii=True))
        payload=api_get("odds",params={"fixtureId":fixture_id,"language":"en","verbosity":3})
        try:
            result=normalize_snapshot(payload,catalog,captured_at_utc=datetime.now(timezone.utc).isoformat())
        except ValueError as exc:
            print("MATCH_" + str(index) + "_SKIPPED=" + str(exc))
            continue
        rows=result["quotes"]
        count=Counter()
        bookmaker_categories=Counter()
        market_counts=Counter()
        for r in rows:
            for label in kind(r.get("market_name")):
                count[label]+=1
                market_counts[label+":"+str(r.get("market_name"))]+=1
                if r.get("bookmaker") in {"superbet.pl","efortuna.pl","bet365","pinnacle"}:
                    bookmaker_categories[r["bookmaker"]+":"+label]+=1
        print("MATCH_" + str(index) + "_QUOTES=" + str(len(rows)))
        print("MATCH_" + str(index) + "_MARKETS=" + str(len(set(r["market_id"] for r in rows))))
        print("MATCH_" + str(index) + "_BOOKMAKERS=" + str(len(set(r["bookmaker"] for r in rows))))
        print("MATCH_" + str(index) + "_BY_CATEGORY=" + json.dumps(count,sort_keys=True))
        print("MATCH_" + str(index) + "_SELECTED_BOOKMAKERS=" + json.dumps(bookmaker_categories,sort_keys=True))
        print("MATCH_" + str(index) + "_CATEGORY_MARKETS=" + json.dumps(market_counts,sort_keys=True))
    print("COVERAGE=FINISHED_RESEARCH_ONLY")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(live())
    except (RuntimeError, ValueError) as exc:
        print("COVERAGE=STOPPED " + type(exc).__name__ + ": " + str(exc))
        raise SystemExit(3)
