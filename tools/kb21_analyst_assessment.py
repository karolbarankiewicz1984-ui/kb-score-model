"""Validate analyst-assigned KB21 sport scores without inventing P(model).

This is a PRE-MARKET assessment validator, not an automated betting model.
Does not touch the historical register or experimental API engine.
"""
import argparse
import json
from pathlib import Path

BLOCKS = {"str": 35, "qual": 35, "match": 30}


def validate(candidate):
    errors = []
    if not isinstance(candidate, dict):
        return {"status": "INVALID", "errors": ["Candidate must be an object"]}
    for field in ("fixture", "market", "freeze_at", "analyst", "reasoning"):
        if not isinstance(candidate.get(field), str) or not candidate[field].strip():
            errors.append(f"Missing {field}")
    score = 0
    for key, maximum in BLOCKS.items():
        value = candidate.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= maximum:
            errors.append(f"{key} must be a number in 0..{maximum}")
        else:
            score += value
        evidence = candidate.get(f"{key}_evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, dict) and x.get("url", "").startswith("https://") and x.get("observed_at") and x.get("note") for x in evidence):
            errors.append(f"Missing auditable {key}_evidence")
    probability = candidate.get("p_model")
    if probability is not None and (isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 <= probability <= 1):
        errors.append("p_model must be a fraction 0..1 or null")
    if probability is not None and not candidate.get("p_model_method"):
        errors.append("Missing analyst p_model_method")
    confidence = candidate.get("confidence")
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 10):
        errors.append("confidence must be 0..10 or null")
    return {"status": "REVIEW_REQUIRED" if not errors else "INVALID", "sport_score": score if not any(e.startswith(tuple(BLOCKS)) for e in errors) else None,
            "p_model": probability, "errors": errors,
            "publication": "DIAGNOSTIC / NO PLAY",
            "note": "Human scores and P(model) are NOT inferred from results, odds, or a replacement formula."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = {"candidates": [validate(x) for x in source.get("candidates", [])], "status": "REVIEW_REQUIRED", "publication": "DIAGNOSTIC / NO PLAY"}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Validated {len(result['candidates'])} assessments; no automatic PLAY")


if __name__ == "__main__":
    main()
