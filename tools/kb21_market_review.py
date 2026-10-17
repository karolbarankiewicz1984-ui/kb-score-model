"""Independent post-freeze market review for original analyst-led KB Score 2.1.

Pure arithmetic, not a betting engine: only evaluate frozen human P(model)
against a later timestamped quote. NEVER approves PLAY or alters historical N.
"""
import argparse
import json
import math
from pathlib import Path

from tools.kb21_analyst_assessment import _time, validate


def review(assessment, quote):
    pre = validate(assessment)
    errors = list(pre["errors"])
    if not isinstance(quote, dict):
        errors.append("Missing market quote")
        quote = {}
    if assessment and quote.get("market") != assessment.get("market"):
        errors.append("Quoted market differs from frozen pre-price market")
    if assessment and quote.get("fixture_id") != assessment.get("fixture_id"):
        errors.append("Quoted fixture_id differs from frozen event")
    price = quote.get("odds")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or (
        not math.isfinite(price) or price <= 1
    ):
        errors.append("Decimal odds must be a finite number above 1")
        price = None

    quote_time = _time(quote.get("quoted_at"))
    freeze = _time(assessment.get("freeze_at")) if isinstance(assessment, dict) else None
    kickoff = _time(assessment.get("kickoff")) if isinstance(assessment, dict) else None
    if quote_time is None:
        errors.append("Price quoted_at must have an explicit timezone")
    elif freeze is not None and quote_time <= freeze:
        errors.append("Market quote must be captured strictly AFTER P(model) freeze")
    if quote_time is not None and kickoff is not None and quote_time >= kickoff:
        errors.append("Market quote must be captured BEFORE kickoff")
    if not isinstance(quote.get("bookmaker"), str) or not quote["bookmaker"].strip():
        errors.append("Missing bookmaker provenance")

    if errors:
        return {"status": "BLOCKED", "errors": errors,
                "publication": "DIAGNOSTIC / NO PLAY",
                "sport_score": None, "p_model": None, "implied_probability": None,
                "fair_odds": None, "ev": None, "min_ev_guideline": None,
                "meets_ev_guideline": False}

    prob = pre["p_model"]
    confidence = assessment["confidence"]
    threshold = .02 if confidence >= 8 else .035 if confidence >= 6 else .05 if confidence >= 5 else None
    ev = prob * price - 1
    return {
        "status": "REVIEW_REQUIRED",
        "publication": "DIAGNOSTIC / NO PLAY",
        "sport_score": pre["sport_score"],
        "p_model": prob,
        "confidence": confidence,
        "implied_probability": 1 / price,
        "fair_odds": 1 / prob if prob > 0 else None,
        "ev": ev,
        "min_ev_guideline": threshold,
        "meets_ev_guideline": threshold is not None and ev >= threshold,
        "errors": [],
        "note": "EV threshold is a guideline only. Calendar, lineup, market, data, and human decision gates remain unverified. Never auto-PLAY.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not isinstance(records.get("reviews"), list):
        raise ValueError("Input requires reviews list")
    results = [review(item.get("assessment", {}), item.get("quote", {}))
               for item in records["reviews"]]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"publication": "DIAGNOSTIC / NO PLAY", "reviews": results},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} KB21 market reviews, zero automatic PLAY")


if __name__ == "__main__":
    main()
