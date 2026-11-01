# MULTIMODEL v2 — izolowany plan techniczny (2026-11-01)

Status: AUDYT WSTĘPNY; NIE WDROŻONO PRODUKCYJNIE.
Gałąź: `codex/multimodel-v2`, baza `main`.

## Zakres niezmienny
Nie zmieniać modeli, parametrów, progów, oficjalnego TOP, historycznych freeze, N ani archiwów. Żadnych prognoz po kickoff, brak syntetycznych kursów, P(model) lub EV. Wszystkie zmiany tylko na gałęzi eksperymentalnej, przez PR i testy regresji. Brak automatycznego merge.

## Wyniki audytu początkowego
- Workflow `.github/workflows/api-market-multiday-experiment.yml` uruchamia skan 10:00 Europe/Warsaw; checkout gałęzi `experiment/api-market-2-playable-odds`, a nie `main`.
- Domyślne `days=2` nie zapewnia trzech dat wymaganych przez raport 11:30. Rozszerzenie do trzech dat wymaga osobnego testu zgodności, bez modyfikowania obecnego procesu produkcyjnego.
- Run 41213715025 (2026-10-31) zakończył się failure; próba pobrania logu job 124573780300 zwróciła 404 BlobNotFound, więc przyczyna nie jest potwierdzona.
- 2026-11-01 dwa uruchomienia API Market Closing Snapshot zakończyły się sukcesem; nie dowodzi to sukcesu skanu wielodniowego.
- Wymagania źródłowe: `RAPORT_MULTIMODEL_3D.md`, `AKTUALNY_MODEL.md`, oryginalne Google Sheets, datowo właściwy ukończony run, PitchAPI prematch.

## Zadania dla Codex — kolejność
1. Zbuduj read-only `multimodel_v2/source_manifest.py`: data lokalna, ID runu, conclusion, SHA, nazwy artefaktów, snapshot timestamp, kickoff, market identity. Zablokuj daty niepokryte poprawnym ukończonym runem.
2. Testy `tests/test_multimodel_v2_provenance.py`: brak lookahead, niezgodne daty, brak kursu, rozbieżne exact line, brak snapshot, duplikaty fixture, DST Warsaw.
3. Zbuduj niezależny filtr FAULE UNDER 1.50–2.00: wyłącznie fouls/under, exact line, 90 min, team/match, bookmaker, prematch odds, timestamp, ocena API; poniżej 67 status EKSPERYMENT/POZA PROGIEM/NIE PLAY, inaczej OBSERWUJ; brak danych -> BRAK ZWERYFIKOWANYCH KANDYDATUR. Nie zmieniaj TOP/N.
4. Rozdziel audyty TOP / wszystkich API / FAULE UNDER, rozliczaj tylko zamrożone przedmeczowe pozycje, ROI i fixture-equal ROI tylko przy kompletnych danych.
5. Generator trzech PDF A5, DejaVu Sans, minimum 6 pt, FAULE UNDER na pierwszej stronie, test istnienia, parser PDF, paginacja, dokładnie trzy pliki i bez fałszywych linków.
6. Porównanie shadow 1:1 na tych samych wejściach, różnice i kontrolowany PR; żadnego merge bez akceptacji.

## Bramy jakości
- 100% zgodności oryginalnych prognoz i freeze; zero zmian produkcyjnych plików i archiwów.
- Testy odrzucają błędne źródła i brakujące kursy; nie produkują fikcyjnych typów.
- Trzy poprawne PDF na daty D, D+1, D+2; czytelny brak danych tam, gdzie źródeł nie ma.
- Rejestr zmian i raport regresji przed każdą decyzją o połączeniu.

## Rejestr zmian
2026-11-01 | M2-001 | Start równoległej gałęzi Codex | plan i audyt read-only | brak zmian produkcyjnych | OPEN.
2026-11-01 | M2-002 | Ryzyko: multi-day default 2 vs 3 dni raportu | test planner i pokrycia dat | OPEN.
2026-11-01 | M2-003 | Nieudokumentowana przyczyna failure run 41213715025 (log 404) | ponowna diagnoza po odzyskaniu logów | BLOCKED.
