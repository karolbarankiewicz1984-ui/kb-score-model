# API Market Scan v3 — trwała specyfikacja

## 1. Izolacja od KB Score 2.1 CORE

API Market Scan v3 jest osobnym modułem. Nie zmienia KB Score 2.1 CORE, jego parametrów, KB N ani DEV N.

Stałe zasady:
- `KB N += 0`
- `DEV N += 0`
- API PURE pozostaje widoczną wartością bazową.
- Warstwy v3 nie mogą przepisywać ustawień CORE.

## 2. Co liczy się w tle

Kolejność warstw:

`API PURE -> Reliability -> Competition Context -> Market Overlay -> Current Context -> FINAL API ASSESSMENT`

### API PURE
Czysta statystyka historyczna z API-Football, bez kursów i bez bieżących newsów.

### Reliability
Konserwatywny filtr wielkości i stabilności próby. Używa dolnej granicy Wilsona jako zabezpieczenia przed nadmiernym zaufaniem do wysokich procentów z małej próby. Reliability może obniżyć ocenę, ale nie może sztucznie podwyższyć API PURE.

### Competition Context
- ligi krajowe: profil krajowy,
- europejskie puchary: historia krajowa i europejska są liczone osobno, a udział warstwy europejskiej rośnie wraz z jej próbą,
- reprezentacje: dynamiczna historia ostatnich 20 meczów oraz mniejsza waga sparingów niż spotkań o stawkę.

Wagi startowe reprezentacji:
- Friendlies: 0.55
- UEFA Nations League: 0.85
- World Cup: 1.00
- World Cup Qualification Europe: 0.95
- Euro Championship: 1.00
- Euro Championship Qualification: 0.95

### Market Overlay
Bieżące pre-match odds dla dokładnie tej samej linii. System:
- zbiera Over i Under od wielu bukmacherów,
- usuwa marżę,
- liczy medianę prawdopodobieństwa rynku,
- ocenia szerokość i spójność rynku,
- wykorzystuje wcześniejsze własne snapshoty do pomiaru ruchu.

API PURE pozostaje zachowane oddzielnie.

### Current Context
Warstwa bieżąca korzysta z dostępnych danych API o:
- kontuzjach/nieobecnościach,
- sędzim,
- oficjalnych składach, gdy są już opublikowane.

Do czasu zebrania odpowiedniej próbki kalibracyjnej jest to warstwa audit-first. Może uruchomić mały negatywny bezpiecznik, ale nie dostaje dużej dodatniej wagi na podstawie intuicji. Maksymalny startowy ujemny filtr kontekstowy to 1.5 pp.

## 3. Ocena końcowa i publikacja

Użytkowy ranking jest oparty na `FINAL API ASSESSMENT`, a nie wyłącznie na surowym procencie historycznym.

Statusy:
- `STRONG` — najmocniejsze pozycje po wszystkich warstwach,
- `ACCEPT` — pozycje spełniające warunki publikacji,
- `WATCH` — obserwacja; nie trafia do głównej listy PDF.

Nie ma obowiązku publikowania 10 pozycji. Jeśli warunki spełniają 2 lub 3 pozycje, raport zawiera tylko 2 lub 3.

## 4. Widok dla użytkownika

PDF pozostaje celowo prosty. Dla każdej publikowanej pozycji pokazuje głównie:
- pozycję i mecz,
- `API PURE`,
- `Ocena końcowa`,
- kierunek zmiany,
- `STRONG` lub `ACCEPT`,
- krótki komentarz zwykłym językiem.

Reliability, L5/L10/L15, rozdział domestic/Europe, szczegóły rynku, injuries, referee, lineup, surowe kursy i inne dane audytowe pozostają w JSON-ie na GitHubie.

Na końcu PDF zawsze znajduje się krótka sekcja „Jak czytać ten raport”.

## 5. Closing market

Osobny workflow sprawdza w ciągu dnia tylko zamrożone pozycje, których start jest blisko. Zapisuje końcowe/near-closing snapshoty rynku do:

`data/api_football/closing_snapshots/YYYY-MM-DD/`

Closing market służy do audytu i kalibracji. Nie zmienia po fakcie opublikowanego freeze.

## 6. Automatyczne rozliczenie

Po zakończeniu dnia osobny proces pobiera rzeczywiste statystyki meczów i rozlicza każdą opublikowaną pozycję jako HIT/MISS. Zapisuje m.in.:
- API PURE,
- reliability-adjusted,
- market-adjusted,
- FINAL API ASSESSMENT,
- status,
- wynik rzeczywisty,
- closing market, jeśli został wiarygodnie zebrany.

Dane trafiają do:

`data/api_football/calibration/YYYY-MM-DD.json`

## 7. Kalibracja

System automatycznie odbudowuje podsumowanie kalibracyjne i mierzy m.in. hit rate, Brier oraz log loss dla API PURE i oceny końcowej.

Analizy są grupowane m.in. według:
- rodzaju rynku,
- statusu STRONG/ACCEPT,
- przedziału API PURE,
- przedziału oceny końcowej,
- kierunku korekty rynku.

Polityka zmian wag:
- N < 50: tylko obserwacja,
- N 50–99: pierwsze sygnały, bez istotnego dostrajania,
- N >= 100: możliwa ostrożna kalibracja,
- N >= 250 dla danej warstwy/rynku: mocniejsza podstawa do zmian.

Wagi nie zmieniają się automatycznie tylko dlatego, że kilka ostatnich typów wygrało lub przegrało. Każda istotna korekta wymaga powtarzalnego sygnału i pozostaje wersjonowana na GitHubie.

## 8. Zasada nadrzędna

Model ma być bardziej złożony w środku, ale prostszy dla użytkownika. Rozbudowa zaplecza ma służyć trafności, a nie liczbie wskaźników w raporcie.
