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
