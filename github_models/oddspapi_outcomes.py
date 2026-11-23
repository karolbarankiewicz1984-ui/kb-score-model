"""Independent final-score and event data fetch, one CSV download per league/season.

Avoids paid OddsPapi score calls, records actual first observation time, and
does not claim that old source files were known before the model forecast.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from github_models.public_results import LEAGUES,SEASONS,parse_csv
from github_models.event_parser import parse_events


def collect(*, timeout=15):
    results,events,sources=[],[],[]
    for season in SEASONS:
        for code,league in LEAGUES.items():
            url=f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
            try:
                with urlopen(Request(url,headers={"User-Agent":"github-models-odds-outcomes/1.0"}),timeout=timeout) as resp:
                    raw=resp.read(4_000_001)
                if len(raw)>4_000_000:
                    raise ValueError("source_too_large")
                observed=datetime.now(timezone.utc).isoformat()
                decoded=raw.decode("utf-8-sig",errors="replace")
                goals=parse_csv(decoded,league_code=code,season=season,observed_at_utc=observed)
                stats=parse_events(decoded,league,observed,league_code=code,season=season)
                results.extend(goals)
                events.extend(stats)
                sources.append({"division":code,"season":season,"status":"ok",
                                "goals":len(goals),"stats":len(stats),
                                "sha256":hashlib.sha256(raw).hexdigest(),
                                "observed_at_utc":observed})
            except Exception as e:
                sources.append({"division":code,"season":season,"status":"error",
                                "reason":type(e).__name__})
    if not results:
        raise RuntimeError("independent_final_scores_not_observed")
    return {"results":results,"events":events,
            "manifest":{"schema":"github-models-odds-independent-outcomes-v1",
                        "observed_at_utc":datetime.now(timezone.utc).isoformat(),
                        "sources":sources,"results_count":len(results),
                        "event_rows_count":len(events)}}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--outdir",required=True)
    a=p.parse_args()
    result=collect()
    path=Path(a.outdir);path.mkdir(parents=True,exist_ok=True)
    for key,name in (("results","verified_results.json"),("events","verified_events.json"),
                     ("manifest","source_manifest.json")):
        (path/name).write_text(json.dumps(result[key],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INDEPENDENT_FINISHED_RESULTS="+str(len(result["results"])))
    print("INDEPENDENT_FINISHED_EVENT_ROWS="+str(len(result["events"])))
    print("INDEPENDENT_SOURCE_OK="+str(sum(s["status"]=="ok" for s in result["manifest"]["sources"])))


if __name__=="__main__":
    main()
