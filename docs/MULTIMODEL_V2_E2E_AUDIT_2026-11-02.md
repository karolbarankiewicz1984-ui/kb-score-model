# MULTIMODEL v2 — audyt end-to-end, 2026-11-02

**Rekomendacja: NIE WDRAŻAĆ. Pełny shadow: SOURCE_BLOCKED.**
Wykonano inspekcję rzeczywistych ZIP, metadanych, logów, Google, kodu, rozliczeń i PDF. Nie zatwierdzono kompletności czterech modeli ani odtworzenia ich matematyki bez oryginalnych wejść.

Gałąź `codex/multimodel-v2`, baza `334a266`. Stan odczytu: **2026-11-02 18:06:41 UTC / 19:06:41 Europe/Warsaw**. D=2 XI, D+1=3 XI, D+2=4 XI. Osobno sprawdzono horyzont runu z 1 XI: 1/2/3 XI. Dowody: [E2E JSON](MULTIMODEL_V2_E2E_EVIDENCE_2026-11-02.json). Raporty z 1 XI są starszymi migawkami, nie aktualnym werdyktem.

## Usterki i blokady

P0: **brak potwierdzonych P0 w sprawdzonym materiale**. Braki wejść nie pozwalają wykluczyć nieznanych usterek poza odtworzonym zakresem.

| ID | Priorytet / dowód | Usterka lub blokada | Poprawka / rozwiązanie | Status |
| --- | --- | --- | --- | --- |
| P1-001 | P1, potwierdzone | Artefakt ma 1/2 XI, brak 3 XI; dla bieżących 2/3/4 XI jest tylko eksport 2 XI. Wykonany plan dwóch dat zgadza się z days=2 | Inspektor kontroluje rzeczywiste daty eksportów/statusów/freeze/PDF. Przyszły horyzont 3 dat wymaga osobnego testu; workflow bez zmian | OPEN |
| P1-002 | P1, potwierdzone | Wydanie 1 XI powstało o 16:54 Warsaw, po terminie 11:30. Właściwy slot zaakceptowano prawidłowo mimo opóźnienia | Oddzielono termin dostarczenia od kickoffu. Szukać istniejącego wcześniejszego wydania, bez tworzenia go wstecz | OPEN — terminowość |
| P1-003 | P1, potwierdzone | Brak świeżych formalnych prognoz KB/Konsensusu i strukturalnego fixture/kickoff/exact market/freeze/quote | Odczyt historii działa; potrzebne autentyczne nowe publikacje, nie przeniesienie starych rekordów | SOURCE_BLOCKED |
| P1-004 | P1, potwierdzone | Eksport 28/20 nie zawiera pełnych 1473/999 kandydatur ani upstream rankingu 340/213. Brak niezależnej quote identity i publication.id w audit_input | Adapter weryfikuje bajty i zachowuje znane pola. Odzyskać oryginalne brakujące wejścia tego samego runu; bez łączenia snapshotów lub tworzenia ID z hasha | SOURCE_BLOCKED |
| P1-005 | P1, potwierdzone | Dostępne 1391 rozliczeń dotyczy innej publikacji produkcyjnej; brak rozliczeń powiązanych z badanym freeze | Nie przeniesiono gotowych obserwacji ani miar. TOP/API/FAULE UNDER pozostają odrębne, ROI niedostępne | SOURCE_BLOCKED |
| P1-006 | P1, potwierdzone | Snapshot PitchAPI 21:10Z jest późniejszy od pierwotnego freeze API 15:54Z. Dopasowanie tożsamości 2/9 nie oznacza dostępności w chwili freeze | Dodano cutoff do matchera i replay. W oryginalnym freeze dostępne 0/9; późniejszy kontekst może służyć późniejszemu wydaniu | FIXED w izolowanym replay; bez wdrożenia |
| P2-001 | P2, potwierdzone | PitchAPI na 2 XI: 61 rekordów, 58 z datą Warsaw 2 XI, 3 z datą Warsaw 3 XI. Dopasowanie tylko 2/9 fixture API | Trzy rekordy wykluczono z pokrycia 2 XI, bez automatycznej zmiany daty/aliasów | EXCLUDED / niepełne pokrycie |
| P2-002 | P2, potwierdzone | ZIP ma dwa PDF po 2 strony 190×270 mm, nie trzy A5. Brak dowodu odbioru pełnych raportów | Trzy nowe A5 z jawnymi brakami i hashami dostępności sprawdzone. Nie udają pełnych prognoz ani potwierdzenia odbiorcy | Częściowo poprawione; pełne dostarczenie BLOCKED |
| RISK-001 | P1, podejrzenie | Filtr historii API porównuje próbkę z kickoffem, nie czasem publikacji; brak dat/ID użytych próbek w artefakcie | Wymagane oryginalne wejścia. Nie zmieniono algorytmu i nie uznano ryzyka za zaobserwowany wyciek | UNCONFIRMED |

