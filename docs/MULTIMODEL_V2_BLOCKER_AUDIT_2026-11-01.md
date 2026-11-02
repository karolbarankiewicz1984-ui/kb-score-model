# MULTIMODEL v2 — audyt blokad źródłowych etapu 6

**Pełny shadow i trzy kompletne raporty: SOURCE_BLOCKED.**
Gałąź `codex/multimodel-v2`; bez merge i wdrożenia. Stan źródeł sprawdzono
2026-11-01 o **15:26 UTC / 16:26 Europe/Warsaw**. Czas odczytu nie jest czasem
prognozy. Dowody i wyniki: [raport JSON](MULTIMODEL_V2_BLOCKER_AUDIT_2026-11-01.json).
Poprzedni raport etapu 6 zachowano jako zapis wcześniejszego stanu wiedzy.

## Tabela blokad

| Blokada | Przyczyna | Możliwe rozwiązanie | Status |
| --- | --- | --- | --- |
| Pełny API Market 1–3 XI | Brak publikacji v3/TOP i pełnego freeze dla tych dat. Istnieją dwie surowe nakładki tylko dla 1 XI: 3023 i 1955 rekordów, bez zapisanych cen bukmacherskich, ocen v3 i TOP | Odczytać istniejący oryginalny v3/freeze, jeśli zostanie odnaleziony. Nowy adapter obsługuje nakładki bez promowania ich do prognozy. Dla przyszłych dat oczekiwać zwykłego procesu źródłowego | SOURCE_BLOCKED |
| Zielony multi-day `41317765320` | Skan/upload pominięte. Runtime notice potwierdza przeciwny slot DST `0 8 * * *`; w listopadzie 10:00 Warsaw to 09:00 UTC | Klasyfikator sprawdza faktyczne kroki. Nie zmieniać prawidłowej osłony DST; szukać rzeczywiście wykonanego właściwego slotu | Diagnoza potwierdzona; brak nowych danych |
| Failure multi-day `41213715025` | runner_id=0, puste steps, brak artefaktów, log 404 BlobNotFound. Są 2 adnotacje, ale endpoint ich treści nie jest obsługiwany przez konektor | Odczytać oryginalne adnotacje, jeśli będą dostępne. Nie przypisywać awarii billingowi, limitowi API, kluczowi ani kodowi bez dowodu | M2-003 BLOCKED; dokładna przyczyna nieustalona |
| Historyczne powiązanie API 222 / TOP 51 | Wcześniej brakowało właściwego runu. Ten workflow zapisuje pliki w Git, bez upload-artifact | Odnaleziono run `40910335546`, job `123576262347` i commit `67b123a2befeb6a540c467e44728d873e3f4e976`. Adapter/manifest sprawdzają blob, SHA, rodzica, czasy i log publikacji jako osobny typ git_publication | Powiązanie ODBLOKOWANE; audyt treści nadal niekompletny |
| Pełne tło multi-day 29/30 X | Eksporty runu `40906734194`: 7/22 selekcje przy deklarowanych 222/934 kandydaturach. Odrzucenia są licznikami. Produkcyjne 222/TOP 51 to inna publikacja | Odzyskać wyłącznie oryginalne rekordy tego samego wykonania, jeśli je zapisano. Nie łączyć runów ani odtwarzać rekordów z liczników | SOURCE_BLOCKED |
| Tożsamość notowań / freeze | Quotes pełnej publikacji nie mają niezależnego market_identity. Surowe nakładki mają prawdopodobieństwa, nie ceny. Eksperymentalny audit_input nie ma natywnego publication.id ani settlement_period w picks | Odczytać oryginalny provider quote z tego samego freeze. Nie kopiować tożsamości kandydatury do quote jako dowodu; hash nie staje się natywnym ID, dzisiejsza cena nie zastępuje dawnej | SOURCE_BLOCKED |
| Historia KB Score 2.1 | Dostępne 93 rewizje; sprawdzone 247/248: 202 rzeczywiste selekcje w obu, bez zmian. Wszystkie daty wydarzeń poprzedzają daty tych rewizji. Live 204 obejmowało dwa puste ID 118/119 | Adapter odzyskuje wyłącznie zapisane wartości. Wcześniejsze rewizje mogą potwierdzić wcześniejszą obecność komórek, lecz nadal wymagane kickoff, exact market i dowód freeze | Historia ODBLOKOWANA; prematch niepotwierdzony |
| Historia Konsensusu | Dostępnych 90 rewizji; sprawdzone 116/118: 211 → 214 selekcji, 3 dodane, 4 aktualizacje wyłącznie Result/Profit 1u. Date i Analysis Time nie dowodzą kickoffu/freeze | Adapter pokazuje różnice wersji bez wyboru korzystnego wariantu. Zachować zapisane P/kursy/statusy; strefa arkusza America/Los_Angeles nie udaje Warsaw | Historia ODBLOKOWANA; prematch niepotwierdzony |
| Prognozy KB/Konsensusu 1–3 XI | Brak takich wpisów w odczytanych rejestrach i najnowszych rewizjach; ostatnie daty 6 X / 14 X | Dla 1 XI wolno odnaleźć wcześniej zapisany oryginał, lecz nie stworzyć porannej prognozy wstecz. Dla 2–3 XI oczekiwać rzeczywistych publikacji przed cutoff/kickoff | SOURCE_BLOCKED; przyszłe źródła oczekiwane |
| PitchAPI 1 XI | Brak snapshotu tej daty w odczytanym drzewie. Ostatni plik 30 X. Runy prematch 30/31 X: failure; history lab nie jest nowym prematch context | Odczytać istniejący snapshot sprzed właściwego cutoffu, jeśli zapisano go w innym udokumentowanym źródle. Obserwacja po kickoff nie zastępuje starego prematch | SOURCE_BLOCKED |
| PitchAPI 2–3 XI i horyzont multi-day | Brak obu plików w tym samym drzewie; daty nadal przyszłe. Domyślne days=2 nie pokrywa 3 dat | Oczekiwać zwykłego kolektora i sprawdzić oryginalne czasy. Horyzont 3 dat wymaga osobnego testu; workflow pozostawiono bez zmian | WAITING; M2-002 OPEN |

