"""Conservative supplementary finished-score evidence from documented club/league reports.

This is an *observed postmatch* source, NOT a backfill of what existed pre-match.
It never changes model probabilities, odds, frozen forecast identities, event
statistics or official bookmaker settlement. Unverifiable rows fail closed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from urllib.parse import urlsplit
import json

SCHEMA = "multimodel-manually-reconciled-independent-finals-v1"
ALLOWED = {"m_01XpUc", "m_1HL1DQ", "m_3biNtz", "m_4clIHb"}

def utc(v):
    d = datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone_required")
    return d.astimezone(timezone.utc)

def frozen_fixture_map(frozen_dir):
    fixtures = {}
    for p in Path(frozen_dir).joinpath("queues").glob("*/*.json"):
        q = json.loads(p.read_text(encoding="utf-8"))
        for f in q.get("fixtures",[]):
            fid = str(f.get("fixture_id"))
            if fid in ALLOWED:
                ident = {k:f.get(k) for k in
                         ("fixture_id","league","league_id","country_code",
                          "home","away","kickoff_utc","home_team_id","away_team_id")}
                if fid in fixtures and fixtures[fid]!=ident:
                    raise ValueError("conflicting_frozen_fixture_identity")
                fixtures[fid] = ident
    return fixtures

def reconcile(history, evidence, frozen_dir, *, observed_at_utc):
    now = utc(observed_at_utc)
    if (evidence.get("schema")!=SCHEMA or
        evidence.get("review_date")!="2026-11-23"):
        raise ValueError("unreviewed_evidence_version")
    rows=evidence.get("rows")
    if not isinstance(rows,list) or len(rows)!=4:
        raise ValueError("incomplete_four_fixtures")
    frozen=frozen_fixture_map(frozen_dir)
    if set(frozen)!=ALLOWED:
        raise ValueError("frozen_fixture_evidence_not_unique")
    appended=[]
    seen=set()
    for e in rows:
        fid=e["fixture_id"]
        if fid not in ALLOWED or fid in seen:
            raise ValueError("unexpected_or_duplicate_evidence")
        seen.add(fid)
        f=frozen[fid]
        for key in ("fixture_id","league","league_id","country_code",
                    "home","away","kickoff_utc","home_team_id","away_team_id"):
            if e.get(key)!=f.get(key):
                raise ValueError("frozen_identity_mismatch_"+key)
        if date.fromisoformat(e["match_date"])!=utc(f["kickoff_utc"]).date():
            raise ValueError("score_date_mismatch")
        if any(type(e.get(k)) is not int or e[k]<0 for k in ("home_goals","away_goals")):
            raise ValueError("invalid_final_goals")
        source_urls=e.get("sources")
        if not isinstance(source_urls,list) or len(source_urls)<2:
            raise ValueError("insufficient_independent_links")
        domains={urlsplit(url).hostname for url in source_urls
                 if isinstance(url,str) and url.startswith("https://")}
        if len(domains)<2:
            raise ValueError("not_two_distinct_source_domains")
        kickoff=utc(e["kickoff_utc"])
        completed_bound=datetime.combine(date.fromisoformat(e["match_date"]),
                                         datetime.min.time(),tzinfo=timezone.utc)+timedelta(days=2)
        if not (kickoff<completed_bound<=now):
            raise ValueError("score_not_eligible_at_observation_time")
        # Keep the names from the existing independently reviewed frozen
        # historical resolver. Do NOT pretend external sources have PitchAPI IDs.
        actual_home=e["canonical_home"]
        actual_away=e["canonical_away"]
        if any(not isinstance(v,str) or not v.strip() for v in (actual_home,actual_away)):
            raise ValueError("invalid_canonical_names")
        same=[h for h in history
              if h.get("league")==e["league"] and
                 h.get("country_code")==e["country_code"] and
                 h.get("match_date")==e["match_date"] and
                 h.get("home")==actual_home and h.get("away")==actual_away]
        for prev in same:
            if (prev.get("home_goals"),prev.get("away_goals"))!=(e["home_goals"],e["away_goals"]):
                raise ValueError("independent_sources_disagree_final_"+fid)
        if same:
            continue
        appended.append({
            "fixture_id":"reviewed_final:2026-11-20:"+fid,
            "league":e["league"],"country_code":e["country_code"],
            "home":actual_home,"away":actual_away,
            "home_goals":e["home_goals"],"away_goals":e["away_goals"],
            "status":"FINISHED","match_date":e["match_date"],
            "completed_at_utc":completed_bound.isoformat(),
            "published_at_utc":now.isoformat(),
            "source_provider":"independent_league_club_reports",
            "evidence_sources":source_urls,
            "frozen_pitch_fixture_id":fid,
            "actual_bookmaker_payout_verified":False,
        })
    manifest={
        "schema":"multimodel-independent-finals-provenance-v1",
        "observed_at_utc":now.isoformat(),
        "evidence_fixtures":len(seen),"new_finished_rows":len(appended),
        "already_in_verified_history":len(seen)-len(appended),
        "sources":{x["frozen_pitch_fixture_id"]:x["evidence_sources"] for x in appended},
        "not_backdated":True,"bookmaker_payout_verified":False,
        "opta_fouls_verified_for_these_fixtures":False,
        "market_cards_bookings_promoted":False,
    }
    return history+appended,manifest

def main():
    p=argparse.ArgumentParser()
    for k in ("history","evidence","frozen-dir","as-of","out","manifest"):
        p.add_argument("--"+k,required=True)
    a=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    rows,manifest=reconcile(read(a.history),read(a.evidence),a.frozen_dir,
                            observed_at_utc=a.as_of)
    for path,data in ((a.out,rows),(a.manifest,manifest)):
        pth=Path(path)
        pth.parent.mkdir(parents=True,exist_ok=True)
        pth.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                       encoding="utf-8")
    print("CURATED_FINAL_EVIDENCE="+str(manifest["evidence_fixtures"]))
    print("CURATED_FINAL_NEW_ROWS="+str(manifest["new_finished_rows"]))
    print("CURATED_FINAL_BOOKMAKER_PAYOUT_VERIFIED=false")

if __name__=="__main__":
    main()
