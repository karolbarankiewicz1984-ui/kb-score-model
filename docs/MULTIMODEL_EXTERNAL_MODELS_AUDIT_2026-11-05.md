# MULTIMODEL — audyt trzech modeli open source (2026-11-05)

## Decyzja
Wyłącznie równoległy eksperyment **shadow**, bez zmian progów produkcyjnych, freeze, TOP, N, modeli KB Score 2.1/3.0 i bez pobierania API-Football. Żaden wynik nie jest jeszcze dowodem przewagi predykcyjnej.

| Repozytorium | Licencja kodu | Co wnosi | Ryzyka / ograniczenia | Decyzja |
|---|---|---|---|---|
| callumfm/dixon-coles | MIT (Copyright 2026 Callum Macalister) | Poisson/Dixon-Coles, decay, shrinkage, cele/xG, scoreline→1X2 | dane przykładowe EPL, pochodzenie i prawa do xG osobno; możliwość współdzielenia błędów z M0 | P1: pierwszy adapter |
| GeorgiosLymperis/football-predictor | MIT (Copyright 2026 Georgios Lymperis) | Bayesian Poisson, Elo+XGBoost, logistic, MLP, ensemble, walk-forward RPS | ciężkie PyMC/MLflow, 6 lig, pliki modeli, różne źródła cech; brak niezależnego dowodu przewagi | P2: najpierw logistic/Elo+XGB, potem reszta |
| 0ywfe/football-prediction-model | MIT (Copyright 2026 0ywfe) | 54 cechy, Elo, xG, XGBoost, temporal splits | 2 commity, zależności od scraperów FBref/StatsBomb, xG proxy i calibracja remisu wymagają audytu | P3: eksperyment bez scraperów w produkcji |

Źródła: https://github.com/callumfm/dixon-coles ; https://github.com/GeorgiosLymperis/football-predictor ; https://github.com/0ywfe/football-prediction-model

## Kontrakt i bramki dopuszczenia
- PitchAPI jako aktualny kontekst, nie automatycznie źródło dokładnych kursów, etykiet historycznych ani wszystkich cech wymaganych przez obce modele.
- Każda prognoza: fixture ID, liga, UTC kickoff, timestamp danych i prognozy, model+wersja+hash, p_home/p_draw/p_away sumujące się do 1, flagi dostępności cech, freeze sprzed kickoffu.
- Brak niezbędnej cechy: **abstain**, nie uzupełniać wynikiem z przyszłości, nie zakładać dostępności xG przed publikacją.
- Osobne mapowanie drużyn/lig i definicji xG; split chronologiczny train/validation/holdout; ten sam zestaw meczów dla wszystkich porównań.
- Mierniki: Brier multiclass, log loss, RPS, kalibracja, hit rate i pokrycie; ROI wyłącznie dla zweryfikowanych kursów exact-market zamrożonych przed meczem. Benchmarki: M0, Elo-only, ewentualnie rynek po usunięciu marży.
- Dane testowe nie są dowodem jakości produkcyjnej. Unikać przetrenowania wag ensemble na holdout; korelację modeli mierzyć na wspólnych błędach.
- MIT wymaga zachowania licencji i copyright przy redystrybucji kodu; licencje danych, modeli i zależności sprawdzić oddzielnie.
- Nie dodawać automatycznego pobierania obcego kodu w CI; pin SHA i skan zależności przed ewentualną integracją.

## Plan
1. P0: ustabilizować 3-PDF i trzydniowe snapshoty PitchAPI, zamknąć regresję.
2. P1: adapter Dixon-Coles + wspólny kontrakt i testy no-leakage (bez zewnętrznych importów).
3. P2: adaptery Elo/XGBoost/logistic na wspólnym, rzeczywiście dostępnym zbiorze cech.
4. P3: 0ywfe jako alternatywna konfiguracja, oddzielny audyt xG proxy i kalibracji remisów.
5. Zebrać rzeczywiste, zamrożone prognozy; raport porównawczy per liga; dopiero potem decyzja o wadze w MULTIMODEL.

## Rejestr zmian
2026-11-05: audyt licencji i architektury; decyzja shadow-only; bez modyfikacji modeli produkcyjnych. Wynik porównawczy: **jeszcze niedostępny**.

