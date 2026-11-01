# MULTIMODEL v2 — kontrakt źródeł i filtr obserwacyjny

Data: 2026-11-01. Gałąź: `codex/multimodel-v2`. Status: izolowana implementacja
zadań 1–3, bez wdrożenia do raportu 11:30 i bez zmian produkcyjnych.

## Użycie

Python 3.11+; wyłącznie biblioteka standardowa. Moduły nie wykonują połączeń
sieciowych, zapisów plików, zmian prognoz, TOP, freeze ani liczników N.

```python
from multimodel_v2.source_manifest import build_source_manifest
from multimodel_v2.fouls_under import fouls_under_watchlist

manifest = build_source_manifest(day, runs, snapshots, as_of=cutoff_utc)
watchlist = fouls_under_watchlist(day, runs, snapshots, as_of=cutoff_utc)
```

`day` to lokalna data `YYYY-MM-DD` w Europe/Warsaw. `cutoff_utc` to rzeczywisty
czas oceny z jawnym offsetem, np. ISO 8601 z `Z`. Kod nie pobiera bieżącego czasu,
więc audyt można odtworzyć. Przy bieżącym użyciu nie wolno cofać `as_of` w celu
odtworzenia rzekomej prognozy. Manifest może opisywać autentyczny historyczny
freeze; filtr nie emituje obserwacji, gdy `as_of >= kickoff`.

## Wejścia i granica weryfikacji

`runs` i `snapshots` są listami słowników odczytanych z oryginalnych metadanych
i artefaktów. To kontrakt normalizacji dowodów, nie automatyczny kolektor GitHub
ani adapter Google Sheets. Funkcja sprawdza spójność dostarczonych dowodów;
nie uwierzytelnia ich pochodzenia przez API ani nie weryfikuje podpisu/hashu pliku.
Za pobranie rzeczywistych plików z danego runu odpowiada wywołujący.

Każdy element `runs` zawiera:

| Pole | Wymagane źródło/znaczenie |
| --- | --- |
| `id`, `status`, `conclusion`, `head_sha`, `path` | Metadane GitHub Actions; wymagane `completed` i `success`, pełny SHA oraz workflow skanu API |
| `run_started_at`, `updated_at` | Jawnie strefowe czasy runu; `updated_at` jest konserwatywną granicą dostępności ukończonego runu |
| `artifacts` | Lista `{name, expired}` z tego runu; akceptowane tylko `expired: false`; nazwy muszą być jednoznaczne |
| `artifacts[].workflow_run` | Jeżeli obecne w metadanych GitHub, `id` i `head_sha` muszą pasować do runu |
| `date_statuses` | Lista `{date, status, artifact_name}` odczytana z datowanych statusów artefaktu; wymagany dokładnie jeden `status: "ok"` dla danej daty |

Dozwolone `path`: `.github/workflows/api-market-scan.yml` oraz
`.github/workflows/api-market-multiday-experiment.yml`. Sukces closing snapshot
nie stanowi dowodu skanu. `head_sha` identyfikuje run GitHub; nie dowodzi SHA
faktycznie wykonanych plików po dodatkowym checkout innej gałęzi w workflow.
Tę różnicę trzeba zachować przy późniejszym porównaniu shadow.

Każdy element `snapshots` zawiera:

| Pole | Znaczenie |
| --- | --- |
| `date` | Oryginalna data lokalna skanu; nie jest wyprowadzana z nazwy pliku |
| `run_id`, `head_sha`, `artifact_name` | Powiązanie z runem i jego dostępnym artefaktem |
| `generated_at_utc` | Oryginalny czas zamrożenia ocen i danych kandydatur; nie wolno podmienić go na wcześniejszy czas notowania |
| `background_candidates` | Pełna lista kandydatur, również poniżej 67; jawna pusta lista oznacza pusty skan, brak pola oznacza brak źródła |

Każda kandydatura ma `fixture_id`, `home`, `away`, `kickoff`, `market`,
`market_scope`, `team_id`, `direction`, `line`, `settlement_period`,
`final_assessment_pct` oraz `market_data.quotes`.

Tożsamość rynku to dokładnie `fixture_id`, `market`, `market_scope`, `team_id`,
`direction`, `line`, `settlement_period`. `market_scope` musi być `team` albo
`match`; drużyna jest wymagana dla `team`, a dla `match` musi być pusta (`null`).
Nie ma domyślnej strony, zakresu ani okresu rozliczenia. Linie są porównywane
dziesiętnie: `13.5 == 13.50`, ale `13.5 != 13.50000001`.

