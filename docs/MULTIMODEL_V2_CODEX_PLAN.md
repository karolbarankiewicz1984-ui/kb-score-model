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
2026-11-02 | M2-017 | Audyt SOURCE_BLOCKED według stanu 1 XI 15:26 UTC | `MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.md/.json`: potwierdzony skip DST, awaria przed zapisanymi krokami bez ustalenia przyczyny; późniejsze runy oceniono osobno w E2E | starsza migawka, nie aktualny werdykt | DOCUMENTED.
2026-11-02 | M2-018 | Rzeczywiste rewizje KB/Konsensusu | `history.py`: potwierdzone wersje, CSV wielu tabel, oryginalne wartości, 202/202 i 211/214 selekcji; bez inferencji prematch i zmian N | odczyt historii działa; świeże prognozy niepotwierdzone | IMPLEMENTED / TESTED.
2026-11-02 | M2-019 | Historyczny pełny API powiązany z właściwym runem | `git_publication.py`, manifest/audit: run 40910335546, oryginalny blob/commit/runtime ID; osobny typ Git bez fikcyjnego upload-artifact | powiązanie odzyskane; quotes i pełny shadow BLOCKED | IMPLEMENTED / TESTED.
2026-11-02 | M2-020 | E2E ZIP 41323529393 / 41350611997 | `artifact_audit.py`, `MULTIMODEL_V2_E2E_AUDIT_2026-11-02.md`, JSON dowodowy: digest, daty/freeze, 28/20 i zero różnic, Pitch 58/61; potwierdzone P1/P2 oddzielone od podejrzenia lookahead | pełny shadow/ROI/dostarczenie prognoz SOURCE_BLOCKED | INSPECTED / DO_NOT_DEPLOY.
2026-11-02 | M2-021 | PDF/dostępność i regresja | jawny eksport API i częściowy Pitch, trzy A5 z brakami dla 2/3/4 XI, hashe bez fikcyjnego odbiorcy; 57 nowych testów, v2 198/198, całość 806/806 | modele/wagi/progi/archiwa/historyczne prognozy/N/workflow bez zmian; płatne skany i merge 0 | TESTED.
2026-11-02 | M2-022 | Wspólny cutoff API/PitchAPI w replay | kontekst 21:10Z nie był dostępny w freeze 15:54Z; 2/9 zgodnych tożsamości, ale 0/9 wejść dostępnych wtedy. Matcher przyjmuje as_of, shadow podaje oryginalny freeze, E2E pokazuje oba wyniki; nowy test granicy czasu | poprawka wyłącznie w izolacji; pełny shadow nadal SOURCE_BLOCKED | FIXED / TESTED.
2026-11-03 | M2-023 | Naprawa 1: D/D+1/D+2 i 11:30 Warsaw | planner.py, DST/late/SKIPPED, digest/run/checkout/fixture i kompletne źródła; minimalny patch days2→3 tylko jako propozycja | 41 testów; workflow bez zmian | CODE DONE / DATA BLOCKED.
2026-11-03 | M2-024 | Naprawa 2: native formal freeze KB/Konsensus | formal_freeze.py, oryginalne ID/fixture/quote/cutoff, historia oddzielnie, atomowy świeży zapis poza checkout; aktualny odczyt 202/214 bez formalnych publikacji | 35 testów; Google bez zapisów/N | CODE DONE / DATA BLOCKED.
2026-11-03 | M2-025 | Naprawa 3: pełna pula i zbieranie oryginałów na przyszłość | full_pool.py/capture.py: zachowanie poniżej67 i TOP, oryginalny runtime trace z niezmienionego filtra, raw receipts, SHA, retencja/rozmiar/redakcja; brak fikcyjnego odzysku1473/999 | 42+11 testów; hooki/upload nie wdrożone | CODE DONE / DATA BLOCKED.
2026-11-03 | M2-026 | Naprawa 4: native settlement linkage | settlement.py: native ID/exact market/frozen_quote, oddzielny TOP/API/FAULE UNDER, własna brama TOP, WIN/LOSS/VOID/UNRESOLVED i kompletne ROI; 1391 obcych rekordów odrzuconych | 40 testów; rzeczywiste ROI null; bez N | CODE DONE / DATA BLOCKED.
2026-11-03 | M2-027 | Integracja czterech napraw i regresja | repair_pipeline.py: pełne pokrycie fixture i dostępność źródeł w oryginalnym cutoff, 20 testów integracyjnych; rzeczywiste 28/20 bez różnic, native222/TOP51 bez zmian | 189 nowych, v2 387/387, pełna regresja995/995; patche nie zastosowane, skany/merge0 | TESTED / SOURCE_BLOCKED.
2026-11-03 | M2-028 | Integracja rzeczywistego producenta w izolacji | producer.py: observer już zwróconego api_get i oryginalnego archive_publication, pełna pula/raw/trace/status poza checkout, brak dodatkowych zapytań i zmiany natywnych zwrotów; późny oryginał zachowany bez nowego trace | rzeczywisty kod experiment 12ebe32 identyczny bajtowo w fixture, 3 daty offline, 15→15 calls, całe payload/TOP/freeze identyczne | CODE TESTED / NOT DEPLOYED.
2026-11-03 | M2-029 | Opcjonalny upload i konsument tej samej rewizji | bundle.py: opt-in, kompletność 3 dat/etapów, digest/source/retencja/sekrety/cutoff, osobne CAPTURE_COMPLETE i source_ready, ZIP odczytany i ponownie sprawdzony | niezastosowane bootstrap/upload/provenance patche, brak zmiennych repo i uploadu produkcyjnego | CODE TESTED / G2 PENDING.
2026-11-03 | M2-030 | Formalny callback i natywne outcomes | publication_bridge.py wyłączony bez autentycznego producenta; outcome_bridge.py i settlement.py zachowują native ID/exact market/wybrany quote, walidują receipts FT/statistics bez wymyślania finished_at | KB/Konsensus nieaktywne wg nowych commitów operatora; API-only osobno, brak oryginalnych quote/period nadal blokuje settlement, N0 | CODE TESTED / DATA BLOCKED.
2026-11-03 | M2-031 | Regresja kontrolowanego rollout i synchronizacja | dołączono 4 commity operatora do 4d8e1f0 wyłącznie przez fast-forward tej samej gałęzi; 28 nowych testów, 1026/1026 całość po synchronizacji; istniejący realny export 28/20 nadal bez różnic | zero zmian źródłowych tools/config/data/archiwów/modeli/workflow względem 4d8e1f0; bez paid scan, deploy, merge do main | TESTED / FULL SHADOW NOT PASS.
2026-11-03 | M2-032 | Dowody i zamknięcie integracji | commit 8903506, push CI41648981909 i PR CI41648992477 SUCCESS, oba logi1026; raport MD/JSON, 32 dokładne ścieżki, G0/G1 techniczny offline PASS, G2 pending, rzeczywiste G3/G4 SOURCE_BLOCKED | nowa polityka API-only/Pitch i brak osobnej sekcji FAULE UNDER uwzględnione w ograniczeniach przyszłej publikacji; patche i formalni observerzy nadal nieaktywne | REVIEW READY / DO NOT DEPLOY.

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
