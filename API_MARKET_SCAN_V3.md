# API Market Scan v3.2 - ocena kwotowanych wariantów

Obowiązuje od wdrożenia 2026-10-06. Korekta na życzenie użytkownika: codzienna analiza ma oceniać zakłady możliwe do odnalezienia w ofercie. Pula wejściowa pochodzi z dokładnie kwotowanych wariantów API; następnie liczymy historyczne pokrycie i korekty kontekstu. Jedna lista od 67 bez limitu liczby pozycji. Kalkulator pozostaje poza zakresem tej zmiany.

## Izolacja KB Score

API nie odczytuje ani nie zapisuje parametrów, rejestrów, N, kalibracji i reguł KB Score. Nie przekazuje swoich wyników do Google Sheets ani do codziennego procesu KB Score. Kod używa wyłącznie własnego `config/api_market.json`, danych `data/api_football/` i raportów `reports/api_market_scan/`.

`api_market_integrity.py` zatrzymuje publikację zmian Git, jeśli wykonanie workflow zmieni plik poza dozwolonymi katalogami danych API. Test pełnego przebiegu sprawdza niezmienność pliku CORE. To kontrola kodu i zapisów przed push; GitHub `contents: write` pozostaje uprawnieniem całego repozytorium, a nie izolacją systemu operacyjnego. Zewnętrzny import wyników API do KB Score jest zabroniony do oddzielnej decyzji użytkownika.

## Obliczenia i wybór pozycji

1. Pula wejściowa: wyłącznie linie i kierunki z prawidłowym kursem w odpowiedzi API. Brak ręcznie wymyślonych niskich linii. Liczymy powyżej i poniżej dla drużyn oraz sumy meczu (gole, rożne, faule, strzały, strzały celne, spalone, interwencje bramkarzy). Obsługiwane są połówkowe linie bez zwrotów. Linie całkowite i azjatyckie wymagają odrębnego modelu rozliczenia i nie są zastępowane połówkowymi.
2. API PURE: historyczne pokrycie dla każdego obsługiwanego, kwotowanego wariantu; L5/L10/L15, historia własna, historia tego, co dopuszcza przeciwnik, dom/wyjazd. Brak progów PURE 72, L10 60/50 i minimum siedmiu meczów. Do obliczenia potrzebna jest niepusta historia liczbowa obu stron.
3. Oddzielna korekta rozgrywek: historia reprezentacyjna z wagami rodzaju meczu; dla klubów rozdział liga/puchary. `competition_adjusted_pct` nie nadpisuje `api_pure_pct`.
4. Wiarygodność próby: dolna granica Wilsona obniża ocenę bez wcześniejszej twardej bramki liczby meczów. Usunięto ograniczenie obniżki do 12 punktów, aby pojedynczy udany mecz nie wyglądał jak mocna próba.
5. Bieżący rynek: odmarżowiony konsensus dokładnej linii i własne wcześniejsze snapshoty; może wzmocnić lub osłabić ocenę. Korekta nie jest nakładana wielokrotnie na wcześniejszy wynik.
6. Dostępny bieżący kontekst API: kontuzje, składy i sędzia. Nieobecności mogą dać dotychczasowy mały ujemny bezpiecznik. Składy/sędzia są zapisywane do audytu; nie dodajemy nieuzasadnionych dodatnich wag. Nieudane pobranie jest błędem/ograniczeniem danych, a nie wiadomością, że absencji nie ma.
7. Publikacja: **ocena końcowa >= 67/100**. Jest to jedyna liczbowa bramka. Brak limitu globalnego, na mecz lub na parametr, brak odrzucenia na podstawie statusu i ostrzeżenia rynku. Każdy obliczalny wariant z notowaniem przechodzi do oceny. Przed publikacją ponownie sprawdzamy obecność ceny dla wybranego kierunku; notowanie tylko UNDER nie potwierdza OVER.

Zakres dostępnych rozgrywek i obsługiwanych parametrów określa kolektor i `api_market_scan.py`. Nie wymyślamy danych dla rynków bez historii. Nie wydajemy nowych prognoz po rozpoczęciu meczu. To warunki poprawnego wejścia, nie progi atrakcyjności typu.

Lista pokazuje najpierw gole i rożne z faktycznymi notowaniami, następnie kwotowane statystyki szczegółowe. W każdej grupie kolejność jest malejąca po ocenie końcowej, bez limitu pozycji. Raport podaje kierunek, zakres, godzinę meczu w Polsce, kursy i nazwy bukmacherów źródłowych. Brak ceny nie jest zastępowany wynikiem czysto teoretycznym. API PURE oznacza pokrycie historyczne; ocena końcowa /100 jest wskaźnikiem wymagającym empirycznej kalibracji, nie gwarantowanym prawdopodobieństwem wygranej.

