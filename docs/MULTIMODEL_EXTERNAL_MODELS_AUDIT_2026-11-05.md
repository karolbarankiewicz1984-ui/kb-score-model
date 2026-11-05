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
