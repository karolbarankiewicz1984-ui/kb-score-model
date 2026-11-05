# MULTIMODEL v2 — etap 6: integracje i porównanie rzeczywistych freeze

Gałąź: `codex/multimodel-v2`. Status: **ADAPTERY WDROŻONE W IZOLACJI; PEŁNY SHADOW I KOMPLETNE RAPORTY SOURCE_BLOCKED**.
Bez wdrożenia produkcyjnego, merge, nowych skanów API i zapisów obserwacji/N.

Odczyt arkuszy utrwalono 2026-11-01 o **13:21:45 Europe/Warsaw (12:21:45 UTC)**.
To czas dostępności kopii odczytu, nigdy zastępczy czas przedmeczowego freeze.
Wyniki maszynowe: [MULTIMODEL_V2_STAGE6_DIFFERENCES_2026-11-01.json](MULTIMODEL_V2_STAGE6_DIFFERENCES_2026-11-01.json).

## Co rzeczywiście odczytano

| Źródło | Dostępne dane | Ocena kompletności |
| --- | --- | --- |
| API Market, run `40906734194` | Run ukończony sukcesem; artefakt `api-market-multiday-experiment`, ID `12911681942`, nieprzeterminowany. Repozytoryjna kopia zawiera eksporty i `audit_input` dla 29/30 października: 7 i 22 pozycje TOP | Eksport deklaruje odpowiednio 222 i 934 kandydatury. Odrzucenia to liczniki przyczyn, nie pełne rekordy. Brak pełnego tła w tym artefakcie |
| API Market, osobny oryginalny freeze `161916070596-866b43bbe577eccc` | 222 rekordy, 2 fixture, oryginalny TOP 51 pozycji w `data/api_football/predictions/2026-10-29/` | Inny snapshot/czas/rewizja niż eksport powyższego runu. Nie połączono ich danych ani metadanych |
| KB Score 2.1 — oryginalny rejestr Google | `Rejestr!A1:AP205`, 204 wiersze danych; kontrola kolumny dat `C2:C996`; ostatnia data wydarzenia 2026-10-06 | Dane historyczne. Brak fixture ID, dokładnego kickoffu, strukturalnego exact market, bukmachera/czasu quote i dowodu freeze przed kickoffem |
| Konsensus — oryginalny rejestr Google | `Selections!A1:Z215`, 214 wierszy; kontrola dat `A2:A1000`; ostatnia data w kolumnie Date to 2026-10-14 | Brak tych samych dowodów tożsamości i czasu. Strefa arkusza to `America/Los_Angeles`: godzina Analysis Time „11:30” nie została uznana za 11:30 Warsaw ani za kickoff/freeze |
| PitchAPI prematch | Snapshot 2026-10-29: 33 rekordy, 30 przechodzi kontrolę dat/próbki; snapshot 2026-10-30: 78 rekordów, 68 przechodzi kontrolę | 98 zweryfikowanych rekordów kontekstu historycznego, nie 98 prognoz. Nie przeliczano xG, ocen ani P(model). Brak snapshotów dla 1–3 listopada |

204/214 to liczby odczytanych wierszy, **nie nowe N ani dowód nowych obserwacji**.
Oba arkusze pozostały bez zmian:

- [Oryginalne źródło KB Score](https://docs.google.com/spreadsheets/d/1Raay44yu5OUefV4czv4TN4Xa_SQ5K5txUUPf1WHvXUI/edit).
- [Oryginalne źródło Konsensusu](https://docs.google.com/spreadsheets/d/1zXMN6HIFdFT-DCAgjv4RLd38Bwq1B_-DVJKAy7jydLc/edit).

Odczytane drzewo `origin/main` wskazywało `df20c41daf3c258aa93b865e14a4116f68c1486e`.
Z tego drzewa skopiowano do `work/` wyłącznie istniejące pliki PitchAPI. Nie
wybrano main jako aktywnej gałęzi, nie zapisano nic do main ani źródłowych archiwów.

Lista runów utworzonych 1 listopada zwróciła 10 pozycji (pełna strona odpowiedzi).
Nie było w niej ukończonego poprawnego skanu multi-day pokrywającego 1–3 listopada.
Dwa udane runy Closing Snapshot (`41259795869`, `41285076744`) oraz udany
PitchAPI history lab (`41302233047`) nie są takim skanem ani nowym prematch context.
Ostatni sprawdzony multi-day `41213715025` ma conclusion `failure` i pustą listę
artefaktów. Przyczyny awarii nadal nie ustalono — M2-003 pozostaje BLOCKED.
Wyszukiwanie eksportów według dat 1–3 listopada nie wskazało właściwego nowego
artefaktu modelu; nie interpretowano wyników niezwiązanych z projektem.

Metadane i tekstowe pliki są dostępne. Bezpośrednia próba pobrania binarnego
ZIP przez CLI zakończyła się `Tunnel connection failed: 403 Forbidden` na proxy.
Użyto istniejącej repozytoryjnej kopii artefaktu. Digest ZIP odczytano z metadanych,
ale **nie zweryfikowano bajtów ZIP**; nie przedstawiamy tego jako udanego pobrania.

## Porównanie 1:1 — trzy odrębne wejścia

W każdym wierszu porównano natywny plik ze swoim wynikiem adaptera: te same
bajty wejściowe, a nie różne runy lub snapshoty. Niezależna projekcja źródła
sprawdza fixture ID, market/scope/team/direction/exact line/settlement, wszystkie
ceny i bukmacherów/czasy, statusy, oceny oraz oryginalną zawartość i kolejność TOP.
Oryginalny `audit_input` jest odczytywany osobno, nie z kopii w adapterze.

| Wejście | Rekordy | TOP | Statusy źródłowe | Różnice pól / niespójności freeze–eksport |
| --- | ---: | ---: | --- | --- |
| Multi-day 2026-10-29 | 7 → 7 | 7 → 7, kolejność zachowana | ACCEPT: 7 | 0 / 0 |
| Multi-day 2026-10-30 | 22 → 22 | 22 → 22, kolejność zachowana | ACCEPT: 22 | 0 / 0 |
| Osobny freeze API 2026-10-29 | 222 → 222 | 51 → 51, kolejność zachowana | STRONG: 19, ACCEPT: 32, BELOW_THRESHOLD: 171 | 0 / 0 |

Nie sumowano tych wejść do wspólnej próbki lub N. Normalizacja whole-match
ustawia nieaplikowalną drużynę rynku na `null`; techniczny team anchor historii
został zachowany w oryginalnym rekordzie. Nie zmienia to źródłowej prognozy.

### Audyty i różnice bram źródłowych

**Zgodność pól adaptera nie oznacza zaliczenia pełnego shadow.**

- Oryginalne pliki TOP zawierają 7/22/51 pozycji. Obecny ścisły audyt v2 zwraca
  brak zweryfikowanej pełnej linii pochodzenia, a nie nowy TOP lub próbkę zero.
- W eksportach multi-day pełne populacje kwalifikujących API i FAULE UNDER są
  nieustalone: `222/934 candidate_count` oraz liczniki odrzuceń nie odtwarzają
  brakujących rekordów ani linii poniżej 67.
- W pełnym osobnym freeze referencyjny odczyt zapisanych pól daje 3 pozycje
  spełniające score >=67 i kurs >=1.20 oraz 0 FAULE UNDER w paśmie 1.50–2.00.
  To klasyfikacja istniejących pól przed weryfikacją niezależnego pochodzenia
  kursów, nie nowa lista gry. Ścisłe audyty v2 pozostają niekompletne.
- API quotes nie zawierają osobnego niezależnego `market_identity`. Adapter
  zachowuje ceny, ale nie kopiuje do quote tożsamości kandydatury jako rzekomego
  dowodu exact line. Nie potwierdzono raw provider quote dla tego samego freeze.
- Multi-day `audit_input` zawiera prawdziwe `frozen_at_utc` i listę picks,
  lecz nie oryginalne `publication.id` wymagane przez obecny kontrakt v2,
  a same picks nie zapisują `settlement_period`. Hash pliku nie udaje brakującego
  ID oryginalnej publikacji. Jest to jawna luka kontraktu/evidence, nie stwierdzenie,
  że oryginalny plik freeze nie istnieje.
- Osobnego freeze produkcyjnego nie przypisano do runu multi-day: nie ma
  zgodnych metadanych runu/artefaktu dla tego konkretnego wejścia.
- Nie podłączono końcowych rozliczeń potwierdzonych dla tych samych freeze;
  ROI i fixture-equal ROI pozostają `null` po obu stronach. Brak wyniku nie stał
  się loss, a cena nie została dobrana po meczu.

PitchAPI dopasowano wyłącznie przy zgodności drużyn, rozgrywek i dokładnego
UTC kickoffu: 2/2 fixture 29 października i 1/8 fixture 30 października.
Pozostałych 7 nie dopasowano przez przybliżenia nazw ani okno sześciu godzin.
Identyfikatory `m_...` pozostały identyfikatorami PitchAPI. To dopasowanie
wydarzenia do kontekstu xG, nie potwierdzenie rynków rożnych/fauli ani nowy głos
modelu. Brak zweryfikowanych freeze KB/Konsensusu uniemożliwia wspólny test
czterech systemów na tych samych przedmeczowych wejściach.

## Czy trzy kompletne PDF na rzeczywistych danych są możliwe

**Nie dla D=2026-11-01, D+1=2026-11-02, D+2=2026-11-03.** Dla każdej z tych
dat lista blokad jest osobno zapisana w JSON:

1. API: brak poprawnego runu, datowanego pełnego snapshotu i oryginalnego TOP
   pokrywających daną datę; sukces closing nie wystarcza.
2. KB: brak aktualnych wierszy i potwierdzonych fixture/kickoff/exact market,
   freeze, bukmachera oraz czasu notowania. Stare rekordy nie są nowymi prognozami.
3. Konsensus: brak aktualnych wierszy i tych samych dowodów; dodatkowo nie ma
   podstaw do przeliczenia Analysis Time na czas freeze w Europe/Warsaw.
4. PitchAPI: brak prematch snapshotów dla 1–3 listopada oraz kontekstu
   jednoznacznie przypisanego do aktualnego kalendarza API.

**Technicznie wygenerowano trzy osobne PDF** `MULTIMODEL_2026-11-01/02/03.pdf`,
po 3 strony A5. Wszystkie przeszły PyMuPDF i niezależny pypdf: osadzone DejaVu
Sans, minimum 7 pt, polskie znaki, poprawna paginacja, FAULE UNDER na pierwszej
stronie, tekst w granicach strony i brak aktywnych linków. Pierwsza strona
odróżnia odczytany historyczny rejestr od braku aktualnej prognozy. Są to
dokumenty z jawnymi brakami źródeł, **nie trzy kompletne raporty prognoz**.
Nie zapisano ich do archiwów produkcyjnych ani nie zwrócono fikcyjnych linków.

## Odtwarzanie i granice adapterów

`multimodel_v2/adapters.py` czyta natywne JSON API/PitchAPI oraz capture odpowiedzi
Google Sheets: `{metadata, range, retrieved_at}`. `metadata` to wynik odczytu
metadanych pliku; `range` zawiera dokładny zakres i tablicę `values` otrzymaną
przez konektor. Pliki capture są roboczymi kopiami odczytu, nie nowym freeze.
`capture_sha256` identyfikuje bajty kopii, nie podpis ani revision ID Google.
Nie archiwizowano w repo pełnych prywatnych uwag z arkuszy.

Adapter nie parsuje opisowego „Typ/Pick” w wymyślony exact market i nie
wylicza P(model), ocen, EV, sygnałów ani wyników. Nie uruchamia sieci ani skanów.
`multimodel_v2/shadow.py` porównuje dwa odczyty tego samego capture, osobno
pokazuje różnice bram i ustala kompletność każdej z trzech dat. PDF może przyjąć
`source_bundles`, aby jawnie wykazać rzeczywiście odczytane źródła i ich braki.

```bash
python -B -m multimodel_v2.shadow \
  --archive-root archive/multimodel/api_market/runs/40906734194 \
  --run-metadata work/run.json --artifacts work/artifacts.json \
  --kb work/kb.json --consensus work/consensus.json \
  --pitchapi work/pitchapi/2026-10-29.json work/pitchapi/2026-10-30.json \
  --api-prediction data/api_football/predictions/2026-10-29/161916070596-866b43bbe577eccc.json \
  --start 2026-11-01 --as-of 2026-11-01T12:21:45Z \
  --pdf-output work/stage6-pdfs
```

`run.json` i `artifacts.json` są oryginalnymi odpowiedziami metadanych GitHub,
nie polami dopisanymi do źródłowego archiwum. Brakującego tła, kursów, metadanych
lub wyników nie uzupełniamy nowym skanem po kickoffie. Dalszy pełny shadow
wymaga oryginalnych, jednoznacznie powiązanych przedmeczowych eksportów,
pełnego background, niezależnych notowań dokładnych rynków i zgodnych rozliczeń.

Testy offline: osobno 22 adapterów i 13 shadow (35 nowych), cały MULTIMODEL v2
141 testów, pełna regresja 749 testów. Negatywne przypadki wykrywają zmianę
ceny, exact line, fixture, statusu, oceny, kolejności TOP, hasha wejścia i freeze;
blokują łączenie różnych runów, lookahead oraz pozorne zaliczenie pełnego shadow.