## Implementacja — 2026-11-05 (kolejny etap)
- Utworzono `multimodel_v2/dixon_coles_shadow.py`: adapter do zewnętrznej biblioteki callumfm/dixon-coles, bez ingerencji w produkcję; default goals-only, wymóg daty publikacji danych i cutoffu; nie instaluje ani nie pobiera pakietu samodzielnie.
- Utworzono `tests/test_multimodel_v2_dixon_coles_shadow.py`: testy braku historii, future-publication, xG provenance, post-kickoff freeze.
- Wstępny przegląd repozytorium: `data/pitchapi/prematch` to snapshoty kontekstu, nie gotowy zbiór zweryfikowanych historycznych wyników z czasem publikacji; `data/football_data_org` wymaga mapowania i kontroli pochodzenia. **Brak podstaw do deklaracji rzeczywistego backtestu.**
- CI dla commitu `3015085b73f8154f171ab009b2831db1feb38142`: uruchomienie #56, wynik oczekiwany w chwili wpisu.
- Następna bramka: audyt historycznego źródła wyników, mapowanie identyfikatorów i czasu publikacji, pin zależności, trening i porównanie na wspólnych meczach.

## Etap audytu historii — 2026-11-05
- CI #56 dla adaptera Dixon-Coles: **success** (GitHub Actions run 42106615544).
- Dodano `multimodel_v2/historical_result_audit.py` i testy: weryfikacja wyniku, czasu zakończenia i publikacji, deduplikacji, statusu dopuszczenia do treningu. Narzędzie jest read-only i nie tworzy fałszywych historii.
- Sprawdzono `data/football_data_org/2026-10-17.json`: pokazany rekord ma status `TIMED` i nie zawiera końcowego wyniku — nie wolno go uznać za próbkę treningową.
- Sprawdzono `data/pitchapi/prematch/2026-11-05.json`: `home_recent.samples` zawiera daty wcześniejszych spotkań i xG, ale bez końcowych goli i potwierdzonych timestampów publikacji tych wyników — to nie jest gotowy trening Dixon-Coles.
- Stan `main` w chwili przeglądu: najnowszy dostępny snapshot `2026-11-05.json`; brakuje plików `2026-11-06.json` i `2026-11-07.json`. Harmonogram dwukrotny istnieje, ale **brak potwierdzenia skutecznego zapisu danych**. Zdiagnozować run workflow, secret i pobieranie przed deklaracją naprawy.
- Kolejny krok: pozyskać zweryfikowane wyniki końcowe z identyfikatorami i datami publikacji, bez mieszania dostawców i bez retrospektywnego dopisywania czasu publikacji; uruchomić adapter i wspólny backtest dopiero na takim zbiorze.

## Wiążąca decyzja operatora — separacja warstwy porównawczej
- MULTIMODEL pozostaje **odrębnym** systemem głównym. Zewnętrzne projekty z GitHub są **wyłącznie warstwą porównawczą** (shadow/research).
- Warstwa porównawcza **nie** dostarcza propozycji do 3 PDF, nie zmienia rankingu, wag, filtrów, kursów, TOP/N, progów, modeli KB Score ani zamrożonych historycznych prognoz. Nie jest automatycznym ensemble.
- Dane mogą być analizowane na wspólnych, już zamrożonych meczach; wyniki porównania służą audytowi, bez automatycznego awansu do produkcji.
- Utworzono `multimodel_v2/comparison_only.py` oraz `tests/test_multimodel_v2_comparison_only.py`: porównanie tych samych fixture ID, lig i kickoffów, `production_eligible=False`, `ranking_weight=0`, brak selekcji.
- Ewentualna przyszła integracja z systemem głównym wymaga **oddzielnej, wyraźnej decyzji użytkownika** po wynikach testów.
- CI #62 poprzedniego etapu: success. Nowe testy rozdzielenia oczekują na odrębne potwierdzenie.

