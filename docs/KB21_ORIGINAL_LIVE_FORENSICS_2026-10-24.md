# KB Score 2.1 LIVE — wyniki odzyskiwania oryginalnej metody (24.10.2026)

**Status: częściowo odzyskane, bez pełnego wzoru P(model).**
Ten dokument jest zapisem odczytu **tylko do odczytu** autentycznego, podłączonego
arkusza **„KB Score – Rejestr i Backtest”**, zakładek `Parametry`, `Rejestr`,
`Kalibracja`, `Listy` i `Backtest`, a także dostępnej historii jego rewizji.
Nie przenosimy wierszy prywatnego arkusza ani jego identyfikatora do repozytorium.
**Nie zmieniono arkusza, N, żadnych wyników ani istniejących prognoz.**

## 1. Odzyskane zasady LIVE — potwierdzone w `Parametry`

| Blok | Maksimum | Co ocenia |
| --- | ---: | --- |
| STR — siła strukturalna | 35 | ELO / power rating, kadra, liga, bazowa siła długoterminowa |
| QUAL — aktualna jakość gry | 35 | xG/xGA, strzały/sytuacje, forma skorygowana o przeciwników |
| MATCH — kontekst/matchup | 30 | miejsce meczu, styl, kluczowe absencje, odpoczynek, kontekst |

**Sport Score = STR + QUAL + MATCH** (0–100).
H2H i motywacja tylko wewnątrz kontekstu, zwykle maksymalnie ±1 pkt i ±2 pkt.
Braki danych nie oznaczają automatycznego odjęcia punktów — dopuszczono
reweighting wewnątrz bloku oraz osobną korektę Confidence.

`P(model)` jest oceną konkretnego rynku **przed** sprawdzeniem kursu,
nie procentem równym Sport Score. `P(HIT)` jest dodatkowym osobnym ujęciem
prawdopodobieństwa konkretnego rynku. `Consensus` służy do kontroli, nie
do kopiowania do `P(model)`; `Price / EV / Edge` nie podwyższa Sport Score.

Dla prawdziwego LIVE:
- `PLAY`, `LEARN` oraz `CONTROL` **bez twardego progu Sport Score**;
- orientacyjne minimalne EV: Confidence 8–10 → 2%, 6–7 → 3,5%,
  Confidence 5 → 5%; Confidence <5 → bez PLAY;
- LEARN: zasadniczo sensowny kierunek z istotną wątpliwością co do ceny,
  danych, kontrargumentów lub spójności;
- CONTROL: kontrola kierunków bez value, ze słabą pewnością lub sprzecznymi
  sygnałami; nie jest grą;
- bez limitu liczby PLAY, do 2 pozycji CONTROL dziennie w opisie ustawień;
- potrzeba oddzielnych kontroli no-vig, Market Signal, Data Quality,
  Lineup Risk i zamrożenia przed kursem.

## 2. Co znaleziono w faktycznych historycznych wpisach LIVE

Odczytano `Rejestr!A25:AO207` (data analizy 22.08–06.10.2026).
Wśród 179 pełnych wierszy z datą i wydarzeniem:
- **123** mają w notatkach jednoznaczne wartości
  `STR x/35 | QUAL y/35 | MATCH z/30`.
  We **wszystkich 123** suma składników jest równa zapisanej kolumnie
  `KB Score`, bez wyjątku.
- Część późniejszych notatek używa skrótu `35/35/30=.../.../...`
  i wymaga innego parsera; brak standardowego zapisu nie oznacza braku
  metodologii ani uprawnienia do retroaktywnego uzupełniania N.
- W typowych wierszach LIVE `Rejestr!J` (`P(model)`), `Rejestr!Y`
  (`KB Score`) i `Rejestr!AB` (`Decyzja`) są **wartościami
  wpisanymi**, a NIE komórkami z jawnym wzorem matematycznym.
- Zapisana wartość EV daje się sprawdzić równaniem
  `EV = P(model) * kurs - 1`. W **179** sprawdzonych wierszach
  nie znaleziono rozbieżności większej niż 1 punkt procentowy.
- W próbce tych 179 wierszy znajdują się 49 PLAY, 42 LEARN i 88 CONTROL.
  Spośród 49 PLAY sześć ma zapisane EV poniżej **typowego**, zależnego
  od Confidence minimum. To potwierdza, że historyczna decyzja
  **nie jest identyczna z jednym sztywnym testem EV** (może być też
  wyjątkiem, zmianą polityki lub błędem; nie należy automatycznie
  akceptować takiego odchylenia).

### Bardzo ważna zmiana wersji

Przed 22.08.2026 starsze wpisy używały dziesięciu czynników w kolumnach
`O:X`, a komórki `Y` nieraz zawierały wzór `SUM(O:X)`. Wśród tych
czynników znajdowały się **Ruch kursów** i **Value factor**.
Nie należy odtwarzać LIVE 2.1 z takiego starego wzoru, ponieważ od
22.08.2026 zasady `Parametry` WYRAŹNIE wykluczają cenę/kurs z Sport Score.
Dane starej i nowej metodologii muszą pozostać rozróżnialne.

