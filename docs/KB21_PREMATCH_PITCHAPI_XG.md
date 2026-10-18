# KB21 — autentyczne przedmeczowe xG z zachowanych migawek PitchAPI

## Cel i źródła

Oryginalny terminarz KB21 pozostaje **TYLKO API-Football, dziś + jutro**
w Europe/Warsaw. Drugie źródło, PitchAPI, jest używane wyłącznie
do pomocniczej **historii xG z wcześniejszych meczów**. PitchAPI
NIGDY nie może dodać meczu do terminarza.

Wykorzystujemy już istniejące pliki
`data/pitchapi/prematch/YYYY-MM-DD.json`, tworzone przez osobny
`PitchAPI prematch context`. Moduł
`tools/kb21_pitchapi_prematch_bridge.py` NIE wywołuje API;
wzbogaca bieżący dwudniowy raport KB21 bez dodatkowych kredytów.

## Kontrola dopasowania i czasu

Każdy zweryfikowany xG wymaga wszystkich warunków:

1. Poprawny źródłowy snapshot PitchAPI z datą docelową, realnym
   czasem zapisu, wersją schematu i deklaracją braku zmian modelu.
2. Mecz musi już znajdować się w zweryfikowanej liście API-Football.
   Dopasowujemy ligę, obie nazwy drużyn (normalizacja istniejąca
   w PitchAPI) i godzinę z tolerancją maksymalnie 20 minut.
   Nawet podobne nazwy nie wystarczą — bez fuzzy match.
3. Zgodność **jeden do jednego**. Kilka meczów PitchAPI pasujących
   do jednej pozycji, lub ten sam rekord PitchAPI pasujący do
   kilku pozycji API-Football, powoduje brak xG.
   Data endpointu PitchAPI bywa liczona w UTC, więc pojedynczy
   rekord z innego dnia **w Europe/Warsaw** jest pomijany, a nie
   powoduje odrzucenia wszystkich poprawnych rekordów migawki.
4. Rzeczywisty moment przechwycenia PitchAPI i utworzenia
   KB21 musi być **przed rozpoczęciem** meczu. Migawka nie
   może być z przyszłości ani starsza niż 3 dni w chwili
   użycia.
5. Dla OBU drużyn wymagamy 3–5 rzeczywistych wcześniejszych
   spotkań, każde o własnym identyfikatorze, datowane
   minimum 2 godziny przed przechwyceniem snapshotu.
   Suma i średnie xG / xGA muszą się zgadzać; duplikaty
   i niekompletne, niepoprawne lub nieliczbowe próbki odpadają.
6. Brak archiwum np. na jutro daje jawny status
   `NO_SAVED_PITCHAPI_PREMATCH_ARCHIVE`, a nie 0 xG.

Przedmeczowe średnie z historycznych meczów to **prawdziwe xG
tych wcześniejszych spotkań**, NIE przewidywana liczba goli
w meczu docelowym. Nie ma dostatecznej próby ani potwierdzonej
kalibracji, żeby podawać automat typu.

## Wynik

Do istniejącego artefaktu
`KB21 SINGLE SOURCE API-Football today+tomorrow` trafia:

- `KB21_PREODDS_XG_YYYY-MM-DD.md` — zestawienie każdego
  kanonicznego meczu, status, średnie xG/xGA, liczność.
- `KB21_PREODDS_XG_YYYY-MM-DD.json` — oryginalne identyfikatory
  spotkań z API-Football, źródłowy PitchAPI ID, czasy,
  średnie i konkretne wcześniejsze ID oraz indywidualne próbki.
- `KB21_PREODDS_XG_MANIFEST.json` — zliczona faktyczna liczba
  sparowanych meczów i kontrola braku nowych API / zapisów.

Moduł *nie* wypełnia oryginalnego STR/35, QUAL/35,
MATCH/30, P(model), kursu ani decyzji PLAY. Nie modyfikuje
KB N, historii wyników, API Market i samych prognoz SHADOW
zamrożonych przed meczem.

Testy: `python -m unittest tests.test_kb21_pitchapi_prematch_bridge -v`.