## Korekta decyzji operatora — niezależne prognozy GitHub Models
Poprzednie sformułowanie „warstwa porównawcza nie dostarcza własnych propozycji” zostaje **uchylone**. Aktualne zasady:
1. **GitHub Models to odrębny system prognostyczny**: modele open-source mogą generować własne rzeczywiste, zamrożone przedmeczowe prognozy i propozycje, własne raporty, archiwum i audyt. Nie trzeba czekać na wynik MULTIMODEL, aby stworzyć prognozę GitHub Models.
2. **MULTIMODEL pozostaje odrębny**: brak automatycznego importu typów z GitHub Models do MULTIMODEL, brak modyfikacji jego progów, rankingu, wag, TOP/N, 3 PDF i historii.
3. **Porównanie jest opcjonalne i tylko odczytowe**: porównujemy prognozy obu systemów na wspólnych meczach, bez mieszania rankingów.
4. Obecne `comparison_only.py` nadal służy **wyłącznie do porównywania**, ale jego flagi `production_eligible=False` i `ranking_weight=0` dotyczą wyłącznie **MULTIMODEL**, a nie możliwości niezależnego publikowania prognoz GitHub Models.
5. Przed rzeczywistym generowaniem prognoz konieczne są zweryfikowane dane, trening, zapis freeze i osobny generator raportów GitHub Models; nie przedstawiać wyników syntetycznych jako realnych.

## GitHub Models — szeroki terminarz, niezależna ocena (decyzja operatora)
- Bez arbitralnego limitu liczby meczów w kolejce: pobieramy wszystkie dostępne mecze z trzech dni ze snapshotów PitchAPI, pod warunkiem walidacji dat, ID, drużyn i snapshotu sprzed meczu.
- `github_models/daily_queue.py`: oddzielny, read-only generator kolejki dla Dixon-Coles, Elo i XGBoost; brak wyników i brak sztucznych prawdopodobieństw; każde z trzech modeli może niezależnie odrzucić mecz z powodu braków treningowych.
- `tests/test_github_models_daily_queue.py`: testuje pełny trzydniowy zakres, brak przyszłych snapshotów, brak zmyślonych prognoz.
- `.github/workflows/github-models-independent.yml`: oddzielny workflow planowany 07:00 UTC, zapisujący wyłącznie artifact kolejki `reports/github_models/queues`, z `contents: read`. Nie zmienia MULTIMODEL, jego PDF ani prognoz.
- **Uwaga wdrożeniowa:** harmonogram GitHub Actions działa automatycznie dopiero po umieszczeniu workflow na domyślnej gałęzi repozytorium; na gałęzi badawczej workflow jest przygotowany, nie jest jeszcze potwierdzony jako działający codziennie.
- Kolejka nie jest prognozą: do rzeczywistych typów trzeba osobno zapewnić wyniki historyczne, trenowanie każdego modelu, freeze prognoz i rozliczanie. Porównywać Brier/log loss/kalibrację i skuteczność, nie zakładać, że model open-source jest lepszy.

## Niezależne prognozy i rozliczanie — etap wdrożenia
- Dodano `github_models/elo_engine.py`: rzeczywisty, prosty model Elo z chronologicznym treningiem wyłącznie na wynikach końcowych, opublikowanych przed freeze. Wyniki to **niekalibrowane** prawdopodobieństwa badawcze; nie wolno utożsamiać ich z dowiedzioną przewagą.
- Dodano `github_models/predict.py`: samodzielny generator prognoz dla kolejki GitHub Models. Dla Elo generuje prognozy tylko gdy są zweryfikowane dane historyczne (minimum 5 meczów każdej drużyny). Dla Dixon-Coles i XGBoost zgłasza jawne blokady dopóki nie są gotowe trening i adapter; **nie fabrykuje typów**.
- Dodano `github_models/settle.py`: oddzielne rozliczanie wyników po potwierdzonym końcowym rezultacie, metryki Brier/log loss/hit rate, bez zmiany prognoz. Moduł jeszcze nie jest podłączony do automatycznego pobierania wyników.
- Rozszerzono workflow `github-models-independent.yml` o prognozy i plik blokad oraz testy `tests/test_github_models_independent_forecasts.py`.
- **Bramka wdrożenia:** historyczne wyniki `data/github_models/verified_results.json` muszą być prawdziwe i zawierać identyfikator, ligę, drużyny, końcowe gole, zakończenie i publikację. W repo brak potwierdzonego zasilania tego pliku. Bez niego Elo prawidłowo wygeneruje 0 prognoz i jawne blokady.
- Workflow pozostaje na gałęzi badawczej; harmonogram zadziała dopiero po bezpiecznym wdrożeniu na default branch. MULTIMODEL nadal nietknięty.

