"""Score prospectively archived shot forecasts against independent public results."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from math import fsum, log
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from github_models.shots_research import FAMILIES, FREEZE_SCHEMA, HISTORY_SOURCE, SCOPES, SELECTIONS, half_line, number, timestamp
from github_models.shots_shadow import read, write_new
from tools.pitchapi_xg_lab import competition, norm

# League matches have regulation-time team aggregates. Use the exact national
# division, ordered team names and local calendar day for the independent join.
DIVISIONS = {
    ("ENG", "premier league"): ("E0", "Europe/London"),
    ("ENG", "championship"): ("E1", "Europe/London"),
    ("DEU", "bundesliga"): ("D1", "Europe/Berlin"),
    ("ITA", "serie a"): ("I1", "Europe/Rome"),
    ("ITA", "serie b"): ("I2", "Europe/Rome"),
    ("ESP", "la liga"): ("SP1", "Europe/Madrid"),
    ("FRA", "ligue 1"): ("F1", "Europe/Paris"),
    ("FRA", "ligue 2"): ("F2", "Europe/Paris"),
    ("NLD", "eredivisie"): ("N1", "Europe/Amsterdam"),
    ("PRT", "primeira liga"): ("P1", "Europe/Lisbon"),
    ("BEL", "jupiler pro league"): ("B1", "Europe/Brussels"),
    ("TUR", "super lig"): ("T1", "Europe/Istanbul"),
}
CSV_ALIASES = {"man united": "manchester united", "ath madrid": "atletico madrid",
               "fc koln": "koln", "1 fc koln": "koln", "inter": "internazionale",
               "paris sg": "paris saint germain", "bayern munich": "bayern munich",
               "wolves": "wolverhampton wanderers", "wolverhampton": "wolverhampton wanderers"}
COLUMNS = {"shots_total": ("HS", "AS"), "shots_on_target": ("HST", "AST")}
RESULT_SOURCE = "football-data.co.uk"
EPSILON = 1e-15  # Finite log-loss only. The published forecast is never clipped.
PUBLICATION_DELAY = timedelta(hours=48)


def _team(name):
    return CSV_ALIASES.get(norm(name), norm(name))


def _fixture_key(fixture):
    country = fixture.get("country_code")
    league = competition(fixture.get("league"))
    if country == "BEL" and league == "first division a":
        league = "jupiler pro league"
    division = DIVISIONS.get((country, league))
    if not division:
        return None
    code, zone = division
    day = timestamp(fixture["kickoff_utc"]).astimezone(ZoneInfo(zone)).date()
    season_start = day.year - (day.month < 7)
    season = f"{season_start % 100:02d}{(season_start + 1) % 100:02d}"
    return season, code, day, _team(fixture["home"]), _team(fixture["away"])


def parse_csv(raw, season, code, observed_at_utc):
    """Independently published regulation-time count fields and source provenance."""
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
    digest = sha256(raw).hexdigest()
    for i, row in enumerate(csv.DictReader(StringIO(raw.decode("utf-8-sig", errors="replace"))), 2):
        if row.get("Div") != code or not row.get("HomeTeam") or not row.get("AwayTeam"):
            continue
        try:
            date_text = row["Date"].strip()
            date_format = "%d/%m/%Y" if len(date_text.rsplit("/", 1)[-1]) == 4 else "%d/%m/%y"
            day = datetime.strptime(date_text, date_format).date()
            home, away = int(row["FTHG"]), int(row["FTAG"])
            if min(home, away) < 0 or row.get("FTR") != ("H" if home > away else "A" if home < away else "D"):
                continue
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        counts = {}
        for family, columns in COLUMNS.items():
            try:
                pair = tuple(int(row[c]) for c in columns)
                if min(pair) >= 0 and max(pair) <= 200:
                    counts[family] = pair
            except (KeyError, TypeError, ValueError):
                continue
        if all(f in counts for f in FAMILIES) and any(
                target > total for total, target in zip(*(counts[f] for f in FAMILIES))):
            continue
        key = (season, code, day, _team(row["HomeTeam"]), _team(row["AwayTeam"]))
        yield key, {"counts": counts, "source": RESULT_SOURCE, "source_url": url, "source_sha256": digest,
                    "source_row": i, "observed_at_utc": observed_at_utc, "period": "fulltime"}


def _load_csv(division):
    season, code = division
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
    try:
        with urlopen(Request(url, headers={"User-Agent": "multimodel-shots-research/1.0"}), timeout=12) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("results_file_too_large")
        observed = datetime.now(timezone.utc).isoformat()
        return list(parse_csv(raw, season, code, observed)), None
    except (OSError, URLError, ValueError) as exc:
        return [], {"source_url": url, "reason": type(exc).__name__}


def _usable_rows(archives, as_of):
    """Keep the first verifiable freeze per exact selection and reject replays."""
    archived = []
    for freeze, uploaded_at in archives:
        if (freeze.get("schema") != FREEZE_SCHEMA or freeze.get("mode") != "prospective"
                or freeze.get("training_source") != HISTORY_SOURCE):
            continue
        frozen, uploaded = timestamp(freeze["frozen_at_utc"]), timestamp(uploaded_at)
        if not timestamp(freeze["queue_cutoff_utc"]) <= frozen <= uploaded <= as_of:
            continue
        for item in freeze["fixtures"]:
            f = item["identity"]
            kickoff = timestamp(f["kickoff_utc"])
            if uploaded >= kickoff:
                continue
            for row in item["candidates"]:
                p = row.get("probability")
                if (row.get("fixture_id") != f["fixture_id"] or row.get("market") not in FAMILIES
                        or row.get("scope") not in SCOPES or row.get("selection") not in SELECTIONS
                        or row.get("period") != "fulltime" or not half_line(row.get("line"))
                        or not number(p) or not 0 <= p <= 1):
                    continue
                key = tuple(row[k] for k in ("fixture_id", "market", "scope", "line", "selection"))
                archived.append((uploaded, frozen, key, row, f, uploaded_at, freeze["frozen_at_utc"]))
    selected = {}
    for _, _, key, row, f, uploaded, frozen in sorted(archived, key=lambda x: x[:3]):
        selected.setdefault(key, (row, f, uploaded, frozen))
    return selected.values()


def audit(archives, outcomes=None, *, as_of_utc=None):
    # Use an explicit cutoff for deterministic read-only replays and tests.
    now = timestamp(as_of_utc) if as_of_utc else datetime.now(timezone.utc)
    forecasts = _usable_rows(archives, now)
    errors = []
    if outcomes is None:
        divisions = {key[:2] for _, f, _, _ in forecasts
                     if timestamp(f["kickoff_utc"]) + PUBLICATION_DELAY <= now
                     and (key := _fixture_key(f))}
        outcomes = defaultdict(list)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for rows, error in executor.map(_load_csv, sorted(divisions)):
                for key, item in rows:
                    outcomes[key].append(item)
                if error:
                    errors.append(error)
        if not as_of_utc:
            now = datetime.now(timezone.utc)
    details, summary = [], []
    for row, fixture, uploaded, frozen in forecasts:
        kickoff = timestamp(fixture["kickoff_utc"])
        key = _fixture_key(fixture)
        observed = outcomes.get(key, ())
        result = {**row, "frozen_at_utc": frozen, "archived_at_utc": uploaded,
                  "kickoff_utc": fixture["kickoff_utc"]}
        if now < kickoff + PUBLICATION_DELAY:
            result["status"] = "pending_publication"
        elif not key:
            result["status"] = "independent_division_unavailable"
        elif len(observed) != 1:
            result["status"] = "ambiguous_result" if observed else "independent_result_unavailable"
        else:
            evidence = observed[0]
            available = timestamp(evidence["observed_at_utc"])
            counts = evidence.get("counts", {}).get(row["market"])
            if (evidence.get("source") != RESULT_SOURCE or evidence.get("period") != "fulltime"
                    or not kickoff + PUBLICATION_DELAY <= available <= now
                    or not counts or len(counts) != 2 or any(type(c) is not int or c < 0 for c in counts)):
                result["status"] = "independent_counts_unavailable"
            else:
                count = {"home": counts[0], "away": counts[1], "match": sum(counts)}[row["scope"]]
                hit = int((count > row["line"]) == (row["selection"] == "over"))
                p = row["probability"]
                result.update(status="settled", observed_count=count, outcome=hit,
                              brier=(p - hit) ** 2, log_loss=-log(max(EPSILON, p if hit else 1. - p)),
                              result_evidence={k: v for k, v in evidence.items() if k != "counts"})
        details.append(result)
    for family in FAMILIES:
        for scope in SCOPES:
            group = [r for r in details if r["market"] == family and r["scope"] == scope]
            valid = [r for r in group if r["status"] == "settled"]
            summary.append({"market": family, "scope": scope, "forecasts": len(group),
                            "settled": len(valid), "distinct_fixtures": len({r["fixture_id"] for r in valid}),
                            "brier": fsum(r["brier"] for r in valid) / len(valid) if valid else None,
                            "log_loss": fsum(r["log_loss"] for r in valid) / len(valid) if valid else None})
    return {"schema": "multimodel-shots-outcomes-v1", "as_of_utc": now.isoformat(),
            "status": dict(Counter(r["status"] for r in details)), "summary": summary, "rows": details,
            "distinct_settled_fixtures": len({r["fixture_id"] for r in details if r["status"] == "settled"}),
            "source_errors": errors, "calibration_authorized": False}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, help="List of downloaded artifacts and GitHub creation timestamps")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    index = read(args.index)
    archives = [(read(Path(args.index).parent / item["path"]), item["created_at"]) for item in index]
    result = audit(archives)
    write_new(args.output, result)
    print(json.dumps({k: result[k] for k in ("status", "distinct_settled_fixtures", "source_errors")}))


if __name__ == "__main__":
    main()