Każdy kurs ma `bookmaker`, `selected_odd`, `provider_updated_at` oraz osobny
słownik `market_identity` z powyższymi siedmioma polami. Jeżeli podano dodatkowe
`direction` lub cenę `under_odd`/`over_odd` dla wybranej strony, muszą być zgodne.
Tożsamość kursu trzeba potwierdzić z oryginalnego notowania tego samego rynku;
nie wolno po prostu skopiować jej z kandydatury. Starsze pliki bez tych dowodów
są odrzucane. Nie dopisujemy pól do archiwów i nie rekonstruujemy brakujących
cen, czasu ani ocen.

## Bramy i wynik

- `run_started_at <= generated_at_utc <= updated_at <= as_of`.
- `provider_updated_at <= generated_at_utc < kickoff`; również kurs musi być
  ściśle przed kickoffem. Czasy bez offsetu są odrzucane.
- Data kickoffu po konwersji do Europe/Warsaw musi być datą raportu. Run
  rozpoczęty po tej lokalnej dacie nie może jej retrospektywnie pokryć.
- Ukończony run bez datowanego statusu, dostępnego artefaktu lub snapshotu nie
  pokrywa dnia. Dwudniowy skan nie zapewnia automatycznie trzeciej daty.
- Powtórzona dokładna tożsamość fixture/rynek w jednym snapshotcie jest
  odrzucana. Różne rynki tego samego fixture są dozwolone. Sprzeczne drużyny
  albo kickoffy blokują fixture, także pomiędzy snapshotami.
- Reruny nie dublują pozycji: zachowywany jest najwcześniejszy zweryfikowany
  freeze dla tożsamości rynku. Sprzeczne kopie tego samego freeze są odrzucane.

Manifest zwraca `status: covered` wyłącznie przy poprawnym runie i datowanym
snapshotcie; w pozostałych przypadkach `blocked`. `covered` opisuje pokrycie
źródeł, nie rekomendację ani gwarancję istnienia poprawnych kandydatur.
`sources` podaje run, conclusion, SHA, nazwy artefaktów, czas snapshotu i datę;
`records` zawiera zweryfikowane rynki, kickoff i kursy, a `rejections` jawne kody
odrzuceń. Ocena API jest zachowana jako liczba dziesiętna zapisana tekstem;
brakująca lub niepoprawna ocena to `null`, nigdy wyliczona wartość zastępcza.

Filtr przyjmuje wyłącznie `fouls`, `under`, `regulation_time` (90 minut wraz
z doliczonym czasem, bez dogrywki), scope team/match i rzeczywisty kurs z
domkniętego przedziału 1.50–2.00. Wybiera najlepszy zweryfikowany kurs w tym
przedziale dla każdej dokładnej tożsamości; pozostałe linie tego samego meczu
pozostają skorelowanymi obserwacjami, nie niezależnym N. Każdy wpis zawiera
konkretną linię, drużynę/cały mecz, bukmachera, cenę, czas notowania, kickoff,
ocenę API i źródło.

- Ocena poniżej 67: `EKSPERYMENT/POZA PROGIEM/NIE PLAY`.
- Ocena od 67: `OBSERWUJ`.
- Brak kompletnych kandydatur: `BRAK ZWERYFIKOWANYCH KANDYDATUR`.

Ocena /100 nie jest P(HIT). Filtr nie oblicza P(model), EV ani ROI i nie
awansuje żadnej pozycji do oficjalnego TOP.

## Walidacja

```bash
python -B -m unittest discover -s tests -p 'test_multimodel_v2_provenance.py' -v
python -B -m unittest discover -s tests
git diff --check
```

Testy używają wyłącznie danych testowych, bez sieci, kluczy i zapisu obserwacji.
Nie potwierdzają dostępności bieżących prognoz KB/Konsensusu, oferty STS/Superbet
ani przyczyny awarii runu 41213715025. Dodatkowy kontrakt zadań 4–5 opisuje
[MULTIMODEL_V2_AUDIT_PDF.md](MULTIMODEL_V2_AUDIT_PDF.md). Zadanie 6 i produkcyjna
integracja pozostają otwarte.

Etap 6 dodaje adaptery natywnych źródeł i raport zgodności. Odczyt działa,
lecz pełny shadow pozostaje zablokowany przez rzeczywiste braki danych;
patrz [raport etapu 6](MULTIMODEL_V2_STAGE6_REPORT_2026-11-01.md).