## 1. Zawartość artefaktów i timestampy

Oba ZIP pobrano przez konektor GitHub, odczytano i potwierdzono digest z API:

| Run / artefakt | Rozmiar | Zgodny SHA-256 | Rzeczywista zawartość |
| --- | ---: | --- | --- |
| 41323529393 / 13089668808 | 99314 B | a63b898dfb51734c33a686511bec2f2f188a8a107bff7fbff259bc5866043276 | 10 plików: po eksporcie JSON/MD, statusie, audit_input i PDF dla 1/2 XI |
| 41350611997 / 13100867272 | 274692 B | 755c9351612428d079240b90cb9dd6944aa0e3ba1377087ac83698b7d80d1f41 | 16 historycznych snapshotów JSON i 16 MD; tylko snapshot 2 XI powstał w tym runie |

API ZIP porównano bajtowo z istniejącym mirror runu w origin/main: **10/10 zgodnych plików**. Archiwów nie nadpisano. Inspektor odrzuca obcy run/SHA, expiry, błędny digest/rozmiar, duplikaty i niebezpieczne ścieżki ZIP; nie rozpakowuje do produkcji.

| Data API | Tło deklarowane / eksport | Fixture eksportu | Freeze UTC | Naruszenia quote <= freeze < kickoff | Status |
| --- | --- | ---: | --- | ---: | --- |
| 1 XI | 1473 / 28 | 13 | 1 XI 15:54:36.230183 | 0/28 | ok |
| 2 XI | 999 / 20 | 9 | 1 XI 15:54:47.669746 | 0/20 | ok |
| 3 XI | brak | — | brak | nieustalone | brak daty |

Eksporty zapisują market/scope/team/direction/line/settlement_period, bez duplikatów exact market. Opublikowane score >=67 i kursy >=1.20. Odrzucenia 312+1133+28=1473 i 193+786+20=999 zgadzają się liczbowo; liczniki nie odtwarzają brakujących rekordów, zwłaszcza fauli under <67. Kontrola czasu dotyczy 48 opublikowanych pozycji, nie całej historii kandydatur. Żaden quote nie potwierdza aktualnego kursu STS/Superbet.

## 2. Workflow, daty i DST

- 41323529393: właściwy slot przyjęty mimo opóźnienia; scan/upload success. Log i ZIP potwierdzają dokładnie dwie daty, nie sam default.
- 41317765320 oraz dzisiejszy 41495085072: scan/upload skipped; runtime notice potwierdza przeciwny slot `0 8 * * *`. Stan **SKIPPED**, nie FAILURE ani SUCCESS_WITH_DATA; source_eligible=false.
- W listopadzie 10:00 Warsaw to 09:00 UTC. Opóźnione przyjęcie właściwego slotu jest poprawne, lecz nie gwarantuje raportu o 11:30.
- Pełna sprawdzona lista dzisiejszych runów: 13/13. Udane raw scany 41443035592/41486556120 to inny workflow. Nie ma w niej wykonanego multi-day obejmującego 2/3/4 XI.
- Head SHA definicji/runu `634c890…` odróżniono od rzeczywistego checkout kodu eksperymentalnego `12ebe32220d04b7488889b2c7c4384ff47eb9d2e`, potwierdzonego logiem. Kod odczytano po tej rewizji; nie uruchamiano go i nie zmieniano.

## 3. Aktualne źródła KB/Konsensus/PitchAPI

Ponownie odczytano oryginalne arkusze. KB Rejestr A1:AP1000: 496 niepustych wierszy, **202 selekcje**, 294 wpisy szablonowe/niepełne, ostatnia data wydarzenia 6 X. Szerzej odczytany zakres wyjaśnia różnicę wobec 204 wierszy wcześniejszego capture — to nie wzrost N. Konsensus Selections A1:Z1000: **214 selekcji**, ostatnia Date 14 X, strefa America/Los_Angeles. Nie tworzono kickoffu/freeze z Analysis Time.

PitchAPI 2 XI: snapshot z 1 XI 21:10:31.906535Z, 58/61 rekordów spełnia datę Warsaw i kontrolę zapisanej historii sprzed snapshotu. Trzy kickoffy 2 XI 23:00/23:30 UTC są już 3 XI Warsaw. Dokładna zgodność drużyn, ligi i UTC kickoffu daje **2/9** fixture API 2 XI. Brak snapshotów 3/4 XI w odczytanym drzewie main; stare pliki w ZIP nie są nowymi snapshotami tego runu.