## Faktyczna dostępność API

Lista runów 30 X–1 XI: 61/61 pozycji. Odczytany `origin/main` wskazuje
`634c890eb0ddd489693f436722177b5ea3af32ad`; main nie był wybierany ani zmieniany.
Brak plików PitchAPI `prematch/2026-11-01.json`, `02.json`, `03.json` sprawdzono
w tym drzewie (pełne nazwy dat w JSON).

- `41300832820`: raw scan wykonany, enrichment/ranking/publikacja freeze pominięte.
  Snapshot `market_snapshots/2026-11-01/111250.json`: 3023 rekordy / 31 fixture,
  captured_at `11:12:50.413176Z` = 12:12:50 Warsaw.
- `41315086777`: taki sam rozdział kroków. Snapshot `141341.json`: 1955 rekordów /
  20 fixture, captured_at `14:13:41.437788Z` = 15:13:41 Warsaw.
- `41321099659`: raw, enrichment, ranking i zapis pominięte; success nie dowodzi źródła.
- `41317765320`: osobny multi-day pominięty przez potwierdzony warunek DST.

Nakładki odczytano do katalogu roboczego. `adapt_api_overlay` kopiuje istniejące
pola i jawnie zwraca brak kursu, oceny i natywnego TOP. Nie interpretuje
market_probability_pct jako P(model) ani nie odwraca go do fikcyjnego kursu.
Oba snapshoty powstały po cutoffie 1 XI 11:30 Warsaw, więc nie uzupełniają tego wydania.

## Powiązanie historycznej publikacji API

Pełny plik `161916070596-866b43bbe577eccc.json` powiązano z własnym dziennym
runem, nigdy z multi-day. Natywna rewizja `1e7f720…` jest head SHA runu i rodzicem
commitu `67b123a…`. Bajty oryginalnego bloba `6c8a1fa6c678916bc20eac8559fc2da4d7c2d300`
zgadzają się z SHA-256 capture. Runtime summary potwierdza prediction_id i 222/51,
a log stworzenie pliku i publikację. Dawny push do main jest dowodem z 29 X,
nie operacją wykonaną w tym audycie.

`read_git_publication` uruchamia tylko `git cat-file/show/rev-parse`.
`api_evidence(..., git_receipt=...)` i manifest sprawdzają powiązanie oraz hash
znormalizowanej kopii. Zmiana ceny/linii/rekordu odrzuca snapshot. Źródło ma
typ git_publication/source_ref: nie tworzymy fikcyjnego upload-artifact,
natywnego ID, oryginalnego statusu daty ani nowych notowań.

Manifest rozpoznaje teraz istniejącą publikację, ale potwierdza **0/222**
rekordów kursowych: 760 odrzuceń niepełnej tożsamości quotes i 222 no_verified_quote.
TOP nadal ma 51 pozycji i status incomplete. Zero zweryfikowanych kwalifikujących
API nie ustala zera kandydatur; odczyt samych natywnych pól nadal daje 3.
W tej konkretnej pełnej publikacji nie ma FAULE UNDER 90 min w wymaganym paśmie.
Nie odblokowuje to pełnego shadow ani listopada. ROI pozostaje null.

## Zapisana historia arkuszy

