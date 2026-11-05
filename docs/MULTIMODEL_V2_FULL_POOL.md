# MULTIMODEL v2 — opcjonalny, niezmienny eksport pełnego tła API

Naprawa 3 z `MULTIMODEL_V2_CODEX_REPAIR_1_4.md`. Moduł
`multimodel_v2/full_pool.py` działa poza produkcyjnymi modelami i kolektorami.
Nie wykonuje wywołań sieciowych, nie skanuje API, nie modyfikuje progów,
oryginalnych prognoz, TOP, archiwów ani N.

## Co usuwa poprawka

Dotychczasowy workflow eksperymentalny zapisywał tylko wyfiltrowane pozycje,
liczniki odrzuceń i `audit_input`. Dla runu 41323529393 oryginalne eksporty
zawierają 28/20 pozycji przy zadeklarowanych 1473/999 kandydaturach. Tych
brakujących wierszy **nie odzyskano** i nie wyliczono z liczników.

Nowy opcjonalny punkt zbierania kopiuje cały istniejący natywny plik
`api-market-scan-v3`: `background_candidates`, `top_positions`, publikację
i wszystkie oryginalne wartości. Zachowuje również pozycje poniżej 67.
Każdy wiersz otrzymuje osobny techniczny digest w raporcie weryfikacji;
kolejność natywnego TOP pozostaje bez zmian.

## Kontrakt i rozdzielone bramy

Koperta `multimodel-v2-full-pool-v1` zawiera:

- `native_payload`: kopię natywnego JSON, ze zmianami wyłącznie w jawnie
  oznaczonych polach zawierających poświadczenia; bez dopisywania brakującego
  fixture, market, ceny, daty, quote identity lub publication ID;
- `source`: rzeczywiste `run_id`, `workflow_path`, `workflow_head_sha` oraz
  `code_checkout_sha`; SHA definicji workflow i rzeczywistego checkout nie są
  utożsamiane. `publication.code_revision` musi odpowiadać checkout;
- opcjonalne `source.raw_quote_receipts`: referencje do oryginalnych odpowiedzi
  zapisanych przez `capture.py`, z `envelope_sha256` (lub `capture_sha256`),
  `response_sha256`, `received_at` oraz opisem provider/endpoint;
- `candidate_decisions`: oryginalny zapis decyzji filtra albo świeży ślad
  wywołania niezmienionego natywnego `evaluate`, z indeksem wiersza,
  `ACCEPTED`/`REJECTED`, rzeczywistymi kodami odrzuceń, czasem, digestem
  oryginalnej konfiguracji i identyfikatorem wywołanej funkcji;
- `counts`: długość zachowanego tła i TOP, pasma zapisanych ocen oraz liczby
  zapisanych decyzji. To diagnostyka odczytu, nie nowe N;
- `preservation`: SHA-256 oryginalnego capture, kanonicznej oryginalnej treści,
  zachowanej treści, lista ścieżek redakcji i deklaracja braku syntezy pól natywnych;
- `content_sha256`, limit rozmiaru i termin retencji, sprawdzane ponownie przy odczycie.

`verification.full_pool_complete` oznacza zachowanie wszystkich wierszy
danego natywnego tła i zgodność jawnego `candidate_count`, jeśli istnieje.
Nie oznacza pokrycia całego kalendarza meczów ani gotowości finansowej.
`verification.source_eligible` osobno wymaga oryginalnych metadanych publikacji,
spójności fixture, dokładnych rynków, poprawnej historii czasu, niezależnej
tożsamości wszystkich obecnych quotes i udokumentowanych decyzji.

`verification.original_top_eligible` jest niezależną, ponownie obliczaną bramą
oryginalnego TOP. Wymaga poprawnego powiązania publikacji/runu/checkout/czasu,
jednoznacznego dopasowania każdej oryginalnej pozycji do tła, spójnych faktów
fixture i oryginalnego wybranego frozen_quote obecnego w niezależnym zbiorze
quotes tła. Brak decyzji filtra, rozbieżna deklarowana liczebność pełnego tła
lub luki odrzuconych pozycji innych fixture nie ukrywają poprawnie zachowanego
TOP. Konflikt faktów fixture użytego w TOP nadal blokuje tę bramę.
Nie wymaga dodatkowego wyboru frozen_quote na rekordzie tła ani redundantnej
kopii market_data w TOP. Nie kopiuje ich do źródła. Jawnie zapisane quote_id,
provider_quote_id, source_id i source_reference muszą zgadzać się przy wiązaniu.
Brak bramy w dostarczonej weryfikacji pozostaje fail-closed u konsumenta.

Każdy obecny quote musi mieć własne `market_identity`, bukmachera,
`selected_odd` i `provider_updated_at`. Tożsamość nie jest kopiowana z kandydatury.
Wymagane: provider timestamp <= publication capture < kickoff, warszawska
data kickoffu i settlement `regulation_time`. Rozbieżny kickoff/drużyna/natywne
home_id/away_id tego samego fixture blokują źródło także pomiędzy różnymi rynkami.

Jawne `market_data.quotes=[]` wraz z ważną oryginalną decyzją REJECTED
pozostaje znanym brakiem oferty. Brak klucza quotes lub wartość None jest
inną sytuacją i nie staje się dowodem braku oferty. Pozycje odrzucone bez ceny
zostają w zachowanym pełnym tle. Do natywnego wybranego TOP wymagany jest
oryginalny `frozen_quote` zgodny z jednym z zachowanych quotes. Nie wybiera się
nowej ceny z innych bukmacherów. Dalsze finansowe bramy kohort pozostają
w module rozliczeń; COMPLETE eksportu nie zatwierdza samodzielnie ROI.