## STS

Obecne API-Football nie daje nam potwierdzenia oferty STS. Dokładny kurs innego bukmachera dowodzi istnienia wariantu w pobranych notowaniach, nie jego dostępności w STS. Raport jawnie rozróżnia te informacje. Sama nazwa zagranicznego bukmachera obecnego również w Polsce nie jest potwierdzeniem jego polskiej oferty.

Nie przenosimy pokrycia z niższej linii na wyższą. Under jest liczony bezpośrednio z obserwacji i otrzymuje własną ocenę wiarygodności; nie jest dopełnieniem końcowej oceny over. Sumy meczu wymagają danych obu drużyn w danym historycznym meczu, a wynik łączy historie meczowych sum gospodarzy i gości. Żółte kartki nie są mapowane na ogólne karty/punkty kartkowe z czerwonymi. Gole wykorzystują wynik regulaminowego czasu, gdy jest dostępny; znane statystyki obejmujące dogrywkę bez podziału nie służą do prognoz statystycznych na 90 minut.

## Dane i trwały zapis

- `market_work/YYYY-MM-DD.json`: robocza statystyka/enrichment, nie służy do rozliczeń.
- `market_scan/YYYY-MM-DD.json`: najnowszy opublikowany widok.
- `predictions/YYYY-MM-DD/<id>.json`: niezmienna wersja pełnej puli i opublikowanej listy, z czasem UTC, wersją modelu, konfiguracją i rewizją kodu.
- `market_snapshots/` i `closing_snapshots/`: notowania w czasie.
- `calibration/YYYY-MM-DD.json`: wyniki wszystkich kandydatów, także poniżej 67.
- `calibration/_summary.json`: oddzielna kalibracja API.

Publikacja zapisuje pełną wersję przed zastąpieniem aktualnego widoku. Starszy widok bez potwierdzonego czasu jest zachowywany jako legacy, bez dorabiania wiarygodnego freeze. Takie dane nie zwiększają próby treningowej. Rozpoczęte mecze nie trafiają do nowej listy ani nowych danych treningowych.

Rozliczenie wybiera pierwszą potwierdzoną prognozę przedmeczową dla kombinacji data/model/mecz/drużyna/parametr/linia/zakres/kierunek. Kolejne uruchomienia nie mnożą N ani nie podmieniają pierwotnej oceny. Przerwa API podczas ponownego rozliczania nie usuwa udanych wcześniejszych wyników.

## Nauka i zmiany w czasie

API ma własne obserwacje HIT/MISS, Brier i log loss dla PURE i oceny końcowej, grupowane po wersji, rynku, zakresie drużyna/mecz, kierunku over/under, przedziale ocen, korekcie rynku i publikacji. Przechowuje również rozgrywki, wielkość próby i kontekst. Liczymy osobno liczbę typów i meczów, ponieważ kilka zakładów z jednego meczu jest skorelowanych.

Zebrane wyniki służą do porównania progu 67 z innymi wartościami oraz do kalibracji warstw. Zachowujemy ostrożne checkpointy 50/100/250, z uwzględnieniem liczby różnych meczów. Nie zmieniamy wag automatycznie po kilku wynikach. Każda zmiana obliczeń lub progu jest wersjonowana wyłącznie w module API; nie zmienia KB Score.

## Kontrole

Od 2026-10-06 wspólny klient odczytów API rozkłada zapytania w czasie i uwzględnia nagłówki limitu minutowego. Błąd 429 lub JSON `rateLimit` powoduje oczekiwanie i ograniczoną liczbę ponowień; wyczerpana pula dzienna zatrzymuje dalsze zapytania. Obsługa połączenia nie zmienia wzorów oceny, progu 67 ani izolacji KB Score. Brak pobrania kursów dla wszystkich meczów przerywa skan przed publikacją; częściowe błędy są widoczne w raporcie. Ukończony prefetch historii z tego samego dnia jest wykorzystywany ponownie podczas enrichment, bez powtarzania pobrań.

Testy offline pokrywają brak ukrytych limitów i progów, zachowanie PURE, jednokrotną korektę rynku, jawne błędy prefetch, zachowanie cache przy błędzie, niezmienne wersje, odrzucenie danych po starcie, rozliczanie kandydatów odrzuconych, brak podwójnego liczenia i brak zapisów CORE. Workflow wykonuje testy przed produkcyjnym skanem.

Regresje v3.2 sprawdzają dokładny kierunek kwotowania, obliczanie under, sumę obu drużyn, oddzielne klucze prognoz, poprawne rozliczanie, zachowanie historycznych identyfikatorów oraz brak publikacji pustego raportu przy awarii wszystkich notowań.
