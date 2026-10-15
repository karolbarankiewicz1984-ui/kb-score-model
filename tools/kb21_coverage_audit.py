"""Read-only coverage diagnostics: never confuses missing provider coverage with missing fixtures."""
import argparse
import json
from collections import Counter
from pathlib import Path

# Only explicit known mapping; do not infer provider coverage from similarly named competitions.
CODES = {
    ("England", "Premier League"): "PL",
    ("Spain", "La Liga"): "PD",
    ("Italy", "Serie A"): "SA",
    ("Germany", "Bundesliga"): "BL1",
    ("France", "Ligue 1"): "FL1",
    ("Portugal", "Primeira Liga"): "PPL",
    ("Netherlands", "Eredivisie"): "DED",
    ("UEFA Champions League",): "CL",
}
def audit(api, coverage):
    available = {x.get("code") for x in coverage.get("competitions", [])}
    groups = {}
    for row in api.get("candidates", []):
        league = row.get("league")
        country = row.get("league_country")
        key = (country, league) if (country, league) in CODES else (league,)
        code = CODES.get(key)
        label = f"{country or '?'} / {league or '?'}"
        entry = groups.setdefault(label, {"league": league, "country": country, "count": 0,
            "independent_code": code, "coverage": "SUPPORTED_BY_PROVIDER" if code in available else
            "NOT_IN_PROVIDER_COVERAGE" if code else "NO_VERIFIED_PROVIDER_MAPPING"})
        entry["count"] += 1
    counts = Counter(x["coverage"] for x in groups.values() for _ in range(x["count"]))
    return {"date": api.get("date"), "status": "COVERAGE_DIAGNOSTIC_ONLY",
        "candidate_count": len(api.get("candidates", [])), "by_coverage": dict(counts),
        "leagues": sorted(groups.values(), key=lambda x: (-x["count"], x["league"] or "")),
        "note": "Provider coverage does not verify individual fixtures. Official league evidence remains mandatory.",
        "kb_n_effect": 0, "dev_n_effect": 0, "register_writes": False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("api_input")
    p.add_argument("coverage_input")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = audit(json.loads(Path(a.api_input).read_text(encoding="utf-8")),
                   json.loads(Path(a.coverage_input).read_text(encoding="utf-8")))
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "by_coverage": result["by_coverage"]}))

if __name__ == "__main__":
    main()