Referencja do surowej odpowiedzi potwierdza zachowanie materiału źródłowego,
nie interpretuje automatycznie provider bet ID jako rynku. Integracja musi
zweryfikować referencje przez `capture.read_provider_capture`; oryginalny
quote musi nadal posiadać niezależnie ustaloną tożsamość. Digests sprawdzają
integralność otrzymanych danych, nie są podpisem dostawcy.

## Dwa tryby bez tworzenia prognoz wstecz

`build_full_pool(capture, source, recorded_at=..., mode="copy_original")`
tworzy wyłącznie nową kopię już istniejącego oryginału. Historyczny plik można
odczytać po meczu, zachowując jego rzeczywisty czas publikacji. Nie wolno
dołożyć nowo obliczonego śladu decyzji do takiego historycznego importu.
Brakujące oryginalne decyzje/quotes pozostają brakujące i dają INCOMPLETE.

`capture_full_pool(capture, source, recorded_at=..., evaluator=...,
decision_config=...)` jest punktem integracji dla **przyszłego** zbierania.
Wywołuje dostarczony niezmieniony czysty filtr dla każdego zachowanego wiersza,
z kopiami oryginalnej konfiguracji i danych. Zapisuje zwrócony oryginalny kod
odrzucenia; nie wylicza nowych ocen, kursów lub TOP. Klasyfikacja dotyczy
tego filtra, np. playable API, i nie zastępuje natywnego TOP.

Przed uruchomieniem callbacku i ponownie przed zbudowaniem eksportu działa
zaufany zegar kolektora: domyślnie `datetime.now(UTC)`. Zarówno natywna
publikacja, jak i `recorded_at`, muszą pochodzić z poprzednich 300 sekund,
a wszystkie kickoffy nadal być przyszłe. Sfałszowanie `recorded_at` tak,
aby pasowało do starego pliku, nie omija zegara. Testy wstrzykują stały
zegar przez `clock`; produkcyjna integracja używa rzeczywistego zegara.
Callback, który kończy się po kickoffie, nie publikuje prematch.

Przyszła opcjonalna integracja po zapisaniu natywnej publikacji, przed utratą
pełnego tła na runnerze (fragment nie został dodany do płatnego workflow):

```python
from datetime import datetime, timezone
from multimodel_v2.adapters import load_json
from multimodel_v2.full_pool import capture_full_pool, write_full_pool

# original_evaluate i original_cfg pochodzą z faktycznie wybranego checkout
# skanera. native_publication_file to już zapisany rzeczywisty wynik tego skanu.
native_capture = load_json(native_publication_file)
export = capture_full_pool(
    native_capture, actual_run_and_checkout_metadata,
    recorded_at=datetime.now(timezone.utc).isoformat(),
    evaluator=original_evaluate, decision_config=original_cfg,
)
path = write_full_pool(export, isolated_export_root)
```

Włączenie fragmentu do przyszłego kolektora wymaga osobnej kontroli
wdrożeniowej. Nie zmienia się konfiguracji scoringu, funkcji natywnego filtra
ani dotychczasowego workflow. Brak działającego producenta native quote
identity nie jest naprawiany przez przepisywanie tożsamości kandydatury.

## Przechowywanie i odczyt

`write_full_pool` publikuje raz w nowym katalogu `root/YYYY-MM-DD/native-id.json`.
Jeżeli brak bezpiecznego natywnego ID, techniczna nazwa `unidentified-<digest>`
nie staje się publication ID i źródło pozostaje niekompletne. Atomowy hardlink
odmawia nadpisania istniejącego pliku. Zabroniony jest cały checkout repo
(również docs/work) oraz symlink w partycji daty. Wyniki zapisuje się wyłącznie
poza checkoutem. Nie zmienia się praw ani plików oryginału.

Domyślny limit to 16 MiB (konfigurowalny do 64 MiB); retencja 30 dni,
dozwolone 1–90 dni. `read_full_pool(path, as_of=...)` sprawdza digest,
liczniki, datę, dostępność i expiry oraz ponownie oblicza bramy źródłowe.
Nie ufa zapisanemu COMPLETE. Expiry blokuje użycie kopii, ale nie usuwa jej
ani oryginalnego archiwum. Nie ma automatycznego kasowania historii.

Znane pola API keys, Authorization/Bearer, tokeny, hasła i ich warianty
providerów są redagowane również w tekstach diagnostycznych/URL. Opcjonalne
`secret_values` pozwala podać znane ciągi do redakcji bez odczytu sekretów
przez moduł. Usunięte wartości nie trafiają do logów ani wyjątków. Pozostałe
wartości modeli, native IDs, ceny i kolejność pozostają niezmienione.

## Sprawdzenie na oryginalnych danych i testy

Oryginalny plik 29 X `161916070596-866b43bbe577eccc.json`: zachowano 222/222
wiersze i TOP 51/51, w tym 171 zapisanych ocen poniżej 67. Pool jest zachowany,
ale eksport nadal INCOMPLETE: oryginalne quotes nie mają niezależnej tożsamości,
brakuje śladu per-row decyzji i natywnego frozen_quote wybranego TOP.
Nie dopisano ich. Eksportów wyłącznie filtered 1473/999 nie akceptuje się jako tła.

Testy: `python -B -m unittest tests.test_multimodel_v2_full_pool` — 42 testy,
w tym forged-old capture, callback po kickoff, spójność fixture, jawne quotes=[],
immutability, retencja/rozmiar, podmienione ceny/liczniki, niezależne SHA
checkout/workflow i redakcja sekretów. Żaden test nie uruchamia provider API.
