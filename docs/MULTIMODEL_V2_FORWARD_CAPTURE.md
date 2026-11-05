# MULTIMODEL v2 — wspólny przepływ oryginalnych danych na przyszłość

Implementacja izolowana, bez uruchamiania providerów, wdrożenia, zmian progów,
modeli, archiwów i N. Dwa patche w `docs/proposals/` są wyłącznie propozycjami,
nie zmianą obowiązującego workflow.

## Co zapisuje przyszły producent

1. Po istniejącym rzeczywistym zapytaniu, przed utratą odpowiedzi, wywołuje
   `capture_provider_response` z już odebranym JSON. Funkcja nie wykonuje
   kolejnego zapytania. Zapisuje oryginalne pola odpowiedzi z jawną redakcją
   sekretów, rzeczywiste czasy transportu, natywny run ID oraz odrębne SHA
   definicji workflow i checkout kodu źródłowego.
2. Po istniejącym zapisie pełnej natywnej publikacji wywołuje
   `capture_full_pool` z rzeczywistym plikiem i niezmienionym czystym filtrem
   `evaluate(payload, cfg)` z faktycznego checkout. Natywny kod i konfiguracja
   nie są zmieniane. Hook zapisuje oryginalne decyzje per-row w czasie nowego
   wykonania; nie odtwarza historycznych powodów z liczników odrzuceń.
3. Uprawniony producent KB/Konsensusu publikuje rzeczywiste natywne freeze
   według [kontraktu formalnego](MULTIMODEL_V2_FORWARD_FREEZE.md), bez parsowania
   opisów rejestru w domniemane prognozy. `record_forward_freeze` jedynie
   utrwala dostarczoną świeżą publikację, nie generuje typów ani natywnych ID.
4. Osobny odczyt rozliczeń przekazuje oryginalny publication/prediction ID,
   exact market i oryginalny frozen_quote. Brak tych pól pozostaje UNRESOLVED,
   bez zastępowania ceną lub obserwacją innej publikacji.

Przykład wywołania po zapytaniu wykonanym przez istniejącego klienta:

```python
from multimodel_v2.capture import capture_provider_response
from multimodel_v2.full_pool import capture_full_pool, write_full_pool

# provider_response i czasy pochodzą z istniejącego wywołania klienta.
# Ten fragment nie zawiera wywołania API.
receipt_path = capture_provider_response(
    provider_response, provider="API-Football", endpoint="odds",
    requested_at=request_started, received_at=response_received,
    source=actual_run_and_checkout_metadata, output_root=isolated_bundle_root,
)
# raw quote reference: integralny digest receipt, response_sha256, received_at.
# Ścisłe powiązanie bet/fixture/team/line musi pochodzić z oryginalnej odpowiedzi.
pool = capture_full_pool(
    native_capture, actual_run_and_checkout_metadata,
    recorded_at=actual_collector_time,
    evaluator=original_native_evaluate, decision_config=original_native_config,
)
pool_path = write_full_pool(pool, isolated_bundle_root / "full_pool")
```

Nie należy wstawiać do przykładu danych historycznych i przesuwać zegara.
Produkcyjne wywołania używają zegara systemowego. Wstrzyknięcie zegara jest
zależnością testową; CLI nie oferuje cofania czasu dla publikacji.
Zmiana liczników i kolejności TOP nie jest częścią tego przepływu.

## Układ opcjonalnego artefaktu

`multimodel-v2-full-source`, zapisany poza checkout, zawiera:

```text
full_pool/YYYY-MM-DD/native-publication-id.json
raw/YYYY-MM-DD/technical-receipt-digest.json
multiday_status/YYYY-MM-DD.json  # oryginalny status daty, jeżeli dołączono
```

Statusy mogą też pochodzić z oryginalnego `api-market-multiday-experiment`
tego samego runu. Obydwa ZIP muszą mieć potwierdzone bajty, SHA i lineage.
Nie wolno łączyć statusów ani pełnych pul z innych runów. Techniczny digest
receipt/nazwa pliku nie staje się natywnym ID prognozy lub quote.

