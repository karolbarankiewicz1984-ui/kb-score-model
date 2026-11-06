"""Collect independent historical event statistics, retaining missing markets."""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from github_models.event_parser import parse_events
from github_models.public_results import LEAGUES, SEASONS

def main():
    rows, sources = [], []
    for season in SEASONS:
        for code, league in LEAGUES.items():
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
            try:
                with urlopen(Request(url, headers={"User-Agent":"research-events/1.0"}), timeout=20) as response:
                    raw = response.read(4000000)
                    if len(raw) >= 4000000:
                        raise ValueError("historical_response_size_limit")
                observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                data = raw.decode("utf-8-sig", errors="replace")
                batch = parse_events(data, league, observed_at, league_code=code, season=season)
                rows.extend(batch)
                sources.append({"url":url,"rows":len(batch),"status":"ok", "observed_at_utc":observed_at,
                                "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
            except Exception as exc:
                sources.append({"url":url,"status":"error","reason":type(exc).__name__})
    if not rows:
        raise RuntimeError("no_event_history")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    dest = Path("data/github_models/verified_events.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, ensure_ascii=False)+"\n")
    Path("data/github_models/events_manifest.json").write_text(json.dumps(
        {"observed_at_utc":now,"sources":sources,"count":len(rows)})+"\n")
    print("Event history:",len(rows),"coverage:",
          {k:sum(k in r["events"] for r in rows) for k in ("corners","cards","fouls")})

if __name__ == "__main__":
    main()
