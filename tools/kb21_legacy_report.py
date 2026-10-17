"""Read-only KB Score 2.1 analyst report renderer. No API and no xG dependency.

Usage: python -m tools.kb21_legacy_report input.json --output reports/kb21_legacy/report.md
This does not calculate original analyst-assigned scores or P(model).
"""
import argparse
import json
from pathlib import Path


def render(payload):
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    date = payload.get("date")
    if not isinstance(date, str) or not date:
        raise ValueError("Missing date")
    official = payload.get("official_calendar")
    independent = payload.get("independent_calendar")
    # A self-declared flag is never proof of independent calendar verification.
    # The strict calendar tool only returns BLOCKED or REVIEW_REQUIRED.
    verified = False
    out = [f"# KB Score 2.1 — analyst recovery — {date}", "",
           "**Mode:** MANUAL / REVIEW; not a restored automatic LIVE engine.",
           f"**Calendar Gate:** {'PASS' if verified else 'BLOCKED / REVIEW REQUIRED — no independent source verification'}",
           f"**Official calendar:** {official or 'MISSING'}",
           f"**Independent calendar:** {independent or 'MISSING'}", ""]
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    for i, c in enumerate(candidates, 1):
        if not isinstance(c, dict):
            raise ValueError("candidate must be an object")
        name = c.get("fixture", "UNSPECIFIED")
        out += [f"## {i}. {name}", f"**Market:** {c.get('market', 'UNSPECIFIED')}",
                f"**Kickoff:** {c.get('kickoff', 'UNVERIFIED')}",
                f"**Evidence:** {c.get('evidence', 'MISSING')}",
                f"**xG:** {c.get('xg', 'unavailable / not mandatory')}",
                f"**Analyst STR/QUAL/MATCH:** {c.get('str', '—')}/35 + {c.get('qual', '—')}/35 + {c.get('match', '—')}/30",
                f"**P(model):** {c.get('p_model', 'UNDETERMINED')}",
                f"**Confidence:** {c.get('confidence', 'UNDETERMINED')}",
                f"**Consensus:** {c.get('consensus', 'UNDETERMINED')}",
                f"**Odds:** {c.get('odds', 'UNAVAILABLE')}",
                f"**Assessment:** {c.get('reasoning', 'NOT PROVIDED')}", ""]
        # Never auto-promote analyst input to PLAY without full validated gate.
        out += ["**Publication status:** DIAGNOSTIC / NO PLAY (recovery mode)", ""]
    if not candidates:
        out += ["No verified candidates supplied. No recommendations.", ""]
    out += ["---", "No changes to historical N, Google Sheet, or API Market. No invented xG, prices or probabilities.", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(payload), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