## KB Score 3.0 jako opcjonalne źródło zweryfikowanych wyników — 2026-11-05
- Odczytano (bez zmian) `karolbarankiewicz1984-ui/kb-score-3/data/pit_sidecar/m0_postmatch/2026-11-05/run-155034343937/M0_POSTMATCH_AND_CALIBRATION_REVIEW.json`: 21 rozliczonych prognoz, 29 oczekujących, nowo rozliczonych 0; ocena M0 nie stanowi automatycznie danych treningowych dla nowych modeli.
- Historyczne `step14_openfootball/2026-11-05.json` deklaruje `eligible_training_examples: 0` w sprawdzonym artefakcie. Nie wolno oznaczać go jako zweryfikowanego zbioru treningowego.
- Dodano `github_models/kb3_history_bridge.py` i testy: akceptacja tylko rzeczywistych wyników FINISHED z identyfikatorem źródła, drużynami, golami, czasem zakończenia i publikacji; usuwanie wszelkich obcych pól, w tym prognoz KB3. To **walidator eksportu**, nie aktywny dostęp między repozytoriami.
- Nie kopiowano danych chronionych, prognoz, SQLite ani zaszyfrowanych plików KB3; KB Score 3.0 i MULTIMODEL pozostają niezmienione.
- Następna bramka: przygotować niezależny eksport **rzeczywistych wyników** z wiarygodnym `published_at_utc`, sprawdzić mapowanie nazw drużyn i lig oraz testy, a dopiero potem zasilić `data/github_models/verified_results.json`.

## Etap: niezależne historyczne wyniki z publicznego źródła
- Dodano `github_models/public_results.py` pobierający rzeczywiste wyniki CSV z football-data.co.uk (5 lig, sezony 2023/24–2026/27), bez wywołań API-Football i bez odczytu prognoz KB3. Nie wymaga płatnej subskrypcji.
- `published_at_utc` oznacza **czas zaobserwowania wyniku przez NASZ importer**, nie dowód pierwotnej publikacji przez dostawcę. `completed_at_utc` to konserwatywna granica dzień meczu + 2 dni, a nie faktyczny moment zakończenia. Dane są dopuszczone dopiero po obu granicach. Źródło i liczebności zapisuje osobny manifest.
- Dodano `tests/test_github_models_public_results.py`, rozszerzono niezależny workflow: testy → publiczne wyniki → kolejka → prognozy → artefakty. **Nie wykonano jeszcze zdalnego workflow na tej gałęzi**, więc liczba rzeczywiście zaimportowanych meczów i wygenerowanych typów pozostaje niepotwierdzona.
- Ryzyko: nazwy drużyn z PitchAPI i football-data.co.uk mogą się różnić. Nie wolno automatycznie zgadywać mapowania ani twierdzić, że system produkuje kompletne typy przed audytem dopasowania ID/nazw. Dodatkowo, Dixon-Coles nadal wymaga opcjonalnej zależności i podłączenia do osobnego runnera.
- Nie dotykano repozytorium KB Score 3.0, produkcji MULTIMODEL ani oryginalnych prognoz. Nie publikować modelowych rekomendacji przed weryfikacją danych i kalibracją.

## Następna iteracja: naprawa workflow i mapowanie drużyn
- Wykryto błędne dosłowne znaki `\\n` w workflow `.github/workflows/github-models-independent.yml` (wcześniejszy zapis wielowierszowy). Naprawiono YAML w commicie `d192eec`.
- Dodano `github_models/team_mapping.py`: dopasowanie dokładne po normalizacji lub przez jawną listę aliasów; brak fuzzy guessing. Nieznane drużyny zgłaszają blokadę, zamiast generować prognozę dla niewłaściwego zespołu.
- Runner `github_models/predict.py` używa teraz tego mapowania przed Elo. Dodano testy aliasu i odmowy nieznanej drużyny; rozszerzono workflow o te testy.
- **Stan weryfikacji:** kod i testy zapisane, ale brak potwierdzonego CI dla najnowszego commitu oraz brak pełnego uruchomienia z pobraniem danych. Workflow nadal na gałęzi badawczej. Nie deklarować działającej codziennej automatyzacji ani liczby typów.
- Następne kroki: audyt rzeczywistych nazw i lig PitchAPI vs football-data.co.uk, test end-to-end, potem podłączenie Dixon-Coles. Przed uruchomieniem codziennym należy upewnić się, że workflow jest na default branch.

