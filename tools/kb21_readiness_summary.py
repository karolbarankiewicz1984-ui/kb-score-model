"""Read-only KB21 daily readiness summary."""
import json
import sys
from pathlib import Path

def render(gate, calendar=None):
    lines = ["# KB21 readiness: " + str(gate.get("date")), "", "Diagnostic only: not PLAY, not original model predictions.", "", "Checked: " + str(gate.get("total", 0)), "Blocked: " + str(gate.get("blocked", 0)), "Ready for review: " + str(gate.get("ready_for_review", 0)), "Historical N changes: 0", "Register writes: none", "", "## Blockers"]
    lines += [f"- {k}: {v}" for k, v in sorted(gate.get("blocker_counts", {}).items())]
    lines += ["", "## Independent calendar"]
    if calendar is None:
        lines.append("No independent calendar comparison available.")
    else:
        rows = calendar.get("rows", [])
        lines.append(f"Name/time matches for review: {sum(bool(r.get('independent_match')) for r in rows)} / {len(rows)}")
    lines += ["", "No fixture is automatically officially verified. Genuine xG and original 35/35/30 components remain required.", ""]
    return "\n".join(lines)

if __name__ == "__main__":
    gate = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    cal = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv)>3 and Path(sys.argv[2]).is_file() else None
    out = Path(sys.argv[-1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(gate, cal), encoding="utf-8")
