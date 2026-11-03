# MULTIMODEL v2 — kontrolowany rollout, 2026-11-03

## Wykonane
- Na izolowanej gałęzi codex/multimodel-v2 w commicie b2032b14602eea7d772e7e8b0d5912ef7b7c976a zmieniono workflow api-market-multiday-experiment.yml: dispatch default days=3, scheduled fallback DAYS:-3, komunikat liczby dni. Brak merge; nie uruchomiono skanu.
- Zbadano oba przygotowane patche i instrukcję docs/MULTIMODEL_V2_FORWARD_CAPTURE.md. Patch full-source-upload jedynie uploaduje katalog runner.temp/multimodel-v2-sources; nie tworzy go. Włączenie go bez podłączonego producenta i przy zmiennej true kończy się błędem (if-no-files-found: error). Dlatego pozostaje wyłączony.

## Do wykonania przed uruchomieniem (Codex)
1. Na codex/multimodel-v2 zintegrować recorder z rzeczywistym kodem experiment/api-market-2-playable-odds bez modyfikacji scoringu i filtra. Zweryfikować, że checkout workflow używa osobnej gałęzi eksperymentalnej; sam merge workflow do main nie udostępni recorderów w checkout.
2. Po istniejącym pobraniu API przechwycić raw receipt, po oryginalnej natywnej publikacji zapisać full_pool z jej rzeczywistym ID i decyzjami odrzucenia; wyjście do runner.temp, nie do archiwów. Natywny SHA i data, retencja, redakcja sekretów, brak nadpisania.
3. Wpiąć opcjonalny upload dopiero po pozytywnym offline teście producenta i konsumenta z tej samej rewizji. Brak danych ma dać jawny SOURCE_BLOCKED, nie fałszywy PASS.
4. Dla KB21 i Konsensusu sprawdzić autentyczne natywne punkty publikacji. Bez istniejącego producenta i oryginalnych publication IDs nie włączać pozornego freeze. Przygotować forward-only integrację wymagającą zgody i dostępu do właściwego producenta.
5. Rozliczenia: czytać wyłącznie outcomes z tego samego native publication ID, fixture, exact market i frozen quote. Trzy kohorty osobno; ROI null gdy niepełne. Nie używać 1391 obcych obserwacji.
6. Wykonać test offline: D/D+1/D+2, oba sloty DST, daty, cutoff, 1:1, puste artefakty, partial, retencja, no secrets. Dopiero po green CI przygotować minimalne, osobne PR do przeglądu produkcyjnego. Żadnego automatycznego merge, ręcznego paid scan lub zmiany main.

## Bramki uruchomienia
G0: testy i źródłowe hooki w izolacji — PENDING.
G1: potwierdzony native recorder i pełny artefakt na suchym offline replay — PENDING.
G2: zatwierdzona konfiguracja workflow i świadome koszty dodatkowej trzeciej daty — PENDING.
G3: pierwsze rzeczywiste przedmeczowe publikacje KB/Konsensus i kompletne quotes — SOURCE_BLOCKED.
G4: prawidłowe settlement tego samego ID i shadow 1:1 — SOURCE_BLOCKED.

Produkcja niezmieniona. Brak płatnych skanów, merge i zmian N.