## Etap: uruchomienie dwóch niezależnych silników
- Dodano `github_models/dixon_coles_engine.py` i podłączono do `github_models/predict.py` obok Elo. Oba analizują tę samą kolejkę; Dixon-Coles wymaga minimum 30 zweryfikowanych historycznych wyników z ligi i historycznego składu drużyn.
- Workflow instaluje opcjonalny pakiet `dixon-coles==0.1.0` z osobnymi zależnościami. Dodano `tests/test_github_models_dixon_runner.py` weryfikujący uruchomienie dwóch niezależnych silników; XGBoost nadal jawnie oznaczony jako niegotowy.
- **Status:** kod zapisany, ale pełnego rzeczywistego uruchomienia ani zgodności z zewnętrzną biblioteką nie potwierdzono. Harmonogram na gałęzi badawczej nie jest automatycznie aktywny. Brak potwierdzonych prawdziwych typów, danych historycznych i testów CI tej iteracji.
- Wymagana kontrola: test end-to-end, zgodność API dixon-coles, pokrycie lig i mapowania nazw, zachowanie dat zamrożenia, metryki na niezależnym holdout. Nie wolno przedstawiać prognoz badawczych jako zweryfikowanych rekomendacji bukmacherskich.

## Audyt gotowości danych i kontrola zależności — kolejna iteracja
- Zweryfikowano bezpośrednio publiczny kod źródłowy `callumfm/dixon-coles`: `DixonColesModel.fit(home_teams, away_teams, home_goals, away_goals, dates, ...)` i `predict(home_team, away_team)` z kluczami `home_win/draw/away_win` odpowiadają wywołaniom adaptera. Nie jest to jednak test instalacji ani dopasowania na danych rzeczywistych.
- Dodano `github_models/coverage_audit.py`, raportujący dla każdego meczu dokładny powód blokady, pokrycie historii Elo i liczebność ligi dla Dixon-Coles. Workflow zapisuje odrębny artefakt `reports/github_models/coverage/YYYY-MM-DD.json`.
- Codex: użytkownik dopuścił wykorzystanie, jeśli potrzebne. Na tym etapie zmiany wykonano bez osobnego zadania Codex; brak uruchomienia sesji Codex.
- Wciąż niepotwierdzone: pełny workflow na GitHub Actions, pobranie CSV w środowisku CI, rzeczywiste dopasowania lig i drużyn oraz pierwsze zamrożone prognozy. Żadnych deklaracji o skuteczności bez wyników.

## Kontrola CI i naprawa prawdopodobieństw Dixon-Coles
- Zweryfikowano przez GitHub API: PR #55 (gałąź `codex/multimodel-v2` -> `main`) jest otwarty; `MULTIMODEL v2 isolated regression` dla commitu `79353cef` zakończył się `success` (run `42116313146`). **Nie jest to pełny workflow `github-models-independent.yml`**.
- Znaleziono realny błąd integracyjny: `callumfm/dixon-coles` zaokrągla wyniki `predict()` do 4 miejsc, więc suma 1X2 może odbiegać od 1 o 0.0001; walidator wymaga tolerancji 1e-6. Poprawiono normalizację, odrzucanie wartości niepoprawnych i dodano `tests/test_github_models_dixon_normalization.py` do workflow.
- Nie wykonano merge PR #55 ani zmian produkcyjnych. Codex nie był potrzebny do tej korekty.
- Nadal do sprawdzenia: instalacja pakietu i prawdziwe fit/predict, zgodność nazw lig PitchAPI, dostępność snapshotów na wszystkie 3 dni, faktyczne prognozy i zamrożenie wyników.