Źródła: [KB](https://docs.google.com/spreadsheets/d/1Raay44yu5OUefV4czv4TN4Xa_SQ5K5txUUPf1WHvXUI/edit)
i [Konsensus](https://docs.google.com/spreadsheets/d/1zXMN6HIFdFT-DCAgjv4RLd38Bwq1B_-DVJKAy7jydLc/edit).
Listy rewizji są kompletne w odpowiedzi. Porównano tylko po dwie ostatnie wersje,
nie pełną historię komórek ani najwcześniejsze prognozy.

| Źródło | Poprzednia rewizja | Najnowsza rewizja | Selekcje | Różnice |
| --- | --- | --- | --- | --- |
| KB | 247, 12 X 09:30:09.722Z | 248, 14 X 09:29:27.833Z | 202 → 202 | Brak |
| Konsensus | 116, 13 X 08:36:04.786Z | 118, 14 X 08:35:50.604Z | 211 → 214 | 3 dodane; 4 aktualizacje Result i Profit 1u |

Konektor zwrócił tekstowy CSV wielu tabel mimo MIME XLSX. `history.py` obsługuje
wielowierszowe uwagi i granice tabel, weryfikuje fileId/revisionId/modifiedTime
oraz jednoznaczne nagłówki. Usuwa wyłącznie jawny techniczny indeks eksportu.
Natywne KB ID nie staje się fixture ID. Konsensus łączony jest po dokładnych
polach źródłowych; duplikaty pozostają niejednoznaczne.

Tabela KB obejmuje też wiersze szablonowe z numerami do 500. 202 to zapisane
selekcje z wydarzeniem/datą/typem; 204 z etapu 6 to niepuste wiersze bieżącego
zakresu, w tym puste ID 118/119. Nie usunięto ich z arkusza ani wcześniejszego
capture. Nie przeliczano N. Wszystkie 202 daty wydarzeń są wcześniejsze od obu rewizji.

W Konsensusie Date nie uznano za potwierdzoną datę wydarzenia, a renderowane
00:00:00 i Analysis Time nie zastępują kickoff/freeze. Adapter zwraca historical_only,
bez nowego prematch, fixture ID i czasu zamrożenia. Prywatne uwagi i dane autorów
pozostały poza repo. Istniejący odzysk 179 rekordów i skrypt produkcyjny bez zmian.

## Co można pobrać teraz

| Dane / działanie | Zasada |
| --- | --- |
| Metadane, logi, istniejące bloby, indeksy i treści rewizji | Bezpieczny odczyt teraz; pobranie nie jest nowym freeze |
| Już zapisany oryginał sprzed cutoffu i kickoffu, odnaleziony po meczu | Można odczytać do audytu; nadal wymagane pozostałe dowody. Nie powstaje nowa prognoza/N |
| Oryginał po cutoffie, ale przed kickoffem | Co najwyżej późniejsze wydanie z własnym czasem, nie uzupełnienie starego |
| Obserwacja po kickoffie | Tylko historia/kontekst/rozliczenie, nigdy brakujący prematch |
| Nieistniejąca prognoza/cena dla minionego cutoffu 1 XI | Zakaz tworzenia wstecz, liczenia z wyników i zastępowania dzisiejszą ceną |
| Przyszłe 2–3 XI | Odczytać istniejące cache lub czekać na zwykłą publikację przed cutoff/kickoff; brak nie jest jeszcze nieodwracalny |
| Wyniki końcowe | Osobne rozliczenie istniejącego freeze z exact market; nie dowód pierwotnej prognozy |
| Płatny scan lub ręczny rerun kolektora | Nie uruchomiono; polityka odrzuca płatne skany |

Czysta funkcja `recovery_policy` klasyfikuje te przypadki bez uruchamiania API/workflow.
Brak dowodu godziny pozostaje brakiem.

## Walidacja i odtwarzanie

- 41 nowych testów; MULTIMODEL v2 182/182; pełna regresja 790/790. Negatywne
  przypadki: obce SHA/runy, podmienione ceny/bloby, echo zamiast runtime,
  pominięta publikacja, błędne rewizje/duplikaty, cutoff/kickoff i brak pozornego PASS.
- Trzy kontrolne PDF 1/2/3 XI: po 3 strony A5, PyMuPDF i pypdf, osadzone
  DejaVu Sans >=7 pt, paginacja, polskie znaki, FAULE UNDER na pierwszej stronie,
  zero aktywnych linków. Na 1 XI pokazano surowe nakładki i brak rankingu/kursów.
  Pliki z brakami nie są kompletnymi prognozami; pozostały poza archiwami.
- CLI shadow przyjmuje `--api-git-proof <plik.json>` z odczytanym `{run, receipt}`
  z `read_git_publication`. JSON audytu zawiera ten dowód pod api_git_publication.
  Nie zawiera prywatnych uwag arkuszy ani pełnych logów.
- `git diff --check` i kontrola zakresu: modele, progi, konfiguracja, oryginalne
  TOP/freeze, dane, archiwa, narzędzia produkcyjne, workflow i N bez zmian.
- Aktualizacja istniejącego draft PR #55; bez merge i bez wdrożenia.
