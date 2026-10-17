"""Read-only KB21 daily readiness summary."""
import json
import sys
from pathlib import Path

def render(gate, calendar=None):
    lines = ["# KB21 readiness: " + str(gate.get("date")), "", "Diagnostic only: not PLAY, not original model predictions.", "", "Checked: " + str(gate.get("total", 0)), "Blocked: " + str(gate.get("blocked", 0)), "Ready for review: " + str(gate.get("ready_for_review", 0)), "Historical N changes: 0", "Register writes: none", "", "## Blockers"]
    lines += [f"- {k}: {v}" for k, v in sorted(gate.get("blocker_counts", {}).items())]
    lines += ["", "## Optional-data warnings (not LIVE scoring blockers)"]
    lines += [f"- {k}: {v}" for k, v in sorted(gate.get("warning_counts", {}).items())]
    lines += ["", "## Independent calendar"]
    if calendar is None:
        lines.append("No independent calendar comparison available.")
    else:
        rows = calendar.get("rows", [])
        lines.append(f"Name/time matches for review: {sum(bool(r.get('independent_match')) for r in rows)} / {len(rows)}")
    lines += ["", "No fixture is automatically officially verified. Genuine xG is OPTIONAL in original KB21. Original analyst-led STR/QUAL/MATCH and pre-price P(model), verified calendars, and human review remain missing.", ""]
    return "\n".join(lines)

if __name__ == "__main__":
    gate = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    cal = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv)>3 and Path(sys.argv[2]).is_file() else None
    out = Path(sys.argv[-1])
    out.parent.mkdir(parents=True, exist_ok=True)
    markdown = render(gate, cal)
    # Read-only companion; NEVER use PitchAPI to bypass the KB21 readiness gate.
    companion = Path("data/pitchapi/prematch") / f"{gate.get('date')}.json"
    if companion.is_file():
        try:
            xg = json.loads(companion.read_text(encoding="utf-8"))
            if (xg.get("schema") == "pitchapi-prematch-context-v1"
                    and xg.get("target_date") == gate.get("date")):
                markdown += (
                    "\n## PitchAPI — context of previous matches only\n"
                    f"- Upcoming fixtures in source: {xg.get('fixtures_collected', 0)}\n"
                    f"- Both clubs with at least three prior matches: "
                    f"{xg.get('fixtures_with_both_sides_sufficient', 0)}\n"
                    "- See: reports/pitchapi/prematch/" + str(gate.get("date")) + ".md\n"
                    "- Not calendar verification, not analyst 35/35/30, "
                    "not expected goals for this fixture; readiness unchanged.\n"
                )
        except (OSError, ValueError):
            pass
    out.write_text(markdown, encoding="utf-8")
