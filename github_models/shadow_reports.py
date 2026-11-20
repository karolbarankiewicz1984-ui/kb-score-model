"""Seven separate Warsaw-calendar SHADOW PDFs; every raw forecast retained in JSON.

A/B/C production PDF stays separate. The full SHADOW table includes all
modeled selections; a compact one-per-market/three-per-fixture shortlist is
purely editorial. No 67/100 quality threshold or invented bookmaker odds.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
import math
from pathlib import Path

from github_models.abc_chronological_pdf import date_time
from github_models.abc_pdf_style import fonts, p, render, styles, table

MAX_DAYS = 7


def label(row):
    if row["market"] == "btts":
        return "Obie drużyny strzelą: " + ("TAK" if row["selection"] == "yes" else "NIE")
    if row["market"] == "handicap":
        team = "Gospodarze" if row["selection"] == "home" else "Goście"
        return "Handicap " + team + " " + ("%+g" % row["line"]).replace(".", ",")
    return "NIEZNANY RYNEK"


def _score(row):
    x = row.get("probability")
    if type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("invalid_shadow_probability")
    return x


def _report(rows, fixtures, target, day, status, cutoff, unsupported):
    fonts()
    st = styles()
    selected = sorted(rows, key=lambda r: (
        date_time(fixtures[str(r["fixture_id"])]["kickoff_utc"]),
        str(r["fixture_id"]), r["market"], str(r.get("line")), r["selection"]))
    groups = defaultdict(list)
    for row in selected:
        groups[str(row["fixture_id"])].append(row)
    story = [
        p("MULTIMODEL V2 | NOWE PROGNOZY SHADOW", st["title"]),
        p("Dzień: " + day + " | Polska (Europe/Warsaw)", st["sub"]),
        p("TEST BADAWCZY — SUROWE, NIEKALIBROWANE prawdopodobieństwa. "
          "Brak kursu i weryfikacji rynku Superbet. NIE oznacza to gotowego kuponu.",
          st["body"]),
        p("Zamrożenie danych UTC: " + str(cutoff) + " | Stan terminarza: " + status,
          st["small"]),
        p("Brak twardego filtra 67/100. Nie zmieniono dotychczasowych A/B/C; "
          "typy z nich znajdują się w osobnym raporcie.", st["small"]),
        p("Najsilniejsze do obserwacji — maks. 3 na mecz, 1 na rynek", st["head"])
    ]
    leaders = []
    for fid, candidates in groups.items():
        top_per_market = {}
        for row in candidates:
            if row["market"] not in top_per_market or _score(row) > _score(top_per_market[row["market"]]):
                top_per_market[row["market"]] = row
        leaders.extend(sorted(top_per_market.values(), key=lambda row: -_score(row))[:3])
    leaders = sorted(leaders, key=lambda row: (-_score(row), str(row["fixture_id"])))
    if leaders:
        data = [["Godz.", "Mecz", "Rynek SHADOW", "P", "Kurs"]]
        for row in leaders:
            f = fixtures[str(row["fixture_id"])]
            data.append([date_time(f["kickoff_utc"]).strftime("%H:%M"),
                         str(f["home"]) + " – " + str(f["away"]),
                         label(row), "%.1f%%" % (_score(row)*100), "brak"])
        story.append(table(data, [45, 170, 225, 45, 38], st))
    else:
        story.append(p("Brak prognoz: nie zastępujemy niedostępnej historii sztucznymi danymi.",
                       st["body"]))
    story.append(p("Pełny wykaz nowych typów według spotkań", st["head"]))
    for fid in sorted(groups, key=lambda id: (
            date_time(fixtures[id]["kickoff_utc"]), str(fixtures[id]["home"]))):
        f = fixtures[fid]
        story.append(p(date_time(f["kickoff_utc"]).strftime("%H:%M") + " | " +
                       str(f["home"]) + " – " + str(f["away"]), st["head"]))
        story.append(p(str(f.get("league") or "Nieustalona liga"), st["small"]))
        data = [["Rynek / strona / linia", "P surowe", "Status", "Kurs"]]
        for row in groups[fid]:
            data.append([label(row), "%.1f%%" % (_score(row)*100),
                         "SHADOW", "brak"])
        story.append(table(data, [282, 73, 99, 69], st))
    story.append(p("Niedostępne generatory bez potwierdzonej historii", st["head"]))
    story.append(p(", ".join(unsupported) + ". Brak prognoz dla tych kategorii "
                   "jest celowy i nie blokuje pozostałych.", st["body"]))
    story.append(p("Po walidacji tożsamości rynku i kursu >=1,20 osobny raport "
                   "Superbet może oznaczyć propozycję jako wycenioną. "
                   "Nie utożsamiaj ocen badawczych z potwierdzoną skutecznością.", st["small"]))
    render(story, str(target), "MULTIMODEL V2 SHADOW " + day)
    if not target.is_file() or target.stat().st_size < 1024 or target.read_bytes()[:5] != b"%PDF-":
        raise ValueError("invalid_shadow_pdf:" + day)
    return {"date": day, "matches": len(groups), "rows": len(selected),
            "shortlist": len(leaders), "pdf": target.name, "source_status": status}


def build(root, day, *, days=MAX_DAYS):
    if type(days) is not int or not 1 <= days <= MAX_DAYS:
        raise ValueError("invalid_shadow_horizon")
    root = Path(root)
    begin = date.fromisoformat(day)
    q = json.loads((root/"queues"/(day + ".json")).read_text(encoding="utf-8"))
    frozen = json.loads((root/"shadow"/(day + ".json")).read_text(encoding="utf-8"))
    expected = [(begin + timedelta(days=i)).isoformat() for i in range(days)]
    if q.get("dates") != expected or frozen.get("schema") != "multimodel-v2-shadow-markets-v1":
        raise ValueError("shadow_queue_or_schema_mismatch")
    fixtures = {str(f["fixture_id"]): f for f in q["fixtures"]}
    if len(fixtures) != len(q["fixtures"]):
        raise ValueError("duplicate_shadow_fixture")
    grouped = defaultdict(list)
    for row in frozen["candidates"]:
        fid = str(row["fixture_id"])
        if fid not in fixtures:
            raise ValueError("shadow_forecast_for_unknown_fixture")
        kick = date_time(fixtures[fid]["kickoff_utc"])
        if kick is None:
            raise ValueError("shadow_fixture_kickoff_invalid")
        if row.get("frozen_at_utc") != frozen.get("generated_at_utc"):
            raise ValueError("shadow_cutoff_changed")
        grouped[kick.date().isoformat()].append(row)
    output = []
    for d in expected:
        status = ("missing" if d in q.get("missing_dates", []) else
                  "invalid" if d in q.get("invalid_dates", []) else
                  "partial" if d in q.get("partial_dates", []) else "verified")
        dest = root/"pdf"/("MULTIMODEL_V2_SHADOW_" + d + ".pdf")
        dest.parent.mkdir(parents=True, exist_ok=True)
        output.append(_report(grouped[d], fixtures, dest, d, status,
                              frozen["generated_at_utc"], frozen["unsupported_markets"]))
    report = {"schema": "multimodel-v2-shadow-seven-day-v1",
              "source_run_cutoff_utc": frozen["generated_at_utc"],
              "model_status": "uncalibrated_research", "odds_verified": False,
              "reports": output, "no_67_point_quality_gate": True,
              "unsupported_markets": frozen["unsupported_markets"],
              "production_abc_unchanged": True}
    dest = root/"shadow"/("SHADOW_MANIFEST_" + day + ".json")
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SHADOW_PDFS=" + str(len(output)))
    print("SHADOW_REPORT_ROWS=" + str(sum(row["rows"] for row in output)))
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--day", required=True)
    p.add_argument("--days", type=int, default=MAX_DAYS)
    a = p.parse_args()
    build(a.root, a.day, days=a.days)


if __name__ == "__main__":
    main()
