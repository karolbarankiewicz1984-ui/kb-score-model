"""Read-only SHADOW overlay for archived Superbet prices (zero extra API calls).

Only exact, full-time BTTS Yes/No is admitted at launch. Asian handicap
bookmaker-sign conventions need separate verified settlement documentation:
handicap forecasts remain visible, explicitly not priced or playable.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from github_models.elo_engine import utc
from github_models.abc_chronological_pdf import date_time
from github_models.abc_pdf_style import fonts, p, render, styles, table
from github_models.shadow_reports import label


def inventory(collection):
    names = Counter()
    for snap in collection.get("snapshots", []):
        for q in snap.get("quotes", []):
            name = (q.get("market_name") or "").casefold()
            if "both teams to score" in name:
                names["btts"] += 1
            elif "handicap" in name:
                names["handicap"] += 1
            elif "foul" in name:
                names["fouls"] += 1
            elif "booking" in name or "card" in name:
                names["cards_or_bookings"] += 1
            elif "corner" in name:
                names["corners"] += 1
            elif "offside" in name:
                names["offsides"] += 1
            elif "shot" in name:
                names["shots"] += 1
            else:
                names["other"] += 1
    return dict(names)


def overlay(collection, shadow, queue):
    if collection.get("bookmakers") != ["superbet.pl"]:
        raise ValueError("unapproved_bookmaker")
    if shadow.get("schema") != "multimodel-v2-shadow-markets-v1":
        raise ValueError("incorrect_shadow_source")
    fixtures = {str(f["fixture_id"]): f for f in queue["fixtures"]}
    links = {str(f["fixture_id"]): str(f["odds_fixture_id"])
             for f in collection["links"]["links"] if f.get("status") == "matched"}
    snapshots = {}
    for snap in collection["snapshots"]:
        fid = str(snap.get("pitch_fixture_id"))
        if fid in snapshots:
            raise ValueError("duplicate_superbet_fixture_snapshot")
        if snap.get("provider") != "oddspapi-v4" or links.get(fid) != str(snap["fixture_id"]):
            raise ValueError("unverified_superbet_fixture_link")
        snapshots[fid] = snap
    results = []
    for forecast in shadow["candidates"]:
        fid = str(forecast["fixture_id"])
        if fid not in fixtures:
            raise ValueError("shadow_queue_disagrees")
        fixture = fixtures[fid]
        kickoff = utc(fixture["kickoff_utc"])
        frozen = utc(forecast["frozen_at_utc"])
        if not frozen < kickoff:
            raise ValueError("shadow_not_prematch")
        score = forecast["probability"]
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("invalid_shadow_probability")
        row = {k: forecast[k] for k in ("fixture_id", "market", "selection", "line",
                                        "probability", "frozen_at_utc")}
        row.update(home=fixture["home"], away=fixture["away"], league=fixture["league"],
                   kickoff_utc=fixture["kickoff_utc"], bookmaker="superbet.pl",
                   odds=None, price_captured_at_utc=None, status="model_only",
                   reason="no_verified_same_market_quote")
        snap = snapshots.get(fid)
        if forecast["market"] == "handicap":
            row["reason"] = "asian_handicap_quote_semantics_not_verified"
        elif snap is None:
            row["reason"] = "no_verified_fixture_quote"
        else:
            captured = utc(snap["captured_at_utc"])
            if not frozen <= captured < kickoff or utc(snap["kickoff_utc"]) != kickoff:
                row["reason"] = "snapshot_timestamp_not_compatible"
            else:
                matching = []
                for q in snap["quotes"]:
                    if (q.get("bookmaker") != "superbet.pl" or
                            (q.get("market_name") or "").casefold() != "both teams to score" or
                            str(q.get("period", "")).casefold() != "fulltime" or
                            q.get("player_prop") or str(q.get("player_id", "0")) != "0" or
                            str(q.get("outcome_name", "")).casefold() != forecast["selection"]):
                        continue
                    price = q.get("odds")
                    if type(price) not in (int, float) or not math.isfinite(price) or price < 1.20:
                        continue
                    changed = q.get("changed_at_utc")
                    try:
                        if changed and utc(changed) >= kickoff:
                            continue
                    except (TypeError, ValueError):
                        continue
                    matching.append(q)
                if matching:
                    # Same captured snapshot, one book: highest recorded active exact quote.
                    best = max(matching, key=lambda x: x["odds"])
                    row.update(odds=best["odds"], price_captured_at_utc=snap["captured_at_utc"],
                               status="quoted_research", reason=None)
                else:
                    row["reason"] = "no_exact_btts_fulltime_quote_at_or_above_1_20"
        results.append(row)
    return {
        "schema": "multimodel-v2-shadow-superbet-overlay-v1",
        "forecast_cutoff_utc": shadow["generated_at_utc"],
        "odds_snapshot_utc": collection["as_of_utc"],
        "bookmaker": "superbet.pl", "no_extra_api_calls": True,
        "quality_score_67_100_required": False,
        "probabilities_calibrated": False, "no_production_change": True,
        "market_inventory_from_archived_quotes": inventory(collection),
        "counts": dict(Counter(r["status"] for r in results)),
        "unsupported_markets": shadow["unsupported_markets"],
        "rows": results,
    }


def pdf(report, output):
    fonts()
    st = styles()
    story = [
        p("MULTIMODEL V2 | SUPERBET + SHADOW", st["title"]),
        p("Prognozy nowych rynków — analiza badawcza", st["sub"]),
        p("A: dokładny zweryfikowany kurs >= 1,20; B: prognoza bez kursu; "
          "C: kategoria bez danych. To NIE jest rekomendacja stawek.", st["body"]),
        p("Nie stosujemy punktowej oceny 67/100. Surowe procenty są NIEKALIBROWANE. "
          "Dotychczasowe A/B/C bez zmian.", st["small"]),
        p("Źródło prognoz: " + str(report["forecast_cutoff_utc"]) +
          " | Kursy Superbet: " + str(report["odds_snapshot_utc"]), st["small"]),
        p("Pokrycie rzeczywistych ofert — archiwum (liczba notowań)", st["head"]),
    ]
    counts = report["market_inventory_from_archived_quotes"]
    story.append(table([["Kategoria", "Zapisane oferty"]] +
                       [[key, str(counts[key])] for key in sorted(counts)],
                       [300, 223], st))
    story.append(p("Najważniejsze pozycje z kursem (A)", st["head"]))
    priced = [r for r in report["rows"] if r["status"] == "quoted_research"]
    if priced:
        priced = sorted(priced, key=lambda x: (-x["probability"], x["kickoff_utc"]))
        data = [["Mecz", "Rynek", "P", "Kurs"]]
        for row in priced[:30]:
            data.append([row["home"] + " – " + row["away"], label(row),
                         "%.1f%%" % (row["probability"] * 100),
                         "%.2f" % row["odds"]])
        story.append(table(data, [175, 245, 48, 55], st))
    else:
        story.append(p("Brak dopasowanych ofert. Nadal publikujemy wszystkie "
                       "prognozy modelowe w sekcji B i JSON.", st["body"]))
    story.append(p("Pełny wykaz A/B — według meczu i godziny", st["head"]))
    grouped = defaultdict(list)
    for row in report["rows"]:
        grouped[row["fixture_id"]].append(row)
    for fid in sorted(grouped, key=lambda k: (
            grouped[k][0]["kickoff_utc"], grouped[k][0]["home"], k)):
        rows = grouped[fid]
        first = rows[0]
        story.append(p(date_time(first["kickoff_utc"]).strftime("%d.%m %H:%M") +
                       " | " + first["home"] + " – " + first["away"], st["head"]))
        data = [["Rynek / strona / linia", "P", "Status", "Kurs"]]
        for r in sorted(rows, key=lambda z: (z["market"], str(z["line"]), z["selection"])):
            data.append([label(r), "%.1f%%" % (r["probability"]*100),
                         "A" if r["status"] == "quoted_research" else "B",
                         "%.2f" % r["odds"] if r["odds"] is not None else "brak"])
        story.append(table(data, [297, 55, 75, 96], st))
    story.append(p("Kategorie C: " + ", ".join(report["unsupported_markets"]) +
                   ". Brak danych do niezależnej prognozy.", st["small"]))
    story.append(p("Handicap azjatycki: oznaczenie B aż do potwierdzenia "
                   "konwencji linii i zasad rozliczenia. Nie zrównujemy punktów "
                   "kartkowych z żółtymi kartkami ani fauli gracza z faulami meczu.",
                   st["small"]))
    render(story, output, "MultiModel V2: research SHADOW and real Superbet odds")


def main():
    p = argparse.ArgumentParser()
    for n in ("collection", "shadow", "queue", "output-dir"):
        p.add_argument("--"+n, required=True)
    a = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    result = overlay(read(a.collection), read(a.shadow), read(a.queue))
    directory = Path(a.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/"SHADOW_SUPERBET_OVERLAY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    pdf(result, str(directory/"MULTIMODEL_V2_SHADOW_SUPERBET.pdf"))
    print("SHADOW_PRICED=" + str(result["counts"].get("quoted_research", 0)))
    print("SHADOW_MODEL_ONLY=" + str(result["counts"].get("model_only", 0)))


if __name__ == "__main__":
    main()
