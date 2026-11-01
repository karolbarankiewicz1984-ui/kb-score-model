# MULTIMODEL v2 — niezależne audyty i trzy PDF A5

Data: 2026-11-01. Gałąź: `codex/multimodel-v2`. Zadania 4–5.
Stan: implementacja odłączona od produkcji; bez merge do main.

## Audyty i oryginalne freeze

```python
from multimodel_v2.audit import build_audits

audits = build_audits(day, runs, snapshots, settlements, as_of=cutoff)
```

Podstawowy kontrakt `runs` i `snapshots` pozostaje opisany w
[MULTIMODEL_V2_SOURCES.md](MULTIMODEL_V2_SOURCES.md). Audyt wymaga dodatkowo
oryginalnego `snapshot.publication`: `id`, `provenance: "live_pre_match"` oraz
`captured_at_utc`. Ten ostatni czas musi przypadać pomiędzy oryginalnym czasem
snapshotu a ukończeniem runu, przed cutoffem i ściśle przed kickoffem każdej
rozliczanej pozycji. Nie dopisujemy tych danych do istniejących archiwów.

Dla daty wybierany jest najwcześniejszy zweryfikowany oryginalny freeze.
Sprzeczne kopie blokują audyt; późniejszy korzystniejszy rerun nie zastępuje
oryginału. Późniejsze snapshoty nie uzupełniają historycznego składu grup.

Każda grupa ma osobny skład, wyniki i mianownik:

| Audyt | Członkostwo ustalone bez znajomości wyników |
| --- | --- |
| `original_top` | Oryginalne `top_positions` wybranego freeze, w oryginalnej kolejności, bez ponownego progowania/rankingu |
| `qualifying_api` | Wszystkie pozycje z `background_candidates` z oryginalną oceną API >=67 i zweryfikowanym kursem dokładnego rynku >=1.20 |
| `fouls_under` | Faule/UNDER, scope team/match, 90 min, zweryfikowany kurs 1.50–2.00, również oceny poniżej 67 |

TOP nie jest rekonstruowany z tła. Brak `top_positions` to brak źródła, natomiast
jawna pusta lista to potwierdzony pusty TOP. Wadliwy oryginalny wpis pozostaje
w audycie TOP z powodem odrzucenia, bez dopisywania wyniku. Dozwolone są
oryginalne adnotacje prezentacyjne; tożsamość rynku, kickoff, drużyny i ocena
muszą odpowiadać danym źródłowym. Powiązane linie nie stają się niezależnymi N.

## Kurs do ROI i osobne wyniki

Pozycja może zawierać oryginalny `frozen_quote`, w tym samym formacie co kurs
w kontrakcie źródeł: `market_identity`, `bookmaker`, `selected_odd`,
`provider_updated_at`. Kurs musi być faktycznie zapisany w freeze i zgodny
z weryfikowalnym oryginalnym notowaniem. Dla API/fauli musi również spełniać
warunki ceny danej grupy. Brak `frozen_quote` nie jest uzupełniany najlepszą
ceną znalezioną po meczu. Wynik sportowy może być znany, a ROI niedostępne.

`settlements` to lista oddzielnych oryginalnych rozliczeń. Każde zawiera:

- `date`: lokalna data meczu;
- `market_identity`: dokładna tożsamość rynku, zakresu, strony, linii i okresu;
- `freeze`: pełne odniesienie `{id, run_id, head_sha, artifact_name, captured_at_utc}`
  do oryginalnej publikacji (funkcja `freeze_reference(snapshot)` normalizuje
  rzeczywiste metadane, nie tworzy nowego ID);
- `fixture_status: "FT"`, `finished_at` i `settled_at` z offsetami;
- `outcome`: oryginalnie rozliczone `win`, `loss`, `void` albo `push`;
- `result_source`: wskazanie rzeczywistego pliku/źródła końcowego wyniku;
- opcjonalnie `quote`, który musi odpowiadać oryginalnemu zamrożonemu kursowi.

Wymagane: `kickoff < finished_at <= settled_at <= as_of`. Niepasująca linia,
freeze, data, brak źródła, wynik LIVE, przyszły wynik albo duplikat pozostają
nierozliczone. Rozliczenia dzielone (`half_win`/`half_loss`) nie są obsługiwane
w tej wersji i nie są zamieniane na pełną wygraną lub przegraną. Wynik nie
dodaje pozycji do żadnej grupy. Kod sprawdza spójność przekazanych dowodów,
nie uwierzytelnia źródła po sieci i nie wyznacza fikcyjnych wyników.

