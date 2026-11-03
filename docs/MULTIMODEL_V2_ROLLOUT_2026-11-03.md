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


## Wynik integracji kontrolowanej — 2026-11-03

Kod zapisany w `8903506f36e607c269ba89c623a06837b938dd61`. W trakcie pracy
zsynchronizowano tę samą gałąź do commitów operatora `4d8e1f0` (fast-forward).
Źródłowych algorytmów, aktywnych workflow i plików historycznych nie zmieniono.

| Bramka | Wynik po integracji | Znaczenie |
| --- | --- | --- |
| G0 | PASS offline | Natywny observer i regresja 1026/1026, w tym 28 nowych testów; 418 testów v2 |
| G1 | PASS techniczny offline | Trzy daty, rzeczywisty niezmieniony kod producenta 12ebe32, 15→15 wywołań stubu; pełne payload/TOP/freeze identyczne, ZIP/konsument tej samej rewizji |
| G2 | PENDING | Osobne niezastosowane bootstrap/upload/provenance patche; brak włączenia zmiennych, skanu i uploadu w produkcji |
| G3 | SOURCE_BLOCKED dla pełnego shadow | Native profile nadal nie zawiera exact identity/period/wybranego quote. KB/Konsensus nieaktywne; formalny callback pozostaje wyłączony bez autentycznego producenta |
| G4 | SOURCE_BLOCKED | Nie ma kompletnego rzeczywistego settlement tego samego ID/rynku/quote; pełny shadow nie jest PASS |

G1 dotyczy wyłącznie kompletu zapisu technicznego na jawnych unit inputs.
Nie potwierdza dostępności rzeczywistych trzech dni ani realnych prognoz.
Zgodnie z nową polityką operatora brak nieaktywnych KB/Konsensusu nie blokuje
odrębnego API-only; tożsamość rynku, quotes i freeze nadal wymagają weryfikacji.
PitchAPI pozostaje kontekstem. Nowych raportów użytkowych według dawnej polityki
osobnej sekcji FAULE UNDER nie opublikowano.

Szczegóły: [raport integracji](MULTIMODEL_V2_ROLLOUT_REPORT_2026-11-03.md),
[dowody i lista plików](MULTIMODEL_V2_ROLLOUT_REPORT_2026-11-03.json),
[kontrakt i osobne propozycje](MULTIMODEL_V2_PRODUCER_INTEGRATION.md).
