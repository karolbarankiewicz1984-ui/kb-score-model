"""Fetch final results from API-Football; read-only network access."""
import argparse
import json
import os
from pathlib import Path
from tools.api_market_http import ApiClient

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    if not str(Path(args.output)).startswith("data/experimental_engine/results/"):
        raise ValueError("isolated results only")
    key=os.getenv("API_FOOTBALL_KEY")
    if not key: raise SystemExit("API_FOOTBALL_KEY missing")
    payload,_=ApiClient().get("https://v3.football.api-sports.io",key,"fixtures",
                              date=args.date,timezone="Europe/Warsaw")
    if payload.get("errors"):raise RuntimeError(str(payload["errors"]))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"date":args.date,"response":payload.get("response",[])},
                               ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":args.date,"results":len(payload.get("response",[]))}))
if __name__=="__main__":main()
