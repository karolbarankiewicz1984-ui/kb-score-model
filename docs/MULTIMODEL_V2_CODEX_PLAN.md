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
2026-11-01 | M2-004 | Zadanie 1: read-only manifest źródeł | `multimodel_v2/source_manifest.py`: ukończony run, datowany status, SHA, artefakt, snapshot, kickoff i exact market; jawna blokada braków i lookahead | izolowane; brak zmian produkcyjnych | IMPLEMENTED.
2026-11-01 | M2-005 | Zadanie 2: testy pochodzenia i regresji | `tests/test_multimodel_v2_provenance.py`: daty, ceny, exact line, snapshot, duplikaty, reruny, DST Warsaw, niezmienność wejść; M2-002 potwierdzone testem braku trzeciej daty, bez zmiany workflow | wyniki w raporcie regresji poniżej | IMPLEMENTED.
2026-11-01 | M2-006 | Zadanie 3: niezależny filtr FAULE UNDER | `multimodel_v2/fouls_under.py`: kurs 1.50–2.00, 90 min, jawne statusy poniżej/od 67, brak kandydatur przy brakach, bez obserwacji po kickoff | bez zmian TOP/N/modeli/progów/archiwów | IMPLEMENTED.
2026-11-01 | M2-007 | Kontrakt wejściowy i ograniczenia | `docs/MULTIMODEL_V2_SOURCES.md`: normalizacja oryginalnych dowodów, brak odtwarzania brakujących danych, rozróżnienie SHA runu od checkout | bez kolektora, PDF i wdrożenia; zadania 4–6 pozostają otwarte | DOCUMENTED.
2026-11-01 | M2-008 | Zadanie 4: trzy niezależne audyty | `multimodel_v2/audit.py`: oryginalny TOP bez zmiany składu/kolejności, wszystkie kwalifikujące API, FAULE UNDER; tylko oryginalny prematch freeze, osobne wyniki, ROI i fixture-equal ROI wyłącznie przy komplecie rozliczeń i zamrożonych cen | bez rekonstrukcji TOP/kursów/wyników i bez zapisów N | IMPLEMENTED.
2026-11-01 | M2-009 | Zadanie 5: trzy osobne PDF A5 | `multimodel_v2/report_pdf.py`: D/D+1/D+2 Warsaw, DejaVu Sans >=7 pt (brama >=6 pt), FAULE UNDER na pierwszej stronie, paginacja, jawne braki, walidacja parserem wszystkich stron; publikacja dopiero całego poprawnego zestawu | bez nadpisywania archiwów i bez fałszywych ścieżek/linków | IMPLEMENTED.
2026-11-01 | M2-010 | Testy zadań 4–5 i izolowane CI | `tests/test_multimodel_v2_audit.py`, `tests/test_multimodel_v2_pdf.py`, odseparowane zależności i nowy workflow wyłącznie testowy; dwa parsery, wielostronicowość, błędne PDF, awaria drugiego pliku, DST i niezmienność wejść | 44 nowe testy; dotychczasowe workflow bez zmian | TESTED.
2026-11-01 | M2-011 | Kontrakt i kontrola plików wynikowych | `docs/MULTIMODEL_V2_AUDIT_PDF.md`, aktualizacja odnośnika źródeł; wizualna kontrola wyrenderowanych stron z danymi testowymi i brakami źródeł | egzemplarze bez przekazanych zweryfikowanych źródeł jawnie pokazują braki, nie fikcyjne prognozy | DOCUMENTED.
2026-11-01 | M2-012 | Poprawka zgodności z aktualnym PyMuPDF w CI | run 41304083060: PyMuPDF 1.28.2 wypisywało deprecjację aliasu `fitz` na stdout i naruszało kontrakt JSON CLI; użyto kanonicznego `pymupdf`, minimalna wersja 1.24.4 | istniejący test CLI zachowany, bez osłabiania walidacji i bez zmian produkcji | FIXED.
2026-11-01 | M2-013 | Etap 6: rzeczywiste adaptery read-only | `adapters.py`: natywne API Market/PitchAPI i oryginalne odpowiedzi Google Sheets; źródła odczytane, hashe capture, zachowanie oryginalnych pól; bez wymyślania ID, quote identity, freeze i kickoff | odczyt historyczny działa; świeże źródła 1–3 XI niekompletne | IMPLEMENTED / SOURCE_BLOCKED.
2026-11-01 | M2-014 | Test 1:1 tych samych freeze | `shadow.py`: oddzielnie eksporty 7 i 22 pozycji oraz pełny freeze 222/ TOP 51; zero różnic fixture/market/quote/status/score/TOP i zero niespójności freeze–eksport; pełny shadow czterech modeli zablokowany | brak połączenia różnych runów i brak zmiany oryginalnego TOP | PARTIAL.
2026-11-01 | M2-015 | Weryfikacja trzech rzeczywistych raportów | PDF dla 1/2/3 XI technicznie poprawne (po 3 strony A5), lecz pokazują aktualne braki i daty odczytanych źródeł; brak pełnego runu API/KB/Konsensusu/PitchAPI dla tych dat | brak fikcyjnych prognoz i wyników; nie uznano plików za kompletne raporty | SOURCE_BLOCKED.
2026-11-01 | M2-016 | Raport różnic i regresja etapu 6 | `MULTIMODEL_V2_STAGE6_REPORT_2026-11-01.md` oraz JSON; 35 nowych testów, 141 MULTIMODEL, pełna regresja 749; dwie kontrole parserem PDF | bez zmian modeli/progów/archiwów/N i bez kosztownych skanów API | TESTED.