ROI i fixture-equal ROI są liczone wyłącznie przy pełnym pokryciu grupy,
rozliczeniu wszystkich jej pozycji i komplecie oryginalnych zamrożonych cen.
Jeden brak blokuje obie miary dla całej grupy; nie wybieramy kompletnego,
korzystniejszego podzbioru. Stawka diagnostyczna to 1 jednostka na pozycję:
win = kurs − 1, loss = −1, void/push = 0; mianownik obejmuje wszystkie
zamrożone pozycje, także zwrot stawki. Fixture-equal ROI uśrednia najpierw
zysk jednostkowy w każdym meczu, następnie średnie meczów z równą wagą.
Nie są to dane o rzeczywiście postawionych stawkach, podatkach czy limitach.
Hit-rate obejmuje win/loss, bez void/push, i wymaga kompletu rozliczeń.

Brak źródeł zwraca `source_missing` i liczebności `null`, nie fikcyjną próbkę
zero. `incomplete` oznacza niepełne dowody; `rows` zachowuje znane pozycje.
Liczebności audytu są diagnostyką wejścia, bez zapisów do rejestrów N.

## Generator PDF i kontrola publikacji plików

Zależności są odseparowane w `multimodel_v2/requirements.txt`. Wymagane są
Python 3.11+, ReportLab 4, PyMuPDF, pypdf do niezależnego testu parsera oraz
pliki `DejaVuSans.ttf` i `DejaVuSans-Bold.ttf` (Ubuntu: `fonts-dejavu-core`).
Standardowa ścieżka fontów to `/usr/share/fonts/truetype/dejavu`; API pozwala
podać `font_dir`. Brak fontu przerywa generowanie, bez cichego fallbacku.

```bash
python -m pip install -r multimodel_v2/requirements.txt
python -B -m multimodel_v2.report_pdf \
  --start YYYY-MM-DD --as-of RZECZYWISTY_CUTOFF_Z_OFFSETEM \
  --evidence work/source_evidence.json --output work/multimodel-pdfs
```

Wejściowy JSON zawiera `runs`, `snapshots`, `settlements`. Pominięcie
`--evidence` oznacza jawny brak dostarczonych źródeł; generator nadal tworzy
trzy dokumenty z komunikatami o brakach, bez fikcyjnego kalendarza/typów.
Nie jest to kolektor GitHub, adapter Google Sheets ani bieżący skan modeli.
Brak eksportu KB/Konsensusu i kontekstu PitchAPI jest jawnie oznaczony.

Wyjście to dokładnie trzy osobne `MULTIMODEL_YYYY-MM-DD.pdf` dla D, D+1 i D+2
w Europe/Warsaw. Daty są dodawane kalendarzowo, również przy zmianie DST,
miesiąca i roku. Każdy PDF ma A5, osadzone DejaVu Sans, tekst co najmniej
7 pt (brama jakości odrzuca poniżej 6 pt), nagłówek z datą i `Strona X / Y`.
FAULE UNDER jest na pierwszej stronie, z maksymalnie dwiema kandydaturami
w skrócie; pełna lista dalej. Oryginalny TOP zachowuje numerację i kolejność;
pierwsze trzy pozycje na mecz są w jego części głównej, pozostałe w aneksie.
Żadna pozycja po kickoffie nie jest pokazywana jako bieżąca prognoza;
autentyczne dawne freeze mogą być opisane wyłącznie w audycie historycznym.

Generator wymaga nowego lub pustego katalogu, nie nadpisuje plików i odrzuca
ścieżki produkcyjne (`archive`, `data`, `reports`, `model`, `config`, `tools`,
`.github`, `.git`). Najpierw generuje wszystkie pliki w katalogu tymczasowym,
parsuje cały zestaw, dopiero potem atomowo udostępnia docelowy katalog.
Awaria drugiego/trzeciego PDF nie publikuje częściowego zestawu ani ścieżek
do nieistniejących plików. Tekst źródłowy jest escapowany; PDF nie zawiera
aktywnych linków. Wynik CLI podaje wyłącznie istniejące, sprawdzone pliki.

`validate_pdf_bundle(directory, start_date)` sprawdza dokładnie trzy właściwe
nazwy. `validate_pdf(path, day)` kontroluje parserem każdą stronę: A5,
paginację, datę, FAULE UNDER na pierwszej stronie, fonty i ich osadzenie,
minimum 6 pt, ramkę tekstu, polskie znaki oraz brak linków. Testy używają
także niezależnego parsera pypdf, danych wielostronicowych, celowo uszkodzonych
PDF i wymuszonych awarii. Dane testowe nie są publikowane jako rzeczywiste
prognozy lub wyniki.

```bash
python -B -m unittest discover -s tests -p 'test_multimodel_v2*.py' -v
python -B -m unittest discover -s tests
git diff --check
```

Osobny workflow `multimodel-v2-checks.yml` uruchamia wyłącznie testy, bez
sekretów, skanów, harmonogramów, zapisów danych i uprawnień zapisu. Istniejące
workflow produkcyjne pozostają bez zmian. Zadanie 6 (shadow 1:1), podłączenie
rzeczywistych eksportów i każda decyzja produkcyjna pozostają otwarte.