Te 2/9 są dopasowaniem do kontekstu dostępnego obecnie. W chwili pierwotnego freeze API o 15:54Z późniejszy snapshot PitchAPI z 21:10Z nie istniał: **0/9** dopasowań przy wspólnym cutoffie. Matcher przyjmuje jawne as_of, replay podaje oryginalny freeze, a raport E2E rozdziela oba wyniki. Nie przepisano późniejszego kontekstu do dawnego wejścia. Bieżący PDF jawnie używa późniejszego czasu raportu.

Nie zapisano nic do arkuszy i nie kopiowano prywatnych uwag/autorów do repo. Odzysk rewizji pozostaje osobno udokumentowany w [audytach blokad](MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.md).

## 4. TOP, exact market, kursy, freeze i N

Porównanie niezależnego odczytu źródła i adaptera: **28→28, 20→20; 0 różnic pól, 0 niespójności freeze–eksport**. Zachowano fixture ID, exact market, kurs/bukmachera/timestamp, ocenę, status i kolejność. Kolejność zgadza się z zapisaną regułą score/API/fixture/selection.

To eksport playable. Log mówi o upstream rankingach 340/213 oraz publikacjach `155435807739-50e8bbe9d1c5d925` i `155447364408-95a9cbca691af9eb`, których pełnych plików brak w ZIP. Nie odtworzono ich z innych snapshotów. Bez background nie można sprawdzić wszystkich odrzuceń, maksimum spośród niezapisanych quotes ani ponownie obliczyć matematyki modelu.

Tożsamość kandydatury jest zapisana; niezależna quote identity nie. Brakujący publication.id i settlement_period w audit_input nie zostały dopisane. Hash jest technicznym dowodem odczytu, nie natywnym ID. Oryginalne prognozy/TOP/freeze i progi bez zmian.

KB/DEV/API mają odrębne źródła obserwacji. 202/214/61/1391 to liczności odczytu, nie nowe N. Logi deklarują kb_n_effect=dev_n_effect=0, PitchAPI model_effect=NONE. Audyt nie uruchamia modeli, setterów ani kolektorów. Oficjalne checkpointy/rejestry względem bazy bez zmian i bez przeliczania N.

## 5. Rozliczenia TOP/API/FAULE UNDER i ROI

Trzy kohorty pozostają odrębne. Wszystkie API i FAULE UNDER wymagają pełnego tła, nie eksportu po odrzuceniu score <67. Nie utworzono pozornego kompletnego zera fauli.

Zapis calibration/2026-11-01.json zawiera 1391 obserwacji, wszystkie prediction_id `161419348869-9e30d0bd0d7d0096`. **0** powiązano z natywnymi publikacjami badanego runu. Nie przeniesiono gotowych rozliczeń, cen i ROI. Wspólny fixture nie identyfikuje całego freeze.

Ścisłe audyty tych wejść: SOURCE_BLOCKED, pełna populacja nieustalona, **ROI=null, fixture-equal ROI=null**. Braki nie są loss. Regresja osobno sprawdza arytmetykę jednostkową, równą wagę fixture, void/push, kompletność i zgodność freeze. Nie zatwierdza to rzeczywistych wyników bez źródeł.

## 6. PDF i kontrola dostarczenia

Dwa źródłowe PDF otwarto dwoma parserami: po 2 strony, 538.58×765.35 pt (190×270 mm), minimum 6.5 pt, zero aktywnych linków. To poprawne dokumenty API, lecz nie realizują kontraktu trzech A5 MULTIMODEL.

Po poprawce komunikatów wygenerowano trzy osobne kontrolne pliki 2/3/4 XI, po **3 strony A5**, DejaVu Sans >=7 pt. PyMuPDF, pypdf, paginacja, granice tekstu, polskie znaki, FAULE UNDER na pierwszej stronie i kontrola wzrokowa — OK. Na 2 XI PDF pokazuje dostępne 20 pozycji eksportu i 58 rekordów częściowego kontekstu, bez udawania kompletnego źródła lub całkowitego braku odczytu.

check_delivery potwierdza istnienie trzech plików i SHA-256: **FILES_VERIFIED_AVAILABLE**, recipient_receipt_confirmed=false, complete_forecast_delivery=false. Link i istnienie pliku nie dowodzą odbioru przez zewnętrzny kanał. Nie wysyłano wiadomości ani nie wymyślano potwierdzenia. PDF z brakami nie jest kompletną prognozą ani zgodą na wdrożenie.

## 7. Poprawki, testy i odtwarzanie

