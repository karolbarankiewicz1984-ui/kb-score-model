# API Market Scan v3.1 - niezależny model API

Obowiązuje od wdrożenia 2026-10-05. Uzgodnienie użytkownika: najpierw pokrycie historyczne z płatnego API, następnie ocena na podstawie dostępnej sytuacji meczowej, jedna lista od 67 bez limitów ilościowych. Próg będzie oceniany w czasie na własnych wynikach API.

## Izolacja KB Score

API nie odczytuje ani nie zapisuje parametrów, rejestrów, N, kalibracji i reguł KB Score. Nie przekazuje swoich wyników do Google Sheets ani do codziennego procesu KB Score. Kod używa wyłącznie własnego `config/api_market.json`, danych `data/api_football/` i raportów `reports/api_market_scan/`.

`api_market_integrity.py` zatrzymuje publikację zmian Git, jeśli wykonanie workflow zmieni plik poza dozwolonymi katalogami danych API. Test pełnego przebiegu sprawdza niezmienność pliku CORE. To kontrola kodu i zapisów przed push; GitHub `contents: write` pozostaje uprawnieniem całego repozytorium, a nie izolacją systemu operacyjnego. Zewnętrzny import wyników API do KB Score jest zabroniony do oddzielnej decyzji użytkownika.

## Obliczenia i wybór pozycji

1. API PURE: historyczne pokrycie dla każdej obsługiwanej linii statystycznej; L5/L10/L15, historia własna, historia tego, co dopuszcza przeciwnik, dom/wyjazd. Brak progów PURE 72, L10 60/50 i minimum siedmiu meczów. Do obliczenia potrzebna jest niepusta historia liczbowa obu stron.
2. Oddzielna korekta rozgrywek: historia reprezentacyjna z wagami rodzaju meczu; dla klubów rozdział liga/puchary. `competition_adjusted_pct` nie nadpisuje `api_pure_pct`.
3. Wiarygodność próby: dolna granica Wilsona obniża ocenę bez wcześniejszej twardej bramki liczby meczów. Usunięto ograniczenie obniżki do 12 punktów, aby pojedynczy udany mecz nie wyglądał jak mocna próba.
4. Bieżący rynek: odmarżowiony konsensus dokładnej linii i własne wcześniejsze snapshoty; może wzmocnić lub osłabić ocenę. Korekta nie jest nakładana wielokrotnie na wcześniejszy wynik.
5. Dostępny bieżący kontekst API: kontuzje, składy i sędzia. Nieobecności mogą dać dotychczasowy mały ujemny bezpiecznik. Składy/sędzia są zapisywane do audytu; nie dodajemy nieuzasadnionych dodatnich wag. Nieudane pobranie jest błędem/ograniczeniem danych, a nie wiadomością, że absencji nie ma.
6. Publikacja: **ocena końcowa >= 67/100**. Jest to jedyna liczbowa bramka. Brak limitu globalnego, na mecz lub na parametr, brak odrzucenia na podstawie statusu i ostrzeżenia rynku. Wszystkie obliczalne linie przechodzą do oceny, także jeśli wcześniej odpadłyby przez deduplikację.

Zakres dostępnych rozgrywek i obsługiwanych parametrów określa kolektor i `api_market_scan.py`. Nie wymyślamy danych dla rynków bez historii. Nie wydajemy nowych prognoz po rozpoczęciu meczu. To warunki poprawnego wejścia, nie progi atrakcyjności typu.

Lista pokazuje najpierw praktyczne linie z faktycznymi notowaniami, następnie rynki specjalistyczne i dostępność niepotwierdzoną. W każdej grupie kolejność jest malejąca po ocenie końcowej; żadna grupa nie jest ukrywana ani limitowana. API PURE oznacza pokrycie historyczne; ocena końcowa /100 jest wskaźnikiem wymagającym empirycznej kalibracji, nie gwarantowanym prawdopodobieństwem wygranej.

## STS

Usunięto sztywną listę dopuszczonych trzech rodzin rynków oraz zakazy linii kartek 0.5 i rożnych 2.5. Nie utożsamiamy brakującego notowania w API z brakiem oferty STS.

Każda pozycja dostaje informację o dokładnej linii w danych kursowych i o niepewności dostępności w STS. Typowe linie z faktycznym notowaniem mają pierwszeństwo w prezentacji. Rynek specjalistyczny lub brak notowania jest jawnie opisany. Bez bezpośredniego notowania STS nie deklarujemy weryfikacji jego oferty i nie ukrywamy pozycji na podstawie przypuszczenia.

## Dane i trwały zapis

- `market_work/YYYY-MM-DD.json`: robocza statystyka/enrichment, nie służy do rozliczeń.
- `market_scan/YYYY-MM-DD.json`: najnowszy opublikowany widok.
- `predictions/YYYY-MM-DD/<id>.json`: niezmienna wersja pełnej puli i opublikowanej listy, z czasem UTC, wersją modelu, konfiguracją i rewizją kodu.
- `market_snapshots/` i `closing_snapshots/`: notowania w czasie.
- `calibration/YYYY-MM-DD.json`: wyniki wszystkich kandydatów, także poniżej 67.
- `calibration/_summary.json`: oddzielna kalibracja API.

Publikacja zapisuje pełną wersję przed zastąpieniem aktualnego widoku. Starszy widok bez potwierdzonego czasu jest zachowywany jako legacy, bez dorabiania wiarygodnego freeze. Takie dane nie zwiększają próby treningowej. Rozpoczęte mecze nie trafiają do nowej listy ani nowych danych treningowych.

Rozliczenie wybiera pierwszą potwierdzoną prognozę przedmeczową dla kombinacji data/model/mecz/drużyna/parametr/linia. Kolejne uruchomienia nie mnożą N ani nie podmieniają pierwotnej oceny. Przerwa API podczas ponownego rozliczania nie usuwa udanych wcześniejszych wyników.

## Nauka i zmiany w czasie

API ma własne obserwacje HIT/MISS, Brier i log loss dla PURE i oceny końcowej, grupowane po wersji, rynku, przedziale ocen, korekcie rynku i publikacji. Przechowuje również rozgrywki, wielkość próby i kontekst. Liczymy osobno liczbę typów i meczów, ponieważ kilka zakładów z jednego meczu jest skorelowanych.

Zebrane wyniki służą do porównania progu 67 z innymi wartościami oraz do kalibracji warstw. Zachowujemy ostrożne checkpointy 50/100/250, z uwzględnieniem liczby różnych meczów. Nie zmieniamy wag automatycznie po kilku wynikach. Każda zmiana obliczeń lub progu jest wersjonowana wyłącznie w module API; nie zmienia KB Score.

## Kontrole

Od 2026-10-06 wspólny klient odczytów API rozkłada zapytania w czasie i uwzględnia nagłówki limitu minutowego. Błąd 429 lub JSON `rateLimit` powoduje oczekiwanie i ograniczoną liczbę ponowień; wyczerpana pula dzienna zatrzymuje dalsze zapytania. Obsługa połączenia nie zmienia wzorów oceny, progu 67 ani izolacji KB Score.

Testy offline pokrywają brak ukrytych limitów i progów, zachowanie PURE, jednokrotną korektę rynku, jawne błędy prefetch, zachowanie cache przy błędzie, niezmienne wersje, odrzucenie danych po starcie, rozliczanie kandydatów odrzuconych, brak podwójnego liczenia i brak zapisów CORE. Workflow wykonuje testy przed produkcyjnym skanem.
