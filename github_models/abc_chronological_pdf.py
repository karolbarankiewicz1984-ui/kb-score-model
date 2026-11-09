"""Full chronological A/B/C report: shortlist first, then EVERY daily market.

Rendering only; never alters forecasting, thresholds or archived JSON.
The same position in nested A/B/C variants is displayed once with badges.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from github_models.abc_pdf_style import fonts, p, render, styles, table

ZONE = ZoneInfo("Europe/Warsaw")
MARKETS = {"1X2": "Wynik 1X2", "goals": "Bramki", "fouls": "Faule",
           "cards": "Żółte kartki", "corners": "Rożne"}
ORDER = {"1X2": 0, "goals": 1, "fouls": 2, "cards": 3, "corners": 4}
PRIORITY = {"A": 0, "B": 1, "C": 2}
LIMIT_TOP = 12

def date_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(ZONE)
    except (ValueError, TypeError, OverflowError):
        return None

def prob(row):
    x = row.get("probability_min", row.get("probability"))
    if type(x) not in (int, float) or not 0 <= x <= 1:
        raise ValueError("invalid_report_probability")
    return float(x)

def line_str(value):
    return str(value).replace(".", ",")

def market_str(row):
    name = MARKETS.get(row["market"], str(row["market"]))
    if row["market"] == "1X2":
        sel = {"1": "1 – gospodarze", "X": "X – remis",
               "2": "2 – goście"}.get(row["selection"], str(row["selection"]))
        return name + ": " + sel
    direction = {"over": "Powyżej", "under": "Poniżej"}.get(
        row["selection"], str(row["selection"]))
    return name + ": " + direction + " " + line_str(row.get("line", "?"))

def row_key(row):
    return (str(row["fixture_id"]), str(row["market"]), str(row.get("line")),
            str(row["selection"]), str(row.get("model", "")))

def collapse(candidates):
    """Fold repeated A/B/C variant memberships, without dropping distinct lines/models."""
    result = {}
    for candidate in candidates:
        key = row_key(candidate)
        variant = candidate["variant"]
        if variant not in PRIORITY:
            raise ValueError("unknown_abc_variant")
        if key not in result:
            copy = dict(candidate)
            copy["variants"] = set()
            result[key] = copy
        elif abs(prob(result[key]) - prob(candidate)) > 1e-9:
            raise ValueError("inconsistent_abc_probability")
        result[key]["variants"].add(variant)
    for item in result.values():
        item["variants"] = "/".join(sorted(item["variants"], key=PRIORITY.get))
    return list(result.values())

def by_day(result, fixtures, report_day):
    """Group the selected Warsaw calendar day; date-unverified entries are explicit."""
    day_items = []
    undated = []
    outside = 0
    for row in result["candidates"]:
        fid = str(row["fixture_id"])
        fixture = fixtures.get(fid)
        if fixture is None:
            raise ValueError("unknown_fixture")
        kickoff = date_time(fixture.get("kickoff_utc"))
        if kickoff is None:
            undated.append(row)
        elif kickoff.date().isoformat() == report_day:
            day_items.append(row)
        else:
            outside += 1
    return day_items, undated, outside

def select_top(unique, count=LIMIT_TOP):
    """Highest raw probabilities with at most 3 picks/market and 1 pick/match."""
    market_counts = defaultdict(int)
    seen_fixtures = set()
    chosen = []
    for item in sorted(unique, key=lambda r: (-prob(r), str(r["fixture_id"]),
                              ORDER.get(r["market"], 100), str(r.get("line")))):
        market = item["market"]
        if market_counts[market] >= 3 or item["fixture_id"] in seen_fixtures:
            continue
        chosen.append(item)
        seen_fixtures.add(item["fixture_id"])
        market_counts[market] += 1
        if len(chosen) == count:
            break
    return chosen

def market_order(row):
    line = row.get("line")
    val = line if isinstance(line, (float, int)) else -1
    return (ORDER.get(row["market"], 100), val, row["selection"],
            str(row.get("model", "")))

def _lead(story, st, day, result, filtered, unique, outside, undated, source):
    counts = {v: sum(r["variant"] == v for r in filtered) for v in PRIORITY}
    nfix = {v: len({str(r["fixture_id"]) for r in filtered
                    if r["variant"] == v}) for v in PRIORITY}
    story.extend([
        p("GitHub Models V2 | Typy A/B/C", st["title"]),
        p("Data spotkań: " + day + " | Godziny w Polsce (Europe/Warsaw)", st["sub"]),
        p("Raport obserwacyjny. Procenty to SUROWE, NIEKALIBROWANE oceny modelu. "
          "Brak zweryfikowanych kursów przedmeczowych, nie rekomendujemy stawek.",
          st["body"]),
        p("Źródło danych: " + str(source or "bieżący zamrożony artefakt") +
          " | Cutoff UTC: " + str(result.get("input_cutoff_utc") or "NIEPOTWIERDZONY"),
          st["small"]),
        p("Podsumowanie dnia", st["head"]),
    ])
    summary = [["Wariant", "Próg surowego P", "Propozycje", "Mecze"]]
    for v, threshold in (("A", 70), ("B", 75), ("C", 80)):
        summary.append([v, str(threshold) + "%", str(counts[v]), str(nfix[v])])
    story.append(table(summary, [100, 150, 137, 136], st))
    story.append(p("Łącznie " + str(len(unique)) +
                   " różnych pozycji rynkowych. Warianty A/B/C są zagnieżdżone; "
                   "w pełnym wykazie jedna pozycja występuje tylko raz, z oznaczeniem wariantów.",
                   st["small"]))
    if outside:
        story.append(p(str(outside) + " wpisów innych dni pominięto z dziennego PDF "
                       "(pozostają w pełnym JSON).", st["small"]))
    if undated:
        story.append(p("UWAGA: " + str(len(undated)) +
                       " wpisów nie ma wiarygodnej godziny/data meczu; znajdują się w "
                       "osobnym bloku na końcu zamiast być przypisane do błędnej daty.",
                       st["small"]))

def render_day(result, fixtures, output_pdf, day, *, source=None):
    fonts()
    st = styles()
    filtered, undated_raw, outside = by_day(result, fixtures, day)
    unique = collapse(filtered)
    undated = collapse(undated_raw)
    story = []
    _lead(story, st, day, result, filtered, unique, outside, undated, source)
    story.append(p("Najsilniejsze pozycje dnia – skrót", st["head"]))
    story.append(p("Maksymalnie " + str(LIMIT_TOP) +
                   " pozycji: najwyższe surowe P, do 3 z jednego rynku "
                   "i do 1 na spotkanie. To nie jest ranking value ani typy PLAY.",
                   st["small"]))
    leaders = select_top(unique)
    if leaders:
        top_rows = [["Start", "Mecz", "Rynek / linia", "P", "A/B/C"]]
        for item in leaders:
            f = fixtures[str(item["fixture_id"])]
            start = date_time(f.get("kickoff_utc"))
            top_rows.append([
                start.strftime("%H:%M") if start else "brak",
                str(f.get("home", "?")) + " – " + str(f.get("away", "?")),
                market_str(item), "%.1f%%" % (prob(item) * 100),
                item["variants"]
            ])
        story.append(table(top_rows, [49, 168, 195, 52, 59], st))
    else:
        story.append(p("Brak zakwalifikowanych prognoz na tę datę.", st["body"]))

    story.append(p("Pełny harmonogram meczów i wszystkich rynków", st["head"]))
    story.append(p("Mecze według godziny rozpoczęcia. W obrębie każdego meczu pokazano "
                   "WSZYSTKIE zakwalifikowane pozycje: różne rynki, kierunki i linie. "
                   "A/B/C oznacza, jakie progi spełnia dana pozycja. Kurs: brak.",
                   st["small"]))
    groups = defaultdict(list)
    for row in unique:
        groups[str(row["fixture_id"])].append(row)
    ids = sorted(groups, key=lambda fid: (
        date_time(fixtures[fid].get("kickoff_utc")) or datetime.max.replace(tzinfo=ZONE),
        str(fixtures[fid].get("home", "")), fid
    ))
    total_emitted = 0
    for fid in ids:
        f = fixtures[fid]
        tm = date_time(f.get("kickoff_utc"))
        heading = (tm.strftime("%H:%M") if tm else "Brak godziny") + "  |  " + \
                  str(f.get("home", "?")) + " – " + str(f.get("away", "?"))
        story.append(p(heading, st["head"]))
        story.append(p(str(f.get("league", "Liga nieustalona")) +
                       " | " + str(len(groups[fid])) + " rynków/linii",
                       st["small"]))
        rows = [["Propozycja u bukmachera", "P modelu", "Wariant", "Kurs"]]
        for row in sorted(groups[fid], key=market_order):
            rows.append([market_str(row), "%.1f%%" % (100 * prob(row)),
                         row["variants"], "brak"])
            total_emitted += 1
        story.append(table(rows, [303, 81, 79, 60], st))
    if total_emitted != len(unique):
        raise AssertionError("not_all_abc_candidates_rendered")
    if undated:
        story.append(p("Oddzielnie: brak potwierdzonej daty/godziny", st["head"]))
        story.append(p("Te propozycje NIE są potwierdzonymi zdarzeniami dnia " +
                       day + "; wymagają weryfikacji metadanych.", st["small"]))
        missing_groups = defaultdict(list)
        for row in undated:
            missing_groups[str(row["fixture_id"])].append(row)
        for fid in sorted(missing_groups):
            f = fixtures[fid]
            story.append(p(str(f.get("home", "?")) + " – " + str(f.get("away", "?")),
                           st["head"]))
            rows = [["Rynek / linia", "P modelu", "Wariant", "Kurs"]]
            for row in sorted(missing_groups[fid], key=market_order):
                rows.append([market_str(row), "%.1f%%" % (100 * prob(row)),
                             row["variants"], "brak"])
            story.append(table(rows, [303, 81, 79, 60], st))

    story.extend([
        p("Zasady i ograniczenia", st["head"]),
        p("P nie jest skalibrowanym prawdopodobieństwem trafienia. "
          "Rynek 1X2 bazuje na zgodności dwóch modeli; rynki dodatkowe "
          "mogą pochodzić tylko z jednego modelu. "
          "Do porównań bukmacherskich trzeba mieć dokładny rynek, "
          "zweryfikowany kurs co najmniej 1,20 i notowanie przed meczem.",
          st["body"]),
        p("Raport nie modyfikuje prognoz, progów A/B/C ani archiwalnego JSON. "
          "Zawiera " + str(total_emitted) + " unikalnych rynków/linii dla " +
          str(len(ids)) + " meczów w tym dniu.", st["small"])
    ])
    render(story, output_pdf, "GitHub Models V2 | pełny ABC " + day)
    return {"date": day, "unique_positions": total_emitted, "fixtures": len(ids),
            "variants": {v: sum(r["variant"] == v for r in filtered)
                         for v in PRIORITY},
            "undated_positions": len(undated), "other_day_variant_rows": outside}
