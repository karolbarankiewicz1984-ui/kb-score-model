# MULTIMODEL v2 — oryginalne publikacje KB21 i Konsensusu na przyszłość

Status kodu: izolowany kontrakt i zapis forward-only. Nie wdrożono producenta
źródłowych prognoz i nie włączono żadnego płatnego kolektora. Istniejące modele,
arkusze, oficjalne TOP, archiwa i N pozostają bez zmian.

## Zapisana historia a aktualny formalny freeze

`formal_freeze.inspect_historical_register` odczytuje dokładnie istniejący format
Google capture przez dotychczasowy adapter. Rozdziela rzeczywiste selekcje,
wiersze szablonowe i wiersze z datą źródłową bieżącego raportu. Zwraca
SOURCE_BLOCKED oraz konkretne brakujące pola. Nie zamienia ID arkusza w fixture
ID, kolumny Date w potwierdzoną datę wydarzenia Konsensusu ani Analysis Time
w kickoff/czas publikacji. Oryginalne wartości P, kursów, ocen i decyzji są
zachowane; żaden historyczny wiersz nie zostaje nową prognozą lub N.

Przejrzane mechanizmy natywne obejmują historyczny odzysk Google,
`kb21_analyst_assessment.py`, `kb21_market_review.py`, Calendar Gate i diagnostyczne
archiwa. Sam wynik DIAGNOSTIC / NO PLAY i historyczny rejestr nie są formalną
publikacją. Nie podłączono ich jako fałszywego aktualnego freeze.

## Nowy formalny kontrakt

Wersja `multimodel-v2-formal-freeze-v1` wymaga istniejących danych od
autentycznego natywnego producenta. Walidator nigdy nie wylicza brakujących
wartości. KB21 i Konsensus mają oddzielne `system` i niezależne publikacje.

| Pole | Znaczenie i reguła |
| --- | --- |
| schema | Dosłownie multimodel-v2-formal-freeze-v1 |
| system | kb21 albo consensus; bez automatycznego przypisywania systemu |
| date | Potwierdzona data wydarzeń YYYY-MM-DD w Europe/Warsaw |
| complete / selection_count | Jawne true i dokładna liczba wszystkich picks. Niekompletny zbiór nie staje się kompletnym zerem |
| publication.id | Oryginalny ID nadany wcześniej przez natywnego producenta; walidator/zapis go nie tworzy |
| publication.captured_at_utc | Oryginalny czas ostatecznego freeze wyboru i notowania, z offsetem |
| publication.published_at_utc | Oryginalny czas publikacji, z offsetem; capture <= publikacja <= cutoff |
| publication.provenance | live_pre_match |
| publication.source_reference | Oryginalne, trwałe odniesienie do natywnej publikacji/revizji |
| picks | Uporządkowane oryginalne selekcje. Nie są filtrowane lub przeliczane |
| picks[].native_selection_id | Oryginalny ID pozycji, nigdy indeks eksportu lub hash |
| picks[].event_date / fixture_id / kickoff | Jawna natywna data, identyfikator wydarzenia i dokładny kickoff z offsetem |
| picks[].home / away / home_id / away_id | Oryginalne drużyny i ich identyfikatory. Team market musi wskazywać jedną z tych drużyn |
| picks[].fixture_source_reference | Oryginalne odniesienie do źródła mapowania fixture i drużyn |
| picks[].market_identity | fixture_id, market, market_scope, team_id, direction, dokładna line, settlement_period; zgodnie z source_manifest |
| picks[].frozen_quote | Jawne market_identity, bookmaker, selected_odd, provider_updated_at i oryginalne source_reference |
| picks[].status | Zachowana natywna decyzja/status; nie nowy KB PLAY |
| Pozostałe natywne wartości | Zachowane bez zmian; P, wynik Sport Score i ocena API nie są wzajemnie przeliczane |

Tożsamość w quote musi być dostarczona niezależnie jako oryginalny dowód;
nie wolno skopiować market_identity kandydatury do pustego quote. Natywny
quote ID, jeżeli istnieje, może pozostać dodatkowym polem; funkcja go nie tworzy.
Weryfikowane jest provider_updated_at <= capture <= publikacja < kickoff,
data Warsaw i dokładne dopasowanie rynku/fixture. Powtórzone native_selection_id,
exact market lub sprzeczne fakty wydarzenia blokują cały freeze.

Źródłowy wcześniejszy freeze P(model) może pozostać osobnym oryginalnym polem.
`publication.captured_at_utc` dotyczy końcowej publikacji selekcji/notowania;
nie zmienia natywnej kolejności pre-market assessment -> market review.

## Czas raportu i audyt historyczny