- Nowe izolowane moduły: digest/odczyt ZIP i E2E, dowód historycznej publikacji Git, rzeczywiste rewizje arkuszy, klasyfikacja odzysku/DST. Żaden nie pobiera płatnych danych.
- Poprawki v2: typ git_publication w manifestach/audycie, jawne częściowe dane w PDF, osobne selekcje i szablony KB, kontrola brakujących dat/plików i dostępności PDF bez fikcyjnego odbiorcy.
- **57 nowych testów; MULTIMODEL v2 198/198; pełna regresja 806/806**, Python 3.12.14. Pełna regresja na bieżących zależnościach PDF jak w CI; testy lokalne offline.
- git diff --check i kontrola zakresu — OK. Modele, algorytmy, wagi, progi, dane, archiwa, historyczne prognozy, narzędzia produkcyjne, workflow i N bez zmian. Płatne skany uruchomione przez audyt: 0; merge/wdrożenie: 0.
- Odtwarzanie: `python -B -m multimodel_v2.artifact_audit --help`. CLI przyjmuje ZIP, odpowiedzi run/artifacts, capture Google, datę startu/as_of i nowy katalog PDF. Wypisuje JSON, nie pobiera źródeł i nie nadpisuje wyników. Hashe każdego członka ZIP i PDF, pokrycie oraz 1:1 są w raporcie dowodowym.
- Istniejący draft PR #55 pozostaje ścieżką przeglądu. Pełny shadow i dostarczenie kompletnych raportów nadal SOURCE_BLOCKED; rekomendacja DO_NOT_DEPLOY.

## Rejestr

2026-11-02 | E2E-001 | DST potwierdzone runtime/krokami; jawny SKIPPED bez kwalifikacji źródła | IMPLEMENTED / TESTED.
2026-11-02 | E2E-002 | Rzeczywiste 1/2 XI, brak trzeciej daty; obecne 2/3/4 XI niekompletne | CONFIRMED / OPEN.
2026-11-02 | E2E-003 | Ponowny odczyt 202/214 historycznych selekcji KB/Konsensus; brak nowego formalnego freeze | SOURCE_BLOCKED.
2026-11-02 | E2E-004 | Oba ZIP pobrane, odczytane w work, digest i 10/10 mirror API potwierdzone; Pitch 58/61 Warsaw | INSPECTED; shadow BLOCKED.
2026-11-02 | E2E-005 | Rozdzielone kohorty, obce gotowe rozliczenia odrzucone; trzy kontrolne A5 i hashe dostępności, bez potwierdzenia odbiorcy | TESTED / DELIVERY_INCOMPLETE.
2026-11-02 | E2E-006 | 28/20 i zero różnic/niezgodności freeze; bez pełnego replay matematyki bez wejść | PARTIAL_1_TO_1 / SOURCE_BLOCKED.
2026-11-02 | E2E-007 | Podejrzenie cutoff historii wydzielone od rzeczywistych 0 naruszeń czasu 48 pozycji; algorytm bez zmian | UNCONFIRMED.
2026-11-02 | E2E-008 | 806/806, v2 198/198, 57 nowych testów; zero zmian chronionych plików i zero płatnych skanów/merge | TESTED / DO_NOT_DEPLOY.
2026-11-02 | E2E-009 | Kontekst PitchAPI po oryginalnym freeze API: matcher/replay kontroluje wspólny cutoff, 2/9 tożsamości i 0/9 wejść dostępnych wtedy; negatywny test czasowy | FIXED IN ISOLATION / bez wdrożenia.

## Lista zmienionych plików w tym audycie

Aktualizacja 2026-11-03: zadania naprawcze 1–4 zaimplementowano w izolacji.
Pełny stan kodu, nowe kontrole i źródła są opisane w [raporcie napraw](MULTIMODEL_V2_REPAIR_1_4_REPORT_2026-11-03.md).
Regresja po naprawach: 995/995, v2 387/387; 189 nowych testów. Na tych samych
zamrożonych wejściach 28/20 brak różnic. Rzeczywiste źródła pozostają
SOURCE_BLOCKED; pierwotne wyniki audytu powyżej zachowano jako migawkę 2 XI.
Nie zastosowano propozycji workflow i nie uruchomiono skanów.

- `docs/MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.json`
- `docs/MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.md`
- `docs/MULTIMODEL_V2_CODEX_PLAN.md`
- `docs/MULTIMODEL_V2_E2E_AUDIT_2026-11-02.md`
- `docs/MULTIMODEL_V2_E2E_EVIDENCE_2026-11-02.json`
- `docs/MULTIMODEL_V2_SOURCES.md`
- `multimodel_v2/adapters.py`
- `multimodel_v2/artifact_audit.py`
- `multimodel_v2/audit.py`
- `multimodel_v2/git_publication.py`
- `multimodel_v2/history.py`
- `multimodel_v2/report_pdf.py`
- `multimodel_v2/shadow.py`
- `multimodel_v2/source_audit.py`
- `multimodel_v2/source_manifest.py`
- `tests/test_multimodel_v2_artifact_audit.py`
- `tests/test_multimodel_v2_source_blockers.py`