### Przykład braku wzoru Sport Score -> P(model)

Zachowały się mecze z tym samym `Sport Score = 84`,
ale istotnie różnym `P(model)` dla wybranych rynków.
Ocena siły meczu **nie jest sama w sobie prawdopodobieństwem wejścia
konkretnego typu**.

## 3. Próba niezależnego odtworzenia P(model) z zanotowanego xG

Z notatek dało się wyodrębnić **94** wiersze LIVE typu `1X2` z parą
wpisanych xG dla gospodarzy i gości oraz jednoznacznym wskazaniem strony.
Dla wszystkich 94 obliczono bazowy rozkład bramkowy **niezależnego Poissona**,
wybrano prawdopodobieństwo dokładnie tego kierunku 1X2, następnie
porównano ze ZAPISANYM `P(model)` (bez dopasowywania parametrów).

- średnia różnica bezwzględna: **4,06 pp**;
- rozbieżność ≤1 pp: **28 z 94**;
- rozbieżność ≤3 pp: **42 z 94**;
- rozbieżność ≤5 pp: **61 z 94**;
- rozbieżność >10 pp: **4 z 94**.

Wniosek: czysty Poisson z **zanotowanych** xG jest przydatnym punktem
porównawczym, ale **nie odtwarza wiernie zapisanego P(model)**.
Nie można stwierdzić na tej podstawie, czy historyczny analityk
dodawał określoną korektę do Poissona, korzystał z innych parametrów,
czy oceniał rynek niezależnie. Dane xG w notatkach bywają zaokrąglone.
Nie wolno nazwać nowego Poissona „odzyskanym oryginałem”.

Historyczne opisy potwierdzają też rozważanie `P(HIT)` dla podpórek
`1X` i `X2` z sumą odpowiednich kategorii 1X2 (zwykłe działanie na
prawdopodobieństwach, nie odzyskany silnik ich wytwarzania).

## 4. Historia wersji arkusza

Google Drive udostępnia rewizje od sierpnia do października 2026;
w kontrolowanych rewizjach z sierpnia 2026 reguły 35/35/30 oraz
EV/Confidence są zapisane opisowo. Nie znaleziono w nich
deterministycznego wyliczenia oryginalnych składowych ani `P(model)`.
Są natomiast formuły **CORE v1R**, jawnie oznaczone jako osobny
historyczny backtest (DEV/VALIDATION/TEST), który nie jest KB21 LIVE.

## 5. Konsekwencje dla kodu

**Można teraz wiernie odzyskać:**
1. model danych oceny STR/35, QUAL/35, MATCH/30 i kontrolę sumy;
2. przechwycenie wybranej linii rynku, osobnego `P(model)` przed ceną;
3. `fair odds = 1/P`, `implied=1/kurs`, `Edge=P - implied`,
   `EV=P*kurs - 1`, a dla pełnych kursów 1X2 osobno no-vig;
4. ramową, audytowalną kwalifikację PLAY/LEARN/CONTROL,
   gdzie progi Confidence/EV służą jako kontrole, a nie jedyny wzór.

**Nieodzyskane:**
1. szczegółowe funkcje/statystyki/subwagi obliczające STR, QUAL, MATCH;
2. funkcja wyprowadzająca oryginalne `P(model)` z danych meczu;
3. kompletny deterministyczny klasyfikator PLAY/LEARN/CONTROL wraz
   z wyjątkami i priorytetami, weryfikowalny na zamrożonych danych;
4. autentyczne przedmeczowe snapshoty dla wszystkich starych wpisów
   (obecna zawartość arkusza nie jest dowodem historycznego freeze).

## 6. Następny eksperyment, bez podmieniania oryginału

- Zachować oryginalne dzienne karty API-Football i dowody/odczyty xG.
- Zbudować oddzielnie wersjonowany **KANDYDAT LIVE AUTO / SHADOW**,
  wykorzystujący bieżące dane oraz jawny punkt odniesienia Poissona,
  niezależny od oryginalnego `P(model)` i jego N.
- Wykonać co najmniej 10 **nowych** przedmeczowych freeze w niezależnych
  artefaktach z czasem rejestracji, następnie porównać z wynikiem.
- Dopiero po kalibracji i uzgodnieniu zasad ręcznie promować nową
  wersję do decyzji; nie tworzyć z samego odtworzenia historii
  automatycznych PLAY, nie przepisywać tabeli pierwotnej.

Źródło główne: użytkownikowy oryginalny arkusz Google Sheets
„KB Score – Rejestr i Backtest”, taby `Parametry` (A1:E50),
`Rejestr` (A1:AO207), `Kalibracja`; odczyt read-only z 24.10.2026.
Informacje mają charakter śledczy i nie są audytem pełnej jakości
historycznych prognoz ani potwierdzeniem ich rzeczywistego zysku.
