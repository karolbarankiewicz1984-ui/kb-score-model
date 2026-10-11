"""KB Score 2.1: reproducible pre-match calculation core.

Requires an independently verified pre-match input JSON. Does not scrape data,
write Google Sheets, or change historical KB probabilities.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

def required_number(data, key, low, high):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key}: required finite number in [{low}, {high}]")
    return float(value)

def calculate(record, now=None):
    """Returns a candidate, never a PLAY decision or a register observation."""
    now = now or dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.fromisoformat(record["kickoff_utc"].replace("Z", "+00:00"))
    if start.tzinfo is None or start <= now:
        raise ValueError("Pre-match freeze only: kickoff must be future and timezone-aware")
    if not record.get("fixture_verified_official") or not record.get("fixture_verified_independent"):
        raise ValueError("Calendar Gate: official and independent fixture verification required")
    if not record.get("sources") or len(record["sources"]) < 2:
        raise ValueError("At least two source references required")
    if not record.get("snapshot_utc"):
        raise ValueError("Dated pre-match input snapshot required")
    snap = dt.datetime.fromisoformat(record["snapshot_utc"].replace("Z", "+00:00"))
    if snap.tzinfo is None or snap > now or snap >= start:
        raise ValueError("Input snapshot must be timezone-aware and pre-match")
    # Three independently documented, normalized score contributions.
    structural = required_number(record, "structural_0_100", 0, 100)
    quality = required_number(record, "quality_0_100", 0, 100)
    matchup = required_number(record, "matchup_0_100", 0, 100)
    sport_score = round(.35 * structural + .35 * quality + .30 * matchup, 3)
    # Goals model is independent of price. Requires separately sourced expected goals.
    home_xg = required_number(record, "home_expected_goals", .05, 6)
    away_xg = required_number(record, "away_expected_goals", .05, 6)
    def poisson(lam, k):
        return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))
    h = [poisson(home_xg, i) for i in range(30)]
    a = [poisson(away_xg, i) for i in range(30)]
    win = sum(h[i] * a[j] for i in range(30) for j in range(i))
    draw = sum(h[i] * a[i] for i in range(30))
    lose = sum(h[i] * a[j] for i in range(30) for j in range(i + 1, 30))
    probabilities = {"home": win, "draw": draw, "away": lose,
                     "over_2_5": 1 - math.exp(-(home_xg + away_xg)) * (1 + home_xg + away_xg + (home_xg + away_xg)**2 / 2),
                     "btts_yes": (1 - math.exp(-home_xg)) * (1 - math.exp(-away_xg))}
    selection = record["selection"]
    if selection not in probabilities:
        raise ValueError("Unsupported market; use home/draw/away/over_2_5/btts_yes")
    p = probabilities[selection]
    # P(cal) requires empirical out-of-sample calibration; never fabricate bins.
    p_cal = None
    odds = record.get("decimal_odds")
    if odds is not None:
        odds = required_number(record, "decimal_odds", 1.001, 1000)
    return {"event":record["event"], "kickoff_utc":record["kickoff_utc"],
            "snapshot_utc":record["snapshot_utc"], "selection":selection,
            "sport_score":sport_score, "sport_components":{"structural":structural,"quality":quality,"matchup":matchup},
            "p_model":round(p,6), "p_cal_diagnostic":p_cal,
            "fair_odds":round(1/p,4), "implied_probability":round(1/odds,6) if odds else None,
            "ev":round(p*odds-1,6) if odds else None,
            "status":"CANDIDATE_ONLY", "market_signal":None,
            "sources":record["sources"], "note":"Provisional Poisson implementation; not historically validated KB 2.1. No PLAY/freeze without validation."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input",help="Verified pre-match JSON")
    parser.add_argument("--output",help="Output JSON path")
    args=parser.parse_args()
    result=calculate(json.loads(Path(args.input).read_text(encoding="utf-8")))
    payload=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output: Path(args.output).write_text(payload+"\n",encoding="utf-8")
    else: print(payload)

if __name__=="__main__": main()
