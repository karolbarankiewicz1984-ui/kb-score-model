"""Make a readable three-day candidate fixture digest from ESPN JSON snapshots.
This is discovery only, never a KB21 PLAY report or a verified Calendar Gate.
Usage: python -m tools.kb21_fixture_digest day1.json day2.json day3.json --output digest.md
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def render(paths):
    out = ["# KB Score 2.1 — trzydniowy przegląd terminarza (kandydaci)", "",
           "**STATUS: NIEZWERYFIKOWANY. Calendar Gate BLOCKED. Bez typów PLAY i bez P(model).**", "",
           "Źródło pomocnicze: ESPN. Wymagana osobna weryfikacja z oficjalnym terminarzem organizatora.", ""]
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        fixtures = data.get("fixtures", [])
        out.extend([f"## {data.get('date', 'brak daty')} — {len(fixtures)} kandydatów", "",
                    f"Status pobierania: {data.get('status', 'BRAK')}; błędy lig: {len(data.get('errors', []))}", ""])
        for f in sorted(fixtures, key=lambda item: item.get("kickoff", "")):
            kickoff = f.get("kickoff", "")
            try:
                kickoff = datetime.fromisoformat(kickoff.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Warsaw")).strftime("%H:%M")
            except (TypeError, ValueError):
                kickoff = "?"
            out.append(f"- {kickoff} PL | {f.get('league', '?')} | {f.get('home', '?')} – {f.get('away', '?')} | ESPN ID: {f.get('event_id', '?')}")
        if not fixtures:
            out.append("- Brak danych. Nie oznacza to braku spotkań.")
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.inputs), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
