# Kontrolowana integracja MULTIMODEL v2 — 2026-11-03

**Kod: przetestowany offline, niewdrożony. Rzeczywiste źródła: SOURCE_BLOCKED.
Pełny shadow: nie wykonany, nie PASS.**

Praca wyłącznie na `codex/multimodel-v2`; aktywną gałąź potwierdzono przed
zmianami. Start `2dddeae`, następnie fast-forward do czterech nowych commitów
operatora kończących się `4d8e1f0`. Commit integracyjny
`8903506f36e607c269ba89c623a06837b938dd61` jest wypchnięty na tę samą gałąź.
Commit zawierający ten raport zapisuje końcowe dowody. Bez merge do main.
Końcowa korekta formatowania kontekstu provenance.patch nie zmienia jego treści;
ponowione 2/2 testy zastosowania propozycji i kontrola whitespace całego zakresu OK.

## Co wykonano

| Zakres | Poprawka | Gotowość kodu / rzeczywistych danych |
| --- | --- | --- |
| Pełna pula i raw | `producer.py` obserwuje istniejące api_get i oryginalny archive_publication, zachowuje zwroty/wyjątki/ID, całą pulę, oryginalny TOP, raw i decyzje niezmienionego filtra; immutable output poza checkoutami | Offline PASS; aktywny workflow i producent bez zmian |
| Trzy daty i upload | `bundle.py`: statusy/etapy/raw/pool/output, hashes/retencja/sekrety/cutoff i oddzielne SHA; opt-in upload oraz ponowne sprawdzenie rzeczywistych bajtów ZIP przez konsumenta tej samej rewizji | Techniczny CAPTURE_COMPLETE; source_ready=false dla badanego native profilu |
| Formalny forward freeze | `publication_bridge.py`: callback po autentycznej publikacji, oryginalne source_reference/IDs, świeżość; brak wpływu na zwrot producenta | DISABLED; autentycznych publisherów nie znaleziono. Nie podłączono modułów badawczych jako KB2.1 |
| Native settlement | `outcome_bridge.py` i rozszerzenie izolowanego `settlement.py`: ten sam ID/rynek/wybrany quote, oryginalne final/statistics receipts i native actual/hit, jawny final_observed_at zamiast fikcyjnego finished_at | Offline PASS; niekompletne oryginalne obserwacje pozostają odrzucone, ROI null |
| Propozycje produkcyjne | Oddzielne bootstrap, upload i native provenance patche, sprawdzone w scratch, shell przez bash -n | Niezastosowane, do przeglądu; nie ustawiono zmiennych repozytorium i nie wykonano uploadu |

Instrukcja: [kontrakt producenta i propozycje](MULTIMODEL_V2_PRODUCER_INTEGRATION.md).
Pełna lista plików i dowody: [JSON](MULTIMODEL_V2_ROLLOUT_REPORT_2026-11-03.json).

## Wynik 1:1 i testów

**1026/1026 testów OK**, w tym **418 MULTIMODEL v2**. Baza 995, trzy nowe
testy dostarczone w commitach operatora i **28 nowych testów rollout**.
Pełna regresja po synchronizacji: Python 3.12.14, aktualne izolowane zależności
PDF. Zawiera dotychczasowe DST/cutoff, trzy niezależne audyty/ROI, ochronę N,
walidację A5/fontów/paginacji dwoma parserami i przypadki błędnych PDF.

Nowy test wykonuje niezmieniony rzeczywisty kod producenta z
`experiment/api-market-2-playable-odds` na SHA `12ebe32220d04b7488889b2c7c4384ff47eb9d2e`.
16 plików kodu/konfiguracji ma identyczne SHA256 i Git blob IDs. Zapisano
wyłącznie code fixture; nie zapisano w nim prognoz, odpowiedzi API ani kursów.
Wejścia unit powstają wyłącznie w katalogach tymczasowych, z zakazaną siecią.

| Pomiar na jawnych unit inputs | Przed | Po |
| --- | --- | --- |
| Daty | D/D+1/D+2 | te same trzy daty |
| Wywołania istniejącego klienta | 15 | 15, identyczne argumenty i kolejność |
| Kandydaci / TOP na każdą datę | 96 / 48 | 96 / 48, cały natywny payload identyczny |
| Wiersze poniżej 67 na każdą datę | 48 | wszystkie 48 zachowane |
| Natywny playable export i freeze | oryginały | identyczne |
| Capsule/native | — | cały payload równy oryginałowi |
| Pliki bundle | — | 63, sprawdzone przed uploadem i po ZIP |
| Wpływ na N / dodatkowe zapytania | 0 | 0 |

Te liczby są dowodem regresji na testowych wejściach, nie wynikiem prawdziwego
skanu ani nowymi prognozami. Testuje się również late capture bez retroaktywnego
trace, błędy recordera i natywnego etapu, partial/puste katalogi, obce rewizje,
brak pliku, sekrety, symlinki, retencję, cutoff, podmianę digestu, formalne braki,
niemodyfikowalność zapisu i rzeczywisty kod oryginalnego settlement.

