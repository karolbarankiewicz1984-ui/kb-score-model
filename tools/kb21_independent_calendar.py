"""Conservative independent fixture evidence matcher.

Consumes user-supplied or licensed provider JSON; never scrapes providers.
Matching names alone is insufficient. Does not change PLAY or historical N.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

def instant(value):
    d=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("Timezone-aware kickoff required")
    return d.astimezone(dt.timezone.utc)

def match_fixtures(api_data, independent_data, tolerance_minutes=5):
    if independent_data.get("provider","").strip().lower() in {"","api-football","api-sports"}:
        raise ValueError("Independent provider name required")
    index={}
    for row in independent_data.get("fixtures",[]):
        key=(row.get("home_team_id"),row.get("away_team_id"))
        if None in key: continue
        index.setdefault(key,[]).append(row)
    matches=[]
    for row in api_data.get("candidates",[]):
        key=(row.get("home_team_id"),row.get("away_team_id"))
        found=[]
        for item in index.get(key,[]):
            try:
                delta=abs((instant(row["kickoff_utc"])-instant(item["kickoff_utc"])).total_seconds())
            except (KeyError,ValueError,TypeError): continue
            if delta<=tolerance_minutes*60 and item.get("source_url"):
                found.append(item)
        matches.append({"fixture_id":row.get("fixture_id"),"event":row.get("event"),
                        "independent_match":len(found)==1,
                        "independent_provider":independent_data["provider"],
                        "source_url":found[0]["source_url"] if len(found)==1 else None,
                        "reason":"MATCHED_FOR_REVIEW" if len(found)==1 else "NO_UNAMBIGUOUS_MATCH",
                        "official_verified":False,"freeze_allowed":False})
    return {"date":api_data.get("date"),"status":"INDEPENDENT_CALENDAR_COMPARISON_ONLY",
            "rows":matches,"kb_n_effect":0,"dev_n_effect":0,"register_writes":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("api_input")
    p.add_argument("independent_input")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=match_fixtures(json.loads(Path(a.api_input).read_text(encoding="utf-8")),
                          json.loads(Path(a.independent_input).read_text(encoding="utf-8")))
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