Raw JSON to dowód odpowiedzi, nie automatyczny dowód canonical market identity.
Jeśli oryginalny dekoder nie zachował niezależnego bet/line/team/scope/period,
pool pozostaje INCOMPLETE. Nie kopiuje się parent identity do quote jako dowodu.
Nie ma tu odzysku brakujących 1473/999 historycznych wierszy.

## Zapis, sekrety i retencja

- Receipt: do 8 MiB, retencja 1–90 dni (domyślnie 30), kontrola rzeczywistego
  czasu odebrania/zapisu, exclusive atomic write. Wyłącznie obsługiwane nazwy
  providerów API-Football/PitchAPI i natywny numeryczny GitHub run ID.
- Ceny i dane źródłowe zachowuje się dosłownie. API keys, Authorization/Bearer,
  warianty nagłówków i parametrów URL są redagowane; ścieżki redakcji są jawne.
  Metadata zawierająca credential zamiast dozwolonego identyfikatora jest odrzucana.
- Full pool: osobne ograniczenia opisano w [kontrakcie puli](MULTIMODEL_V2_FULL_POOL.md).
  Zapis nie nadpisuje natywnego ID/partycji i nie usuwa oryginalnych archiwów.
- Wszystkie wyjścia operator umieszcza poza repo i chronionymi katalogami.
  Symlink uciekający z zadeklarowanej partycji jest błędem przed zapisem.

## Wspólna walidacja 1:1

`python -B -m multimodel_v2.repair_pipeline --manifest <plik.json> --start D --as-of <UTC>`
czyta istniejące ZIP i pliki, nie pobiera danych. Manifest wskazuje:

```text
run: plik odpowiedzi metadanych runu
jobs: plik odpowiedzi jobs
artifacts: lista {zip, metadata, artifact_id}
formal: {kb21: [pliki], consensus: [pliki]}
pitch: [pliki snapshotów]
checkout_sha, scheduled_date, cron_slot, event_name
job_log: opcjonalny capture oryginalnego logu
outcomes: opcjonalny plik oryginalnych rozliczeń
```

Weryfikacja ponownie sprawdza transport ZIP, zawartość członków, capsule digest,
retencję, run/commit, wszystkie trzy daty i wspólny termin 11:30 Warsaw.
Formalne publikacje muszą istnieć przed oryginalnym freeze API; PitchAPI przed
najwcześniejszym użytym freeze modelu. Wymagane jest pokrycie wszystkich fixture
oryginalnej puli, z tożsamymi natywnymi drużynami/nazwami/kickoffem. Rynki
każdego modelu zachowuje się oddzielnie i weryfikuje dokładnie; nie łączy się
różnych rynków w jeden głos.

`READY_FOR_PARALLEL_TEST` oznacza gotowość wejść do zadeklarowanego replay,
nie ukończony matematyczny shadow. `full_shadow_passed` pozostaje false,
dopóki właściwe porównanie nie zostanie wykonane. Historyczny replay nie
uprawnia do publikowania nowych prognoz po kickoffie. Osobne flagi pokazują
gotowość historycznego testu i bieżącego raportu przedmeczowego.

## Co nadal wymaga działań operatora

Nie zastosowano patchy workflow. Włączenie trzech dat i opcjonalnego uploadu
wymaga osobnej decyzji wdrożeniowej. Przed ustawieniem repository variable
`MULTIMODEL_V2_FORWARD_CAPTURE=true` istniejący kolektor musi jawnie wywoływać
zweryfikowane hooki i zapisać pliki do runner.temp/multimodel-v2-sources.
Recorder v2 musi pochodzić z przypiętej, zatwierdzonej rewizji, niezależnie od
checkout źródłowego skanera. Sam upload nie utworzy brakujących danych.

Odczyt Google działa. Nowe formalne publikacje wymagają uprawnionego producenta
KB/Konsensusu i autentycznego kanału pochodzenia. Ta implementacja nie wymaga
ani nie uzyskuje uprawnień zapisu do Google. Klucze providerów potrzebne są
istniejącym kolektorom, nie temu offline'owemu audytowi. Nie uruchomiono żadnego
skanu ani workflow źródłowego, nie proszono o nowe sekrety i nie wykonano merge.