`verify_formal_freeze(capture, report_date=..., as_of=..., report_cutoff=...)`
zwraca READY tylko dla całego kompletnego i poprawnego dostarczonego kontraktu.
Capture musi zawierać niepusty `locator` oraz `capture_sha256` z dokładnie
64 małych cyfr hex. Brak lub błędny wrapper daje SOURCE_BLOCKED z polami
capture.locator/capture.capture_sha256 i odrębnymi odrzuceniami; walidacja
natywnego dokumentu nadal zwraca jego własne brakujące pola. `load_json`
tworzy taki wrapper z rzeczywiście odczytanych bajtów. Sam przekazany dict
payload nie jest wystarczającym kompletnym dowodem źródłowym.
Domyślny cutoff to 11:30 Europe/Warsaw w dacie wydarzenia; uwzględnia DST.
Można podać wcześniejszy globalny cutoff wydania D także dla wydarzeń D+1/D+2.
Nie można przedłużyć cutoffu po 11:30 daty wydarzenia.

READY oznacza weryfikację pól i czasu oryginalnego źródła, nie nowe
uprawnienie do PLAY/Calendar Gate i nie samodzielne potwierdzenie autentyczności
wydawcy. Kolektor musi pozyskać source_reference z autoryzowanego natywnego
źródła i zachować jego oryginalne bajty/rewizję. Hash identyfikuje kopię, nie
zastępuje oryginalnego ID ani uwierzytelnienia źródła.

Autentyczny historyczny freeze można przeczytać po kickoffie do replay:
status może być READY, ale current_ready i eligible_for_current_report są wtedy
false. Weryfikator zawsze zwraca eligible_as_new_prematch=false i n_effect=0.

## Rzeczywisty zapis wyłącznie na przyszłość

`record_forward_freeze(payload, output_dir)` przyjmuje istniejącą publikację
natywną. Nie ma funkcji tworzącej model, wybór, kurs lub natywny ID. Domyślny
zegar pochodzi z UTC systemu kolektora; CLI nie ma opcji cofnięcia zegara.
Oryginalna publikacja musi być świeża (do 60 sekund), capture nie starszy niż
300 sekund, wszystkie kickoffy przyszłe, a raportowy cutoff spełniony.
To ograniczenia transportu zapisu, nie zmiana progów lub algorytmu modelu.

Wynik to jeden atomowo publikowany plik receipt poza całym checkout repo:
`<output>/<system>/<event_date>/<hash-native-id>.json`. Hash jest wyłącznie
bezpiecznym adresem pliku. Oryginalny publication.id pozostaje niezmieniony
w native_freeze i native_publication_id. Receipt przechowuje nienaruszony
native_freeze, digest, rzeczywisty czas zapisu i n_effect=0. Wyłączny hard-link
publikuje gotowy, fsyncowany plik; replay tego samego ID w tej samej dacie
lub inna treść pod tym ID nie nadpisuje istniejącego pliku. Wyjścia w repo,
ucieczki przez symlink i zbyt duże dokumenty są odrzucane.

`read_forward_freeze` sprawdza digest oraz zgodność oryginalnego ID i odczytuje
wewnętrzny kontrakt bez przypisywania mu nowego czasu freeze. Odczyt wymaga
zwykłego pliku bez symlinka, sprawdza rozmiar przed załadowaniem i ogranicza
liczbę odczytanych bajtów do limitu. Receipt zawiera też efektywny report_cutoff;
reader ponownie sprawdza natywny kontrakt i świeżość względem oryginalnego
recorded_at_utc, zamiast bezwarunkowo ufać zmodyfikowanemu czasowi receipt.
Zapisany stary
oryginał nadal można wczytać, ale nie można wykonać nowego zapisu forward-only
na podstawie danych utworzonych wstecz.

## Izolowany workflow bez zmiany produkcji

1. Autoryzowany natywny producent kończy rzeczywisty assessment i istniejące
   kontrole publikacji. Udostępnia własny ID, oryginalne pola i czas.
2. Odczytujący kolektor pobiera tę rzeczywistą publikację i jej źródła. Nie
   uruchamia nowych płatnych skanów i nie wpisuje nic do Rejestru/Selections.
3. Waliduje dokument, a następnie natychmiast zapisuje forward-only do
   prywatnego RUNNER_TEMP lub innego nowego katalogu poza checkout.
4. Osobny izolowany artifact może przechować ten receipt i oryginalne dowody.
   Raport D/D+1/D+2 odczytuje je ze wspólnym report_cutoff. Brak źródła zwraca
   SOURCE_BLOCKED, bez rekonstrukcji prognozy i bez zmiany liczników.

CLI:

```bash
python -B -m multimodel_v2.formal_freeze inspect-register --help
python -B -m multimodel_v2.formal_freeze verify --help
python -B -m multimodel_v2.formal_freeze record --help
```

CLI verify/inspect-register wypisują wyłącznie podsumowania i listy braków,
bez prywatnych uwag i oryginalnych wierszy. API biblioteki zachowuje oryginał
w pamięci do kontroli 1:1; raporty repozytoryjne powinny zapisywać tylko liczniki,
hashe i brakujące pola.

Nie zainstalowano nowego workflow produkcyjnego. Włączenie rzeczywistego
producenta i izolowanego transportu wymaga wyboru autoryzowanego źródła,
uprawnienia Google read-only, jeżeli jest używane, oraz uprawnień GitHub do
osobnego artifact. Sam walidator i lokalny zapis nie wymagają kluczy API.
Obecne rejestry bez formalnych publikacji pozostają SOURCE_BLOCKED.
