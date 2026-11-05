"""Independent public football-data.co.uk CSV ingestion for GitHub Models.

Fetch observation time is the *first time OUR pipeline observed* the results,
not a claim about historical provider publication. Match completion is bounded
conservatively at match date + 2 days; no post-freeze ingestion is allowed.
"""
import argparse
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

LEAGUES = {"E0": "Premier League", "D1": "Bundesliga",
           "I1": "Serie A", "SP1": "La Liga", "F1": "Ligue 1"}
SEASONS = ("2324", "2425", "2526", "2627")

def parse_csv(text, *, league_code, season, observed_at_utc):
    observed = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise ValueError("observed_at_timezone_required")
    accepted = []
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        try:
            if row.get("Div") != league_code:
                continue
            date = row["Date"].strip()
            try:
                day = datetime.strptime(date, "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                day = datetime.strptime(date, "%d/%m/%y").replace(tzinfo=timezone.utc)
            # A conservative bound, NOT the actual completion timestamp.
            completed_bound = day + timedelta(days=2)
            if completed_bound >= observed:
                continue
            home, away = row["HomeTeam"].strip(), row["AwayTeam"].strip()
            hg, ag = int(row["FTHG"]), int(row["FTAG"])
            if not home or not away or home == away or min(hg, ag) < 0:
                continue
            accepted.append(dict(fixture_id=f"fdco:{season}:{league_code}:{day.date()}:{home}:{away}",
                                 league=LEAGUES[league_code], home=home, away=away,
                                 home_goals=hg, away_goals=ag, status="FINISHED",
                                 completed_at_utc=completed_bound.isoformat().replace("+00:00", "Z"),
                                 published_at_utc=observed_at_utc,
                                 source_provider="football-data.co.uk",
                                 source_record_id=f"{season}:{league_code}:{line}"))
        except (KeyError, ValueError, AttributeError, TypeError):
            continue
    return accepted

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="data/github_models/verified_results.json")
    p.add_argument("--manifest", default="data/github_models/source_manifest.json")
    p.add_argument("--timeout", type=int, default=20)
    args = p.parse_args()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    from github_models.kb3_history_bridge import import_verified_results
    rows, sources = [], []
    for season in SEASONS:
        for code in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
            try:
                with urlopen(Request(url, headers={"User-Agent": "github-models-research/1.0"}), timeout=args.timeout) as response:
                    raw = response.read(4_000_000)
                batch = parse_csv(raw.decode("utf-8-sig", errors="replace"),
                                  league_code=code, season=season, observed_at_utc=now)
                rows.extend(batch)
                sources.append(dict(url=url, status="ok", rows=len(batch)))
            except Exception as exc:
                sources.append(dict(url=url, status="error", reason=type(exc).__name__))
    imported = import_verified_results(rows, as_of_utc=now)
    if not imported["accepted"]:
        raise RuntimeError("no_verified_results_ingested")
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(imported["accepted"], ensure_ascii=False, indent=2) + "\n")
    Path(args.manifest).write_text(json.dumps(dict(observed_at_utc=now, sources=sources,
                accepted=imported["accepted_count"], rejected=imported["rejected_count"],
                caveat="observed_at is OUR ingestion timestamp; completion is conservative date+2d bound"),
                ensure_ascii=False, indent=2) + "\n")
    print(f"Imported {imported['accepted_count']} observed historical results")

if __name__ == "__main__":
    main()
