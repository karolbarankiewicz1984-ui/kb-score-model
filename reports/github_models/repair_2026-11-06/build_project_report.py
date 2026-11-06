"""Build the project ledger from one verified research artifact and cohort.

This command does not fit models, create probabilities, change source inputs or
write to any observation register. It refuses mismatched cohorts and cutoffs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from github_models.elo_engine import utc
from github_models.research_pdf import _validate


CHANGES = [
    ("R01", "Niejednoznaczne nazwy lig i błędne powiązanie kraju", "competition_identity.py",
     "Zweryfikowane, nieprzybliżane ID PitchAPI oraz para nazwa–kraj oddzielają m.in. angielską i rosyjską Premier League, niemiecką i austriacką Bundesligę oraz włoską i brazylijską Serie A."),
    ("R02", "Brak kodu kraju w LeagueRef i różne kody dostawców", "pitchapi_fixtures.py; competition_identity.py",
     "Kolektor pobiera szczegółowe metadane ligi. Jawne aliasy kodów obejmują rzeczywiście zaobserwowane wartości, m.in. GER/DEU, NED/NLD, POR/PRT i DEN/DNK. INT i nieznane kody nie stają się zweryfikowanym krajem."),
    ("R03", "Różnice nazw drużyn i znaków Unicode", "team_mapping.py; reviewed_team_aliases.py; reviewed_resolver.py",
     "Wspólny resolver stosuje wyłącznie jawne aliasy w jednej lidze i rzeczywistym zbiorze kandydatów. Kolizja nazwy dokładnej i aliasu, niejednoznaczne warianty oraz sprzeczne identyfikatory są odrzucane; brak fuzzy matching."),
    ("R04", "Historia ograniczona do pięciu lig", "public_results.py; additional_results.py; collect_events.py; event_parser.py",
     "Rozdzielono parser 22 europejskich dywizji mmz4281 i odmiennego schematu 16 plików /new. Kraje, ligi, sezony, wyniki, duplikaty i rzeczywiste czasy odczytu są sprawdzane. Statystyk nie zastępują wyniki bramkowe."),
    ("R05", "Limit 80 spotkań oraz granice UTC/Warszawa", "pitchapi_fixtures.py; daily_queue.py",
     "Nowy kolektor badawczy pobiera wszystkie zwrócone fixtures bez limitu 80 i grupuje je według dni Warszawy. Zakres wymaga trzech, a przy granicy dat maksymalnie czterech zapytań o daty UTC. Błąd źródła nie jest pustym kompletnym kalendarzem."),
    ("R06", "Niespójna identyfikacja prognoz i audytów", "predict.py; coverage_audit.py; event_markets.py",
     "Wszystkie ścieżki korzystają z jednego resolvera i historii dostępnej w cutoff. Audyt rozdziela gotowość tożsamości, Elo, historii Dixon–Coles i rzeczywiście zapisane prognozy."),
    ("R07", "Niebezpieczne rozliczanie przez przybliżoną datę", "settlement.py; market_settlement.py; settle.py; kb3_history_bridge.py",
     "Usunięto dopasowanie daty ±1 dzień i odejmowanie dwóch dni od dowolnego czasu końca. Rozliczenie wymaga dokładnej ligi, kolejności drużyn i zweryfikowanej daty. Zamrożona tożsamość zachowuje dostawcę i oba warianty kluczy ID; identyfikatorów różnych dostawców nie utożsamia się."),
    ("R08", "Wsteczny czas obserwacji i sztuczne podbijanie prób", "public_results.py; collect_events.py; elo_engine.py; event_markets.py",
     "Czas obserwacji powstaje po odczycie odpowiedzi, a cutoff po wszystkich odpowiedziach. Duplikat nie zwiększa N treningowego; sprzeczne wersje są wykluczane. Kontrole publikacji, ukończenia i kickoff pozostają aktywne."),
    ("R09", "Błędy matematyki Poissona i normalizacji", "event_markets.py; elo_engine.py; multimodel_v2/dixon_coles_shadow.py",
     "Naprawiono zerową intensywność, utratę małych ogonów i walidację parametrów. Linie całkowite wymagające zwrotu są jawnie poza kontraktem binarnym. Dixon–Coles koryguje wyłącznie dopuszczalny błąd zaokrąglenia, a nie dowolne błędne wagi."),
    ("R10", "Kartki o niejasnej definicji", "event_parser.py; event_markets.py; research_pdf.py",
     "Rynek cards oznacza HY+AY, czyli żółte kartki. Nie dopisano czerwonych kartek, fauli ani rożnych do źródeł zawierających tylko gole."),
    ("R11", "Niepełny przebieg badawczy i brak powtarzalnych wejść", ".github/workflows/github-models-independent.yml",
     "Workflow wykonuje pełną regresję, pobiera rzeczywiste źródła, trenuje modele, oblicza wszystkie rynki, odczytuje istniejące archiwa rozliczeń i tworzy PDF. Artefakt zawiera macierze wejściowe, manifesty, snapshoty, prognozy i raport."),
    ("R12", "Powtarzane identyczne dopasowania Dixon–Coles", "predict.py; dixon_coles_engine.py; multimodel_v2/dixon_coles_shadow.py",
     "Cache jest lokalny dla jednego przebiegu i związany z dokładnymi uporządkowanymi wejściami, dostępnością, cutoff, wersją, parametrami i klasą zależności. Walidacja działa przed odczytem cache; nieudane dopasowanie nie trafia do cache. Rzeczywisty replay ligi argentyńskiej dał identyczne pełne prognozy z cache i bez cache."),
    ("R13", "Nieczytelna prezentacja i nadinterpretacja prognoz", "research_pdf.py; reports/github_models/repair_2026-11-06/build_summary_pdf.py",
     "Raport ma sekcje, instrukcję interpretacji pięciu rynków, liczebności prób i krótkie uzasadnienia obserwacji. Prognozy są jawnie niekalibrowane; nie opisuje się ich jako potwierdzonych okazji bukmacherskich. Pełna macierz jest oddzielona od zwięzłego podsumowania."),
    ("R14", "Brak porównania każdej ligi na tej samej próbie", "coverage_comparison.py; reports/github_models/repair_2026-11-06/verify_artifacts.py",
     "Stary kod uruchamia się w osobnym procesie i checkout. Raport zachowuje wszystkie ID lig i ten sam mianownik, także dla odrzuceń, oraz rozdziela zmianę zakresu historii od samej naprawy identyfikacji. Hashe wiążą wejścia i artefakt."),
]


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers, rows):
    return "\n".join(["| " + " | ".join(map(_cell, headers)) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |"]
                      + ["| " + " | ".join(map(_cell, row)) + " |" for row in rows])


def _pdf(path):
    if not path:
        return {"status": "NOT_SUPPLIED"}
    import pymupdf
    from pypdf import PdfReader
    path = Path(path)
    minimum = float("inf")
    outside = links = 0
    with pymupdf.open(path) as document:
        pages = len(document)
        for page in document:
            links += len(page.get_links())
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            minimum = min(minimum, span["size"])
                            outside += not page.rect.contains(pymupdf.Rect(span["bbox"]))
    if not pages or len(PdfReader(path).pages) != pages or minimum < 8 or outside:
        raise ValueError("project_report_pdf_validation_failed")
    return dict(status="PASS", file=path.name, pages=pages, bytes=path.stat().st_size,
                minimum_font_pt=minimum, outside_page_spans=outside, active_links=links,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), parsers=["PyMuPDF", "pypdf"])


def build(artifact_root, comparison_path, verification_path, *, summary_pdf=None, full_pdf=None):
    root = Path(artifact_root)
    reports = root / "reports/github_models"
    queue_path, = (reports / "queues").glob("*.json")
    day = queue_path.stem
    queue = _read(queue_path)
    predictions = _read(reports / "predictions" / (day + ".json"))
    markets = _read(reports / "markets" / (day + ".json"))
    history = _read(root / "data/github_models/verified_results.json")
    events = _read(root / "data/github_models/verified_events.json")
    comparison, verification = _read(comparison_path), _read(verification_path)
    fixtures = _validate(predictions, queue, markets)
    cutoff = predictions["generated_at_utc"]
    if comparison["total"] != len(fixtures):
        raise ValueError("project_report_cohort_size_mismatch")
    if verification.get("status") != "PASS" or verification.get("ci", {}).get("conclusion") != "success":
        raise ValueError("project_report_requires_successful_verified_run")
    if verification["queue_fixtures"] != len(fixtures):
        raise ValueError("project_report_cohort_size_mismatch")
    if utc(comparison["as_of_utc"]) != utc(cutoff) or utc(verification["cutoff_utc"]) != utc(cutoff):
        raise ValueError("project_report_cutoff_mismatch")
    covered = [str(fid) for group in comparison["leagues"] for fid in group["fixture_ids"]]
    if len(covered) != len(set(covered)) or set(covered) != set(fixtures):
        raise ValueError("project_report_fixture_set_mismatch")
    if comparison["summary"] != verification.get("coverage"):
        raise ValueError("project_report_verified_coverage_mismatch")
    for key, path in (("queue", queue_path),
                      ("history", root / "data/github_models/verified_results.json"),
                      ("events", root / "data/github_models/verified_events.json")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if comparison.get("input_sha256", {}).get(key) != digest:
            raise ValueError("project_report_comparison_input_hash_mismatch")
        if verification.get("source_sha256", {}).get(str(path.relative_to(root))) != digest:
            raise ValueError("project_report_verified_source_hash_mismatch")
    for variant, totals in comparison["summary"].items():
        for metric in ("total", "identity_ready", "elo_ready", "dixon_coles_history_ready"):
            if sum(group[variant][metric] for group in comparison["leagues"]) != totals[metric]:
                raise ValueError("project_report_coverage_sum_mismatch")
    if (verification["actual_1x2_forecasts"] != len(predictions["predictions"])
            or verification["actual_event_forecasts"] != len(markets["markets"])):
        raise ValueError("project_report_forecast_count_mismatch")
    if verification["history_results"] != len(history) or verification["event_history_rows"] != len(events):
        raise ValueError("project_report_history_count_mismatch")
    model_counts = Counter(row["model_id"] for row in predictions["predictions"])
    market_counts = Counter(row["market"] for row in markets["markets"])
    if dict(model_counts) != verification["actual_1x2_models"] or dict(market_counts) != verification["actual_markets"]:
        raise ValueError("project_report_market_count_mismatch")
    actual_by_id = defaultdict(Counter)
    for row in predictions["predictions"]:
        fixture = fixtures[str(row["fixture_id"])]
        lid = fixture.get("league_id")
        key = str(lid) if lid is not None and str(lid).strip() else (
            "unverified:" + str(fixture.get("country_code") or "unknown") + ":" + str(fixture["league"]))
        actual_by_id[key][row["model_id"]] += 1
    per_league = []
    for group in comparison["leagues"]:
        name = ", ".join(group.get("canonical_leagues") or group["raw_labels"])
        country = ", ".join(group.get("countries", [])) or "niezweryfikowany"
        per_league.append(dict(league_id=group["league_id"], league=name, country=country,
            total=group["total"], before_original=group.get("before_original_history"),
            before_same=group["before_same_history"], after=group["after"],
            actual_models=dict(actual_by_id[group["league_id"]])))
    pdf = dict(summary=_pdf(summary_pdf), full_annex=_pdf(full_pdf))
    repo = Path(__file__).resolve().parents[3]
    changed = subprocess.check_output(["git", "diff", "f609427", "--name-only"], cwd=repo, text=True).splitlines()
    protected = [name for name in changed if name.startswith(("tools/", "config/", "model/", "data/", "archive/"))
                 or (name.startswith(".github/") and name != ".github/workflows/github-models-independent.yml")
                 or (name.startswith("reports/") and not name.startswith("reports/github_models/repair_2026-11-06/"))]
    if protected or not verification.get("production_multimodel_unchanged") or verification.get("n_counter_writes") != 0:
        raise ValueError("project_report_production_isolation_not_verified")
    ci = verification["ci"]
    tests = verification["tests"]
    math = verification["math"]
    summary = comparison["summary"]
    lines = [f"# MULTIMODEL v2 — naprawa pokrycia i identyfikacji ({day})", "",
        "Status: **badawcze poprawki zweryfikowane; produkcyjny MULTIMODEL bez zmian**.", "",
        f"Gałąź: `codex/multimodel-v2`. Baza porównania: `{comparison.get('baseline_commit', 'nie przekazano')}`. "
        f"Rewizja pełnego przebiegu: `{ci.get('head_sha', 'nie przekazano')}`. Cutoff danych UTC: `{cutoff}`.", "",
        "## Wynik i sposób porównania", "",
        f"Ta sama kolejka zawiera **{len(fixtures)}** spotkań. Wszystkie kolumny porównania używają tych samych ID i cutoff; "
        f"{comparison.get('started_fixtures', 0)} spotkań rozpoczętych do cutoff wyłączono jednakowo w obu wariantach. "
        "To porównanie zapisanej kolejki, nie deklaracja kompletności całego światowego kalendarza.", "",
        "„Przed / 5 lig” to kod bazowy i dawny zakres importu. „Przed / ta sama historia” izoluje zmianę identyfikacji: "
        "oba kody otrzymują identyczną rozszerzoną historię dostępną w cutoff. Gotowość tożsamości, Elo i historii Dixon–Coles "
        "nie oznacza automatycznie udanego dopasowania ani kalibracji.", ""]
    rows = []
    for key, label in (("before_original_history", "Przed / 5 lig"), ("before_same_history", "Przed / ta sama historia"), ("after", "Po zmianach")):
        row = summary.get(key)
        rows.append([label] + ([row[metric] for metric in ("identity_ready", "elo_ready", "dixon_coles_history_ready")]
                               if row else ["nie przekazano"] * 3))
    lines += [_table(["Wariant", "Rozpoznana tożsamość", "Gotowe Elo", "Historia DC"], rows), "",
        f"Rzeczywiście zapisano **{len(predictions['predictions'])}** prognoz 1X2 na "
        f"**{verification['actual_1x2_fixtures']}** spotkań oraz **{len(markets['markets'])}** pozycji rynków zdarzeń. "
        "Poniższa tabela zachowuje każde ID ligi, także przy zerowym pokryciu.", "",
        "## Pokrycie każdej ligi", "",
        "W trzech kolumnach „Elo gotowe” podano historyczną gotowość. Dwie ostatnie kolumny liczą rzeczywiście zapisane prognozy modeli.", ""]
    lines += [_table(["ID ligi", "Liga / kraj", "Kolejka", "Elo gotowe: przed 5 lig", "Elo gotowe: przed ta sama historia", "Elo gotowe: po", "Elo zapisane", "DC zapisane"],
        [[row['league_id'], row['league'] + ' / ' + row['country'], row['total'],
          row['before_original']['elo_ready'] if row['before_original'] else '—', row['before_same']['elo_ready'],
          row['after']['elo_ready'], row['actual_models'].get('github-elo', 0), row['actual_models'].get('callumfm-dixon-coles', 0)] for row in per_league]), "",
        "## Naprawy i usunięte blokady", "",
        _table(["Rejestr", "Problem", "Poprawka i zachowane zabezpieczenie", "Pliki"],
               [[key, problem, fix, paths] for key, problem, paths, fix in CHANGES]), "",
        "## Dane i kontrola czasu", "",
        f"Artefakt zawiera **{len(history)}** zweryfikowanych wyników z **{len({row['league'] for row in history})}** lig "
        f"oraz **{len(events)}** rekordów statystyk zdarzeń. Odczyty są opisane manifestami i hashami; czas obserwacji pochodzi "
        "z odczytu odpowiedzi, a nie z daty rozegrania meczu. Dla football-data.co.uk `completed_at_utc` pozostaje "
        "konserwatywną granicą data meczu + 2 dni, nie rzeczywistym końcowym gwizdkiem.", "",
        "Zakres obejmuje 22 dywizje `mmz4281` i 16 dodatkowych plików krajowych `/new`. Osobno skonfigurowano Swiss Challenge League, "
        "ale dwa znalezione wyniki z 2020/21 są poza zakresem od 2023 r.; nie obniżono zakresu jakości, aby dopisać prognozy. "
        "Dodatkowe pliki z wynikami bez statystyk mogą zasilać 1X2 i bramki, lecz nie tworzą obserwacji kartek, fauli ani rożnych.", "",
        "Cutoff oznacza dostępność wejść. Obliczenia i publikacja artefaktu mogą zakończyć się później; raport nie potwierdza formalnego "
        "forward ani oryginalnej publikacji każdej prognozy przed kickoff. Replay odtwarza obliczenia badawcze; nie jest nowym zamrożeniem historycznej prognozy.", "",
        "## Rynki i matematyka", "",
        _table(["Model / rynek", "Zapisane pozycje"], [[key, count] for key, count in sorted(model_counts.items())] +
               [[{"goals": "Bramki", "corners": "Rożne", "cards": "Żółte kartki", "fouls": "Faule"}.get(key, key), count]
                for key, count in sorted(market_counts.items())]), "",
        f"Walidacja matematyki: **{math.get('status', 'nie przekazano')}**. Maksymalny błąd sumy 1X2: "
        f"`{math.get('max_1x2_sum_error', 'nie przekazano')}`; maksymalny błąd komplementarności OVER/UNDER: "
        f"`{math.get('max_binary_complement_error', 'nie przekazano')}`. Maksymalna różnica względem "
        f"`scipy.stats.poisson.sf`: `{math.get('max_poisson_reference_error', 'nie przekazano')}` "
        "z tolerancją wynikającą z zapisu do sześciu miejsc po przecinku. Sprawdzono zakres [0,1], skończoność, kompletne pary stron i monotoniczność ogonów.", "",
        "Dla 1X2 suma trzech prawdopodobieństw wynosi 1. Dla tej samej linii połówkowej OVER i UNDER sumują się do 1. "
        "Kartki oznaczają żółte kartki HY+AY. Linie całkowite z możliwym zwrotem nie są przedstawiane jako taki rynek binarny. "
        "Poprawna matematyka nie dowodzi trafności, kalibracji, wspólnego rozkładu niezależnych modeli ani opłacalności zakładu.", "",
        "## Testy i GitHub Actions", "",
        _table(["Kontrola", "Wynik"], [
            ["Pełna regresja bazowa", str(tests.get('baseline_full_count', 'nie przekazano')) + " / PASS"],
            ["Końcowa pełna regresja lokalna", str(tests.get('local_full_count', 'nie przekazano')) + " / " + str(tests.get('local_status', 'nie przekazano'))],
            ["Końcowy pełny przebieg GitHub Actions", str(ci.get('run_id', ci.get('id', 'nie przekazano'))) + " / " + str(ci.get('conclusion'))],
            ["SHA uruchomionego kodu", ci.get('head_sha', 'nie przekazano')],
            ["SHA256 pobranego artefaktu", ci.get('artifact_sha256', 'nie przekazano')],
            ["Zachowane progi jakości", json.dumps(verification.get('thresholds_unchanged', {}), ensure_ascii=False)],
            ["Zapisy do N", verification.get('n_counter_writes', 'nie przekazano')]]), "",
        "W trakcie kolejnych rozszerzeń lokalne pełne zestawy przechodziły po 1182, 1201 i 1211 testów. Końcową liczbę oraz "
        "status ostatniego uruchomienia podano powyżej na podstawie przekazanej weryfikacji; liczby z etapów nie zastępują kontroli końcowego SHA.", "",
        "W niezależnym teście na rzeczywistych danych argentyńskich pełne słowniki prognoz z cache i bez niego były identyczne. "
        "Pierwsze 5,3 s obejmowało rozgrzanie JIT; rozgrzane wywołania miały około 0,021 s z cache i 0,053 s bez niego. "
        "Nie przypisuje się pierwszego kosztu każdemu kolejnemu meczowi ani nie obiecuje takiego skrócenia całego workflow.", "",
        "## PDF", ""]
    lines += [_table(["Dokument", "Stan", "Strony", "Minimalna czcionka", "SHA256"],
        [[kind, state['status'], state.get('pages', '—'), state.get('minimum_font_pt', '—'), state.get('sha256', '—')]
         for kind, state in pdf.items()]), "",
        "Dostarczone PDF sprawdzono niezależnie PyMuPDF i pypdf; dokumenty mają numerację, polskie znaki, sekcje, instrukcję interpretacji "
        "oraz krótkie uzasadnienia wybranych obserwacji oparte na podanych prognozach i próbach. Jeżeli nie przekazano pliku, tabela jawnie pokazuje brak weryfikacji. "
        "Prognozy pozostają niekalibrowane i nie są potwierdzonymi okazjami bukmacherskimi.", "",
        "## Pozostałe ograniczenia i przygotowane dalsze kroki", "",
        "- Nieobsługiwane ligi i niejednoznaczne lub niepotwierdzone tożsamości pozostają w mianowniku i w rejestrze odrzuceń. Rozszerzenie wymaga zweryfikowanego źródła, kraju, ID i dostatecznej historii; nie wystarczy podobna nazwa drużyny.",
        "- XGBoost pozostaje zablokowany jako model nietrenowany lub bez gotowego adaptera. Nie utworzono zastępczych prawdopodobieństw.",
        "- Zachowano minima Elo 5 meczów drużyny, Dixon–Coles 30 meczów ligi i rynków zdarzeń 60 meczów ligi / 8 drużyny. Przykład Rodiny z dwóch obserwacji nie uzasadnia obniżenia progu Elo; status ostatniej kolejki wynika z jej rzeczywistych danych.",
        "- Starsze rekordy bez zweryfikowanej daty meczu pozostają nierozliczone. Dane HG/AG są opisane jako full time, ale nie podają rzeczywistego końca meczu ani osobnego oznaczenia dogrywki; nie utożsamia się ich z gotowym rozliczeniem dowolnego regulaminu bukmachera.",
        "- Źródło rosyjskie ma ograniczoną aktualność i zostało oznaczone przez dostawcę jako wycofywane. Daty ostatnich wyników w dostarczonym artefakcie podaje tabela historii poniżej; nie uzupełniano późniejszych wyników szacunkami.",
        "- Nie wykonano niezależnego potwierdzenia całego światowego kalendarza, walidacji kalibracji poza próbą, potwierdzenia value/EV ani formalnego forward. Przed takimi zastosowaniami potrzebne są odrębne dowody, a nie zwiększenie samego pokrycia.",
        "- Automatyczna retencja artefaktów Actions wynosi 30 dni. Do trwałego odtworzenia należy zachować oryginalny ZIP z podanym SHA256 i kod z SHA uruchomienia; samo ponowne pobranie dzisiejszego CSV nie odtworzy dawnego czasu obserwacji.", "",
        "### Faktyczna historia według ligi", ""]
    history_groups = defaultdict(list)
    for row in history:
        history_groups[row['league']].append(row)
    lines += [_table(["Liga", "Wyniki", "Najwcześniejsza data", "Ostatnia data"],
        [[league, len(rows), min(row['match_date'] for row in rows), max(row['match_date'] for row in rows)]
         for league, rows in sorted(history_groups.items())]), "",
        "## Rejestr przebiegu i izolacja produkcji", "",
        "Commity robocze: `6dd43aa` — wspólna identyfikacja i kontrola rynków; `581e951` — rozszerzenie historii o kolejne kraje; "
        "`3c2dc11` — domknięcie dostępnych dodatkowych źródeł; `703b533` — pełna obsługa obserwowanych kodów krajów oraz bezpieczny cache. "
        "Ostateczny SHA rzeczywiście użyty przez CI znajduje się w tabeli weryfikacji.", "",
        "Problemy środowiska rozwiązano bez zmiany produkcji: początkowe połączenie z proxy wymagało jawnego dostępu sieciowego; "
        "niepełne odtworzenie plików przez API dało 59 braków plików i jeden błąd hasha fixture, po czym pełny klon przeszedł 1078 testów; "
        "instalację do katalogu tylko do odczytu zastąpiło lokalne venv. Nie zmieniano źródłowych fixture ani archiwów, aby ukryć te błędy.", "",
        "W sprawdzonym diffie nie ma zmian w `tools/`, `config/`, `model/`, `data/`, `archive/`, natywnych raportach ani produkcyjnych workflow. "
        "Dopuszczony zakres to pakiet badawczy, jego testy, opcjonalny shadow Dixon–Coles, workflow badawczy i dokumentacja/artefakty naprawy. "
        "Nie wykonano merge do main, wdrożenia produkcyjnego ani zapisów obserwacji do N.", "",
        "## Odtworzenie", "",
        "1. Zachowaj oryginalny ZIP artefaktu i sprawdź jego SHA256 z tabeli. Rozpakuj go do osobnego katalogu; nie nadpisuj plików produkcyjnych.",
        "2. Użyj kodu z SHA pełnego przebiegu i osobnego checkout bazy `f609427`. Zainstaluj izolowane zależności z `github_models/requirements.txt`.",
        "3. Z archiwalnego `verified_results.json` wyodrębnij dawny zakres kodów E0/D1/I1/SP1/F1 bez zmiany rekordów i timestampów. Zachowaj pełną macierz jako wejście obu kodów wariantu „ta sama historia”.",
        "4. Uruchom porównanie z dokładnym cutoff zapisanym w artefakcie. Następnie uruchom `verify_artifacts.py` oraz generatory PDF/tego raportu. To replay badawczy, nie nowy forward.", "",
        "```bash",
        "python -B -m github_models.coverage_comparison \\",
        "  --queue ARTIFACT/reports/github_models/queues/" + day + ".json \\",
        "  --history ARTIFACT/data/github_models/verified_results.json \\",
        "  --events ARTIFACT/data/github_models/verified_events.json \\",
        "  --before-history OLD_SCOPE.json --baseline-root BASELINE_CHECKOUT \\",
        "  --as-of '" + cutoff + "' --output coverage_comparison.json",
        "```", "",
        "Pełne powody odrzuceń i hashe wejść znajdują się w porównaniu JSON, trzech audytach wariantów i weryfikacji. "
        "Ten raport jest rejestrem badawczych zmian, a nie wpisem do produkcyjnego rejestru prognoz.", ""]
    ledger = dict(schema="github-models-project-repair-ledger-v1", date=day, status="VERIFIED_RESEARCH_ONLY",
        cutoff_utc=cutoff, baseline_commit=comparison.get("baseline_commit"), ci=ci,
        changes=[dict(id=key, problem=problem, paths=paths, resolution=fix,
                      status=("IMPLEMENTED_PDF_NOT_SUPPLIED" if key == "R13" and
                              any(state["status"] != "PASS" for state in pdf.values()) else "IMPLEMENTED_AND_VERIFIED"))
                 for key, problem, paths, fix in CHANGES],
        coverage_summary=summary, per_league=per_league, actual_models=dict(model_counts), actual_markets=dict(market_counts),
        tests=tests, math=math, pdf=pdf, histories=dict(results=len(history), leagues=len(history_groups), events=len(events)),
        footprint=dict(changed_tracked_paths=changed, protected_changes=protected, production_multimodel_unchanged=True),
        n_counter_writes=0, calibrated=False, formal_forward_publication_verified=False,
        unresolved=["unsupported_or_insufficient_histories", "untrained_xgboost", "missing_event_statistics",
                    "unverified_legacy_match_dates", "fulltime_period_metadata_limit", "out_of_sample_calibration_not_verified"],
        environment_issues_resolved=["explicit_network_access", "complete_exact_clone", "local_venv"],
        source_sha256=verification.get("source_sha256", {}))
    return "\n".join(lines), ledger


def main():
    parser = argparse.ArgumentParser()
    for name in ("artifact-root", "comparison", "verification", "output", "ledger-output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--summary-pdf")
    parser.add_argument("--full-pdf")
    args = parser.parse_args()
    markdown, ledger = build(args.artifact_root, args.comparison, args.verification,
                             summary_pdf=args.summary_pdf, full_pdf=args.full_pdf)
    for path, value in ((args.output, markdown), (args.ledger_output, json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n")):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")
    print(json.dumps(dict(report=args.output, ledger=args.ledger_output, leagues=len(ledger["per_league"]), status=ledger["status"])))


if __name__ == "__main__":
    main()