## Raport regresji — zadania 1–3 (2026-11-01)

- Baza przed zmianami: `f5ce926dcee70dacdf030531998d0404bf2a2f76`, gałąź `codex/multimodel-v2`, katalog roboczy czysty.
- Testy bazowe: `python -B -m unittest discover -s tests` — 608/608 OK; w tym 59/59 testów API Market.
- Testy zadań 1–3: `python -B -m unittest discover -s tests -p 'test_multimodel_v2_provenance.py'` — 62/62 OK (offline, w tym DST, granice czasu/ceny/oceny i niezmienność wejść).
- Pełna regresja po zmianach: `python -B -m unittest discover -s tests` — 670/670 OK, Python 3.12.14.
- `git diff --check` — OK. Porównanie z bazą: zero zmian w `model/`, `config/`, `tools/`, `.github/`, `data/`, `reports/`, `archive/` oraz obowiązujących dokumentach modelu, progów i checkpointów. Zmieniono wyłącznie nowy pakiet, jego testy, kontrakt źródeł i ten rejestr.
- Przegląd: istniejący [draft PR #55](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/55), nadal bez merge i bez wdrożenia do produkcji.
- Brak uruchomienia skanu, zapisów obserwacji i rekonstrukcji prognoz. Status M2-003 pozostaje BLOCKED; nie ustalono przyczyny awarii bez logów.

## Raport regresji — zadania 4–5 (2026-11-01)

- Baza przed zmianami: `b2e5299922787ff3bc8b47ea1a2de99f03c2ca7b`, aktywna gałąź `codex/multimodel-v2`, czysty i aktualny względem origin katalog roboczy.
- Baza testów: 670/670 OK. Nowe testy: 25 audytu + 19 PDF = 44/44 OK.
- `python -B -m unittest discover -s tests -p 'test_multimodel_v2*.py'` — 106/106 OK.
- `python -B -m unittest discover -s tests` — 714/714 OK, Python 3.12.14.
- Kontrola PDF: PyMuPDF 1.26.6 i niezależny pypdf 6.10.0; ReportLab 4.4.9, osadzone DejaVu Sans, A5, minimalny faktyczny rozmiar 7 pt, polskie znaki, wszystkie strony z numeracją X/Y, brak aktywnych linków i tekstu poza stroną. Zweryfikowano również wzrokowo wyrenderowane strony.
- Po poprawce M2-012 pełna regresja ponownie 714/714 OK także w osobnym świeżym venv z aktualnymi zależnościami jak w CI: ReportLab 4.5.1, PyMuPDF 1.28.2, pypdf 6.21.4. Istniejący test CLI nadal wymaga czystego JSON na stdout. Nowy workflow testuje SHA gałęzi źródłowej, bez syntetycznego merge.
- Dokładnie trzy datowane pliki dla 2026-11-01/02/03; brak przekazanych zweryfikowanych źródeł jest jawny. Testowe prognozy i wyniki nie trafiają do plików użytkowych ani repozytoryjnych archiwów.
- `git diff --check` — OK. Dotychczasowe modele, progi, freeze, dane, raporty, archiwa, checkpointy i workflow bez zmian; jedyny nowy workflow jest testowy, bez harmonogramu, sekretów i uprawnień zapisu.
- Istniejący draft PR #55 pozostaje ścieżką przeglądu. Zadanie 6, integracja rzeczywistych eksportów i produkcyjne wdrożenie pozostają otwarte; bez merge do main. M2-003 nadal BLOCKED.

## Raport regresji — etap 6 (2026-11-01)

- Baza: `294112ebc1279c1eb8d1737daf4e1a3fbf827c83`, aktywna i czysta gałąź `codex/multimodel-v2`; odczyt origin/main nie zmienił main ani gałęzi roboczej.
- Dane rzeczywiste: eksporty runu `40906734194` (7/22 pozycji, zadeklarowane tła 222/934), osobny oryginalny freeze 222/TOP 51, odczyty Google KB 204 wiersze i Konsensus 214, dwa snapshoty PitchAPI 33/78 rekordów. Liczby odczytu nie są nowymi N.
- Wynik porównania pól 1:1: 0 różnic dla każdego z trzech odrębnych wejść. Pełny shadow i kompletne raporty 1–3 XI: **SOURCE_BLOCKED**, nie PASS; szczegółowe powody i różnice audytów w [raporcie etapu 6](MULTIMODEL_V2_STAGE6_REPORT_2026-11-01.md).
- Testy adapterów/shadow: 35/35 OK; MULTIMODEL v2: 141/141 OK; pełna regresja: 749/749 OK. Python 3.12.14, standardowa biblioteka w adapterach; bez wywołań źródłowych modeli/API.
- Trzy PDF A5 po 3 strony zweryfikowano dwoma parserami, osadzenie DejaVu Sans, >=7 pt, paginację, polskie znaki, FAULE UNDER na pierwszej stronie i brak aktywnych linków. Pliki z brakami nie zastępują kompletnych raportów prognoz.
- Wszystkie źródłowe modele, konfiguracja, progi, freeze, dane, raporty, archiwa, workflow i liczniki N bez zmian. Odczyty Google nie wykonywały żadnych zapisów. Nowych skanów API i merge: 0. M2-002 i M2-003 pozostają otwarte/zablokowane.