Ponownie odczytano te same rzeczywiste frozen eksporty 1/2 XI (28/20 pozycji):
**0 różnic pól**, 0 niespójności source/adapter, kolejność oryginalnego TOP
zachowana. Hashe oryginałów i freeze zapisano w JSON. Dotychczasowa regresja
zachowania rzeczywistego native 222/TOP51 i odrzucenia 1391 obcych rozliczeń
również przechodzi. Nie połączono tych odrębnych publikacji w jedno źródło.

CI commitu integracyjnego:

- [push 41648981909 — SUCCESS, 1026 testów w logu](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/41648981909).
- [PR 41648992477 — SUCCESS, 1026 testów w logu](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/41648992477).

## Dokładne blokady i decyzja

| Priorytet / blokada | Przyczyna i dowód | Możliwe rozwiązanie | Status |
| --- | --- | --- | --- |
| P1 / native provenance | Producent zapisuje GITHUB_SHA jako code_revision mimo osobnego checkoutu experiment; recorder wykrywa native_publication_checkout_mismatch i nie przepisuje oryginału | Osobny przyszły patch metadata, nowy zatwierdzony native pin i regresja | PROPOSAL ONLY |
| P1 / exact market i frozen quote | Badany native profil nie zawiera kompletnego period/independent quote identity i pierwotnie wybranej ceny TOP; raw receipt nie jest automatycznie wybranym quote | Autentyczne źródłowe pola i zapis wyboru w chwili publikacji, bez odgadywania okresu i odtwarzania starych cen | SOURCE_BLOCKED |
| P1 / rzeczywiste trzy daty | Recorder i upload nie są aktywowane; nie zaobserwowano kompletnego rzeczywistego forward zestawu trzech dat | Po zatwierdzeniu minimalnej konfiguracji zbierać wyłącznie odpowiedzi istniejących zapytań; uwzględnić dostęp po wygaśnięciu API-Football 4 XI | G2 PENDING / DATA BLOCKED |
| P1 / native settlement | Legacy obserwacje nie mają period/final receipt/selected quote; 1391 dostępnych rekordów należy do obcych IDs | Obserwować istniejący poprawny job przez wystawiony launcher settle; przechować oba final receipts, nie pożyczać wyników innej publikacji | SOURCE_BLOCKED |
| Stan źródeł / KB i Konsensus | Brak autentycznych native publisherów; dostępne moduły KB są CANDIDATE_ONLY, DIAGNOSTIC/NO PLAY, RESEARCH_ONLY_NOT_PLAY lub UNSIGNED | Pozostawić callback wyłączony; podłączać tylko prawdziwy publisher po uzyskaniu właściwego dostępu | INACTIVE; nie blokuje samo w sobie API-only |
| P2 / raport i dostarczenie | Nowa polityka operatora wyłącza osobną sekcję/preferencje FAULE UNDER; historyczny renderer utrzymano do regresji | Przed publikacją nowych raportów podłączyć nową politykę prezentacji i zweryfikować rzeczywisty kanał odbioru | NO NEW USER REPORTS / NOT DELIVERED |

Brak potwierdzonych nowych P0. Niepotwierdzone ryzyko historycznego lookahead
z wcześniejszego audytu nie zostało uznane za fakt ani naprawione zmianą algorytmu.
PitchAPI pozostaje kontekstem. Obecność natywnego API-only jest oddzielona od
weryfikacji quote, tak jak w nowych commitach operatora. Żadna flaga obecności
źródła nie upoważnia do composite TOP ani publikacji zakładów.

**G0 i techniczny G1: PASS offline. G2: PENDING. Rzeczywiste G3/G4 i pełny
shadow: SOURCE_BLOCKED. Rekomendacja: kod do przeglądu i kontrolowanego zbierania
po zatwierdzeniu; brak gotowości do wdrożenia raportów/zakładów lub pełnego
rzeczywistego shadow 1:1.** Nie uruchomiono płatnego skanu, produkcyjnych modeli,
uploadu źródeł ani merge. Modele, wagi, progi, oryginalne forecast/freeze, archiwa,
aktywne workflow i N bez zmian względem zsynchronizowanej bazy `4d8e1f0`.

Zakres danych to wcześniej zamrożone wejścia audytowe, sprawdzony profil kodu
i nowa inwentaryzacja operatora. Nie jest to nowy globalny audyt aktualnych
źródeł ani twierdzenie o braku wszystkich nowych plików na main.

## Zmienione pliki

32 pliki w tym etapie:

- `multimodel_v2/{producer,bundle,publication_bridge,outcome_bridge,settlement}.py`.
- `tests/test_multimodel_v2_rollout.py`.
- `tests/fixtures/multimodel_v2/native_experiment/`: 16 identycznych plików kodu/konfiguracji, `source_manifest.json`, `README.md`.
- `docs/proposals/multimodel-v2-{recorder-bootstrap,full-source-upload,native-provenance}.patch`.
- `docs/MULTIMODEL_V2_{CODEX_PLAN,PRODUCER_INTEGRATION,ROLLOUT_2026-11-03,ROLLOUT_REPORT_2026-11-03}.md` i JSON raportu.

Dokładne 32 ścieżki są w `changed_files` JSON. Cztery nowe pliki operatora
dołączone przez fast-forward nie są zaliczone do powyższych zmian.
