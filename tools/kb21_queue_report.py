"""Render KB Score 2.1 three-day *diagnostic* analyst worksheets.

No invented P(model), scores, xG, odds, Calendar Gate PASS, or PLAY.
These are source-linked triage worksheets, NOT operational daily KB21 picks.
"""
import argparse
import json
from pathlib import Path

from tools.kb21_analyst_assessment import validate


def render_day(queue, day):
    if not isinstance(queue, dict) or not isinstance(queue.get("fixtures"), list):
        raise ValueError("Expected KB21 queue JSON with fixtures list")
    selected = [f for f in queue["fixtures"] if f.get("date_warsaw") == day]
    errors = queue.get("source_errors", [])
    out = [
        f"# KB Score 2.1 — karta analityczna — {day}", "",
        "**TRYB: DIAGNOSTYCZNY / NO PLAY. Oryginalny model NIE jest jeszcze przywrócony.**",
        "**Calendar Gate: BLOCKED — brak zweryfikowanej, kompletnej karty oficjalnej.**",
        "Źródło kandydatów: ESPN (nieoficjalne); wymagane oficjalne źródło organizatora i niezależna kontrola.",
        "Sport Score = STR /35 + QUAL /35 + MATCH /30. P(model) wymaga uzasadnionej oceny analitycznej PRZED kursem.",
        "Żadne wpisy nie są dopisywane do historycznego rejestru ani licznika N.",
        "",
        f"**Mecze z listy pomocniczej:** {len(selected)} | **Błędy pobierania źródeł (łącznie):** {len(errors)}",
        "",
    ]
    status = queue.get("crosscheck_summary", {}).get(day, {})
    if status:
        out.append(f"**Niezależny terminarz dostępny:** {'TAK' if status.get('snapshot_loaded') else 'NIE'}")
        out.append(f"**Porównane pozycje (do przeglądu, NIE weryfikacja oficjalna):** {status.get('statuses', {}).get('MATCHED_FOR_REVIEW', 0)}")
        out.append("")
    if not selected:
        out.extend(["Nie znaleziono kandydatów na tę datę. Nie dowodzi to braku meczów.", ""])
    for number, fixture in enumerate(selected, 1):
        form = fixture.get("assessment", {})
        result = validate(form)
        valid = result["status"] == "REVIEW_REQUIRED"
        score = result.get("sport_score") if valid else None
        p = result.get("p_model") if valid else None
        score_label = ("{}/35 + {}/35 + {}/30 = {}/100".format(
            form.get("str"), form.get("qual"), form.get("match"), score)
            if score is not None else "BRAK ZWERYFIKOWANEJ OCENY")
        research = fixture.get("pre_match_research") or {}
        context = research.get("context") or {}
        history = []
        for side, name in (("home", "Gospodarze"), ("away", "Goście")):
            stats = context.get(side)
            if stats:
                history.append(
                    f"{name}: {stats['previous_completed_matches']} wcześniejszych meczów, "
                    f"gole strzelone {stats['goals_for_per_match']:.2f}/mecz, "
                    f"stracone {stats['goals_against_per_match']:.2f}/mecz"
                )
        history_line = "; ".join(history) if history else "BRAK SPRAWDZONYCH DANYCH HISTORYCZNYCH"
        out.extend([
            f"## {number}. {fixture.get('fixture', 'Nieustalone spotkanie')}",
            f"- Liga: {fixture.get('competition', '?')} ({fixture.get('fixture_id', '?')})",
            f"- Start (Warszawa): {fixture.get('kickoff', '?')}",
            f"- Mecz i rozgrywki potwierdzone oficjalnie: NIE",
            f"- Niezależne zestawienie: {fixture.get('independent_crosscheck', {}).get('status', 'NIE WYKONANO')}",
            f"- Identyfikator w drugim źródle: {fixture.get('independent_crosscheck', {}).get('provider_match_id') or 'BRAK'}",
            f"- Statystyki historyczne (gole, NIE xG): {history_line}",
            f"- Źródło historii: {context.get('source_file') or 'BRAK'}, stan: {research.get('status', 'NIE POBRANO')}",
            f"- Rynek: {form.get('market') or 'DO UZUPEŁNIENIA'}",
            f"- STR / QUAL / MATCH: {score_label}",
            f"- P(model): {f'{p:.1%}' if p is not None else 'NIE WYZNACZONO'}",
            f"- Data freeze: {form.get('freeze_at') or 'BRAK'}",
            f"- Analiza: {result['status']}; liczba braków/błędów: {len(result['errors'])}",
            "- Decyzja: NO PLAY (Calendar Gate BLOCKED)",
            "",
        ])
    out += [
        "## Czego brakuje do pełnej analizy",
        "Oficjalne terminarze wszystkich wymaganych rozgrywek, niezależna kontrola kompletności,",
        "dowody STR/QUAL/MATCH, pre-price P(model), freeze przed meczem, ocena jakości i ryzyka.",
        "Ceny, EV i decyzje rynkowe dopiero po zamrożeniu oceny sportowej.", "",
    ]
    return "\n".join(out)


def render_index(queue, days):
    out = ["# KB Score 2.1 — kolejka do oceny", "",
           "**WYŁĄCZNIE DIAGNOSTYKA / NO PLAY. Calendar Gate BLOCKED.**", ""]
    for day in days:
        matches = [f for f in queue.get("fixtures", []) if f.get("date_warsaw") == day]
        count = len(matches)
        history = sum(f.get("pre_match_research", {}).get("status") == "PRIOR_GOAL_CONTEXT"
                      for f in matches)
        crosschecked = sum(f.get("independent_crosscheck", {}).get("status") == "MATCHED_FOR_REVIEW"
                           for f in matches)
        out.append(f"- {day}: {count} kandydatów, {history} z historią poprzednich meczów, "
                   f"{crosschecked} zgodnych u obu dostawców; "
                   f"KB21_ANALYST_QUEUE_{day}.md")
    out += ["", "Każdy dokument jest szablonem do przedmeczowej oceny, nie typem bukmacherskim.", ""]
    return "\n".join(out)


def write_reports(queue, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    days = sorted(set(queue.get("days", [])) | {
        f.get("date_warsaw") for f in queue.get("fixtures", []) if f.get("date_warsaw")
    })
    for day in days:
        (output / f"KB21_ANALYST_QUEUE_{day}.md").write_text(
            render_day(queue, day), encoding="utf-8"
        )
    (output / "KB21_ANALYST_QUEUE_INDEX.md").write_text(
        render_index(queue, days), encoding="utf-8"
    )
    return days


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue")
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    days = write_reports(queue, args.outdir)
    print(f"Created {len(days)} dated KB21 worksheets (all DIAGNOSTIC / NO PLAY)")


if __name__ == "__main__":
    main()
