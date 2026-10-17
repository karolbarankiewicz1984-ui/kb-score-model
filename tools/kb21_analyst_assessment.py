"""Validate analyst-led KB21 sport scoring and pre-market freeze provenance.

Only checks evidence, timing, and STR/QUAL/MATCH arithmetic; NEVER derives
P(model) from Sport Score or market prices. A passing validation requires
separate Calendar Gate review before any operational publication.
"""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

BLOCKS = {"str": 35, "qual": 35, "match": 30}


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _https_url(value):
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname)


def _number(value, low, high):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and low <= value <= high)


def validate(candidate):
    if not isinstance(candidate, dict):
        return {"status": "INVALID", "sport_score": None, "p_model": None,
                "errors": ["Candidate must be an object"],
                "publication": "DIAGNOSTIC / NO PLAY"}

    errors = []
    for field in ("fixture", "market", "analyst", "reasoning"):
        if not isinstance(candidate.get(field), str) or not candidate[field].strip():
            errors.append(f"Missing {field}")

    freeze = _time(candidate.get("freeze_at"))
    kickoff = _time(candidate.get("kickoff"))
    if freeze is None:
        errors.append("freeze_at must have an explicit timezone")
    if kickoff is None:
        errors.append("kickoff must have an explicit timezone")
    if freeze is not None and kickoff is not None and freeze >= kickoff:
        errors.append("freeze_at must be strictly before kickoff")

    score = 0
    score_valid = True
    for block, maximum in BLOCKS.items():
        value = candidate.get(block)
        if not _number(value, 0, maximum):
            errors.append(f"{block} must be a number in 0..{maximum}")
            score_valid = False
        else:
            score += value
        evidence = candidate.get(f"{block}_evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"Missing auditable {block}_evidence")
            continue
        for index, item in enumerate(evidence):
            if not isinstance(item, dict) or not _https_url(item.get("url")) or not (
                isinstance(item.get("note"), str) and item["note"].strip()
            ):
                errors.append(f"Invalid {block}_evidence[{index}] URL/note")
                continue
            observed = _time(item.get("observed_at"))
            if observed is None:
                errors.append(f"Invalid {block}_evidence[{index}] observed_at timezone")
            elif freeze is not None and observed > freeze:
                errors.append(f"{block}_evidence[{index}] observed after pre-market freeze")

    probability = candidate.get("p_model")
    if probability is None:
        errors.append("Missing analyst pre-price p_model")
    elif not _number(probability, 0, 1):
        errors.append("p_model must be a fraction 0..1")
    if not isinstance(candidate.get("p_model_method"), str) or not candidate["p_model_method"].strip():
        errors.append("Missing analyst p_model_method")
    confidence = candidate.get("confidence")
    if not _number(confidence, 0, 10):
        errors.append("confidence must be a number in 0..10")

    # Mixing live bookmaker fields with the pre-market assessment can create
    # hindsight leakage. Market capture belongs in a separate, later stage.
    for field in ("odds", "ev", "bookmaker", "market_signal", "consensus"):
        if field in candidate and candidate[field] is not None:
            errors.append(f"{field} belongs AFTER pre-market freeze, not inside assessment")

    return {
        "status": "REVIEW_REQUIRED" if not errors else "INVALID",
        "sport_score": score if score_valid else None,
        "p_model": probability if _number(probability, 0, 1) else None,
        "errors": errors,
        "publication": "DIAGNOSTIC / NO PLAY",
        "note": "Passing format checks never verifies independent Calendar Gate, probability judgement, or decision. No automatic PLAY.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(source, dict) or not isinstance(source.get("candidates"), list):
        raise ValueError("Input must contain candidates list")
    evaluated = [validate(x) for x in source["candidates"]]
    result = {"candidates": evaluated, "status": "REVIEW_REQUIRED",
              "publication": "DIAGNOSTIC / NO PLAY"}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Validated {len(evaluated)} assessments; no automatic PLAY")


if __name__ == "__main__":
    main()
