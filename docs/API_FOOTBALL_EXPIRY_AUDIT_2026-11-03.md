# API-Football — audyt przed wygaśnięciem 2026-11-04

Status: sprawdzono metadane repozytorium i GitHub Actions 2026-11-03. Bez nowych wywołań API, bez modyfikacji modeli, progów, TOP, N i archiwów.

## Potwierdzone zasoby na main
- data/api_football/market_scan: 28 plików; najnowszy 2026-11-02.json (3 125 880 B); 2026-11-01.json 7 337 214 B; 2026-10-25.json 20 665 805 B.
- data/api_football/market_snapshots: 28 katalogów, w tym 2026-11-03. Nie zweryfikowano zawartości poszczególnych katalogów.
- data/api_football/predictions: 27 katalogów, do 2026-11-02.
- data/api_football/daily: 29 plików, do 2026-11-02.
- data/pitchapi/prematch: 17 plików, w tym 2026-11-04.json (84 010 B); PitchAPI pozostaje aktywne według operatora.
- reports/api_market_scan: dzienne raporty do 2026-11-02.

## Artefakty Actions
- API Market multiday run 41509023488: success; artifact 13172816639, api-market-multiday-experiment, 94 370 B, expires 2027-01-31. Metadane nie dowodzą kompletności dat ani zawartości.
- PitchAPI run 41548660035: success; artifact 13190221413, pitchapi-prematch-context, 285 208 B, expires 2026-12-02.
- API Market Scan run 41630628732 (2026-11-03): success, brak artefaktów Actions; nie oznacza to braku commitowanych danych.

## Ryzyka i działania przed końcem abonamentu
1. Zidentyfikować rzeczywiste ścieżki pełnych oryginalnych odpowiedzi i quote snapshots oraz sprawdzić zachowanie timestamps, fixture, market identity, bookmaker, line i frozen quote; metadane katalogów nie są wystarczające.
2. Sprawdzić integralność plików, wielkość, SHA, datę źródłową i pre-match; nie traktować danych późniejszych jako zamrożonych.
3. Zachować poza Actions kopie artefaktów z krótszą retencją; repozytorium nie jest automatycznie kopią artefaktu ZIP.
4. Nie uruchamiać dodatkowych płatnych skanów bez decyzji operatora. Zakończenie subskrypcji nie usuwa zapisanych w Git plików, ale może zatrzymać świeże pobieranie.
5. W MULTIMODEL nie traktować nieaktywnych KB21/Konsensus jako bieżących źródeł. Oddzielić historyczny audyt od bieżących propozycji API.
6. KB Score 3.0 w osobnym repo; wymaga odrębnego audytu jego własnych wejść i zależności od API-Football.

## Ograniczenia
To inwentaryzacja potwierdzonych ścieżek i artefaktów, a nie pełny backup ZIP, test kompletności payloadów lub test uruchomienia modelu bez API-Football. Nie potwierdzono możliwości odzyskania pełnej puli odrzuconych kandydatur.
