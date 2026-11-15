"""One-shot safe OddsPapi live acceptance probe, never prints credentials or raw account payload.

Maximum billable calls: 3 (catalog, fixtures, one fixture odds).
No continuous collection or production model changes.
"""
from __future__ import annotations
import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta

from github_models.oddspapi_market import api_get, normalize_snapshot, subscription_budget

def run():
    if not os.environ.get("ODDSPAPI_API_KEY"):
        print("ODDSPAPI_SECRET_STATUS=NOT_AVAILABLE_TO_WORKFLOW")
        return 2
    print("ODDSPAPI_SECRET_STATUS=PRESENT")
    try:
        account = api_get("account")
    except Exception as exc:
        print("ODDSPAPI_AUTH=FAILED " + type(exc).__name__ + ":" + str(exc))
        return 3
    try:
        state = subscription_budget(account, requested=0, reserve=10)
    except Exception as exc:
        print("ODDSPAPI_ACCOUNT=RECEIVED_BUT_QUOTA_UNVERIFIED " + str(exc))
        return 4
    active = [s for s in account.get("subscriptions", [])
              if s.get("is_active") and s.get("subscription_id") == account.get("current_subscription_id")]
    active = active[0]
    print("ODDSPAPI_AUTH=OK")
    print("PLAN_REQUEST_LIMIT=" + str(state["request_limit"]))
    print("PLAN_REQUEST_USED=" + str(state["request_count"]))
    print("PLAN_RESERVE_AVAILABLE=" + str(state["remaining_before_reserve"]))
    print("PLAN_SOCCER_ALLOWED=" + str(10 in active.get("sport_ids", [])))
    print("PLAN_BOOKMAKERS=" + json.dumps(state["bookmakers_in_plan"], ensure_ascii=True))
    if 10 not in active.get("sport_ids", []):
        print("LIVE_PROBE=STOP_NO_SOCCER_PLAN")
        return 5
    if state["remaining_before_reserve"] < 3:
        print("LIVE_PROBE=STOP_QUOTA_RESERVE")
        return 0

    try:
        catalog = api_get("markets", params={"language": "en"})
    except Exception as exc:
        print("CATALOG=FAILED " + type(exc).__name__ + ":" + str(exc))
        return 6
    if not isinstance(catalog, list):
        print("CATALOG=UNEXPECTED_STRUCTURE " + type(catalog).__name__)
        return 7
    soccer = [m for m in catalog if m.get("sportId") == 10]
    print("CATALOG=OK")
    print("CATALOG_TOTAL=" + str(len(catalog)))
    print("CATALOG_SOCCER=" + str(len(soccer)))
    keywords = ("foul", "card", "corner", "goal", "both teams", "handicap", "shot", "offside", "penalty")
    for word in keywords:
        hits = [m for m in soccer if word in (str(m.get("marketName") or "")).lower()]
        print("CATALOG_" + word.upper().replace(" ", "_") + "_COUNT=" + str(len(hits)))
    now = datetime.now(timezone.utc)
    frm = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        fixtures = api_get("fixtures", params={"sportId": 10, "from": frm, "to": to,
                                               "statusId": 0, "hasOdds": "true", "language": "en"})
    except Exception as exc:
        print("FIXTURES=FAILED " + type(exc).__name__ + ":" + str(exc))
        return 8
    if not isinstance(fixtures, list):
        print("FIXTURES=UNEXPECTED_STRUCTURE " + type(fixtures).__name__)
        return 9
    future = []
    for row in fixtures:
        try:
            if row.get("hasOdds") and row.get("statusId") == 0 and row.get("sportId") == 10:
                dt = datetime.fromisoformat(row["startTime"].replace("Z", "+00:00"))
                if dt > now and row.get("fixtureId"):
                    future.append(row)
        except (ValueError, KeyError, TypeError):
            pass
    print("FIXTURES=OK")
    print("FIXTURE_WITH_ODDS_IN_7D=" + str(len(future)))
    print("LEAGUES_WITH_ODDS_IN_7D=" + str(len({x.get("tournamentId") for x in future})))
    if not future:
        print("ODDS_SAMPLE=SKIPPED_NO_AVAILABLE_FUTURE_FIXTURE")
        return 0
    preferred = {"premier league": 0, "la liga": 1, "laliga": 1,
                 "serie a": 2, "bundesliga": 3, "ligue 1": 4,
                 "serie b": 5, "ligue 2": 6, "ekstraklasa": 7}
    def priority(x):
        name = str(x.get("tournamentName") or "").lower()
        order = preferred.get(name, 100)
        return (order, x.get("startTime") or "", x.get("fixtureId") or "")
    chosen = sorted(future, key=priority)[0]
    fid = chosen["fixtureId"]
    print("SAMPLE_MATCH=" + str(chosen.get("participant1Name")) + " vs " +
          str(chosen.get("participant2Name")) + " / " + str(chosen.get("tournamentName")))
    print("SAMPLE_KICKOFF=" + str(chosen.get("startTime")))
    print("SAMPLE_ODDSPAPI_FIXTURE_ID=" + fid)
    try:
        live = api_get("odds", params={"fixtureId": fid, "language": "en", "verbosity": 3})
        result = normalize_snapshot(live, catalog, captured_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        print("ODDS_SAMPLE=FAILED " + type(exc).__name__ + ":" + str(exc))
        return 10
    quotes = result.get("quotes") or []
    summary = result.get("market_summary") or []
    print("ODDS_SAMPLE=OK")
    print("ODDS_SAMPLE_QUOTES=" + str(len(quotes)))
    print("ODDS_SAMPLE_MARKETS=" + str(len({x["market_id"] for x in quotes})))
    print("ODDS_SAMPLE_BOOKMAKERS=" + str(len({x["bookmaker"] for x in quotes})))
    print("ODDS_SAMPLE_NO_VIG_QUOTES=" + str(sum(x["no_vig_probability"] is not None for x in quotes)))
    print("ODDS_SAMPLE_CONSENSUS_MARKETS=" + str(sum(x["consensus_no_vig_probability"] is not None for x in summary)))
    print("ODDS_SAMPLE_MIN_1_20=" + str(sum(x["eligible_min_odd"] for x in quotes)))
    for word in keywords:
        found = [m for m in summary if word in str(m.get("market_name") or "").lower()]
        print("ODDS_SAMPLE_" + word.upper().replace(" ", "_") + "=" + str(len(found)))
    print("LIVE_PROBE=COMPLETED_RESEARCH_ONLY")
    return 0

if __name__ == "__main__":
    raise SystemExit(run())
