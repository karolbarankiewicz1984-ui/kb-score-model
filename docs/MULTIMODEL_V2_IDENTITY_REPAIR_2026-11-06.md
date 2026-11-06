# MULTIMODEL v2 — naprawa pokrycia i identyfikacji (2026-11-06)

Status: **badawcze poprawki zweryfikowane; produkcyjny MULTIMODEL bez zmian**.

Gałąź: `codex/multimodel-v2`. Baza porównania: `f609427e07ea9e9e944a61c3063ab18a11f3b897`. Rewizja pełnego przebiegu: `703b533ed45ae005c2a0825cd6a50de640da797c`. Cutoff danych UTC: `2026-11-06T09:53:42.542940+00:00`.

## Wynik i sposób porównania

Ta sama kolejka zawiera **488** spotkań. Wszystkie kolumny porównania używają tych samych ID i cutoff; 0 spotkań rozpoczętych do cutoff wyłączono jednakowo w obu wariantach. To porównanie zapisanej kolejki, nie deklaracja kompletności całego światowego kalendarza.

„Przed / 5 lig” to kod bazowy i dawny zakres importu. „Przed / ta sama historia” izoluje zmianę identyfikacji: oba kody otrzymują identyczną rozszerzoną historię dostępną w cutoff. Gotowość tożsamości, Elo i historii Dixon–Coles nie oznacza automatycznie udanego dopasowania ani kalibracji.

| Wariant | Rozpoznana tożsamość | Gotowe Elo | Historia DC |
| --- | --- | --- | --- |
| Przed / 5 lig | 33 | 33 | 33 |
| Przed / ta sama historia | 87 | 87 | 87 |
| Po zmianach | 277 | 276 | 277 |

Rzeczywiście zapisano **553** prognoz 1X2 na **277** spotkań oraz **4302** pozycji rynków zdarzeń. Poniższa tabela zachowuje każde ID ligi, także przy zerowym pokryciu.

## Pokrycie każdej ligi

W trzech kolumnach „Elo gotowe” podano historyczną gotowość. Dwie ostatnie kolumny liczą rzeczywiście zapisane prognozy modeli.

| ID ligi | Liga / kraj | Kolejka | Elo gotowe: przed 5 lig | Elo gotowe: przed ta sama historia | Elo gotowe: po | Elo zapisane | DC zapisane |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l_0275VP | Ligue 2 / FRA | 9 | 0 | 5 | 9 | 9 | 9 |
| l_0ALvwF | Serie A / ITA | 10 | 10 | 10 | 10 | 10 | 10 |
| l_0ErfuF | La Liga / ESP | 10 | 7 | 7 | 10 | 10 | 10 |
| l_0F4I4F | 1. Liga / CZE | 8 | 0 | 0 | 0 | 0 | 0 |
| l_0Lpz1f | Saudi Pro League / SAU | 6 | 0 | 0 | 0 | 0 | 0 |
| l_0S1uaf | Super Lig / TUR | 9 | 0 | 4 | 9 | 9 | 9 |
| l_0aEfof | Pro League / ARE | 7 | 0 | 0 | 0 | 0 | 0 |
| l_0eg6C9 | MLS / USA | 15 | 0 | 8 | 15 | 15 | 15 |
| l_0jy5yE | Serie B / ITA | 10 | 0 | 8 | 10 | 10 | 10 |
| l_0kSJLz | Romanian Superliga / ROU | 7 | 0 | 0 | 7 | 7 | 7 |
| l_0uqFK8 | Eliteserien / NOR | 8 | 0 | 4 | 8 | 8 | 8 |
| l_16Sq13 | Ligat ha'Al / ISR | 7 | 0 | 0 | 0 | 0 | 0 |
| l_1BFfna | 1. Lig / niezweryfikowany | 10 | 0 | 0 | 0 | 0 | 0 |
| l_1D8Xrl | Brazilian Serie A / BRA | 1 | 0 | 0 | 1 | 1 | 1 |
| l_1Isor4 | Bundesliga / DEU | 9 | 0 | 0 | 9 | 9 | 9 |
| l_1LMdEO | Premiership / SCO | 6 | 0 | 4 | 6 | 6 | 6 |
| l_1SGwQT | Women's Premier League / SAU | 3 | 0 | 0 | 0 | 0 | 0 |
| l_1TVRZW | Primera Division / VEN | 3 | 0 | 0 | 0 | 0 | 0 |
| l_1XsMdH | Allsvenskan / SWE | 8 | 0 | 5 | 8 | 8 | 8 |
| l_1dmt9H | Serie A / ECU | 6 | 0 | 0 | 0 | 0 | 0 |
| l_1pQOHK | Challenger Pro League / BEL | 7 | 0 | 0 | 0 | 0 | 0 |
| l_1qpFVw | Indian Super League / IND | 3 | 0 | 0 | 0 | 0 | 0 |
| l_1rPvVD | 1. Division / DNK | 5 | 0 | 0 | 0 | 0 | 0 |
| l_1xXulJ | Primera A / COL | 7 | 0 | 0 | 0 | 0 | 0 |
| l_20pNSc | Chinese Super League / CHN | 8 | 0 | 0 | 8 | 8 | 8 |
| l_214sqK | Ekstraklasa / POL | 9 | 0 | 2 | 9 | 9 | 9 |
| l_271pqa | K League 2 / KOR | 8 | 0 | 0 | 0 | 0 | 0 |
| l_2ApGa4 | J1 League / JPN | 10 | 0 | 0 | 10 | 10 | 10 |
| l_2EKrnc | K League 1 / KOR | 6 | 0 | 0 | 0 | 0 | 0 |
| l_2L6d1F | Jupiler Pro League / BEL | 9 | 0 | 0 | 9 | 9 | 9 |
| l_2Mh0jT | Russian Premier League / RUS | 8 | 0 | 0 | 7 | 7 | 8 |
| l_2tFk9k | HNL / HRV | 5 | 0 | 0 | 0 | 0 | 0 |
| l_2xBPKk | Super Liga / SRB | 7 | 0 | 0 | 0 | 0 | 0 |
| l_3CB6qX | Saudi First Division / SAU | 8 | 0 | 0 | 0 | 0 | 0 |
| l_3Ci5Cg | Veikkausliiga / FIN | 3 | 0 | 2 | 3 | 3 | 3 |
| l_3FJFUl | Ligue 1 / FRA | 9 | 9 | 9 | 9 | 9 | 9 |
| l_3Kf7Ni | USL League One / USA | 1 | 0 | 0 | 0 | 0 | 0 |
| l_3UiOcj | Premier League / CAN | 2 | 0 | 0 | 0 | 0 | 0 |
| l_3fglZv | J3 League / JPN | 10 | 0 | 0 | 0 | 0 | 0 |
| l_3hW1NO | Thai League 1 / THA | 8 | 0 | 0 | 0 | 0 | 0 |
| l_3hvsne | 2. Bundesliga / DEU | 9 | 0 | 1 | 9 | 9 | 9 |
| l_3kyHLd | La Liga 2 / ESP | 10 | 0 | 0 | 10 | 10 | 10 |
| l_3qNjzC | Liga de Primera / CHL | 7 | 0 | 0 | 0 | 0 | 0 |
| l_3qUkB8 | Serie B / BRA | 9 | 0 | 0 | 0 | 0 | 0 |
| l_3uNwVX | Liga 1 / PER | 7 | 0 | 0 | 0 | 0 | 0 |
| l_3v84VE | Liga MX / MEX | 7 | 0 | 3 | 7 | 7 | 7 |
| l_3wr44B | Qatar Stars League / QAT | 6 | 0 | 0 | 0 | 0 | 0 |
| l_3xwVF2 | Super League / GRC | 7 | 0 | 0 | 7 | 7 | 7 |
| l_3yVUAO | USL Championship / USA | 4 | 0 | 0 | 0 | 0 | 0 |
| l_3zsMpo | Austrian Bundesliga / AUT | 6 | 0 | 0 | 6 | 6 | 6 |
| l_45VZuL | Liga Profesional / ARG | 28 | 0 | 5 | 28 | 28 | 28 |
| l_45xKXM | Virsliga / LVA | 5 | 0 | 0 | 0 | 0 | 0 |
| l_47077Y | 3. Liga / DEU | 10 | 0 | 0 | 0 | 0 | 0 |
| l_49KZaB | Eerste Divisie / NLD | 10 | 0 | 0 | 0 | 0 | 0 |
| l_49Zmno | Danish Superliga / DNK | 6 | 0 | 0 | 6 | 6 | 6 |
| l_4DWyTT | Championship / ENG | 12 | 0 | 1 | 12 | 12 | 12 |
| l_4FPF2L | Division Profesional / PRY | 4 | 0 | 0 | 0 | 0 | 0 |
| l_4H43wr | Eredivisie / NLD | 9 | 0 | 2 | 9 | 9 | 9 |
| l_4MPd7x | A-League / AUS | 5 | 0 | 0 | 0 | 0 | 0 |
| l_4MU9Yh | 1. liga / SVK | 6 | 0 | 0 | 0 | 0 | 0 |
| l_4QexZg | Primeira Liga / PRT | 9 | 0 | 0 | 9 | 9 | 9 |
| l_4WFCIZ | Premier League / ENG | 10 | 7 | 7 | 10 | 10 | 10 |
| l_4auCPk | Swiss Challenge League / CHE | 5 | 0 | 0 | 0 | 0 | 0 |
| l_4d6Bwl | Swiss Super League / CHE | 6 | 0 | 0 | 6 | 6 | 6 |
| l_4dzm4e | Primera Division / BOL | 6 | 0 | 0 | 0 | 0 | 0 |

## Naprawy i usunięte blokady

| Rejestr | Problem | Poprawka i zachowane zabezpieczenie | Pliki |
| --- | --- | --- | --- |
| R01 | Niejednoznaczne nazwy lig i błędne powiązanie kraju | Zweryfikowane, nieprzybliżane ID PitchAPI oraz para nazwa–kraj oddzielają m.in. angielską i rosyjską Premier League, niemiecką i austriacką Bundesligę oraz włoską i brazylijską Serie A. | competition_identity.py |
| R02 | Brak kodu kraju w LeagueRef i różne kody dostawców | Kolektor pobiera szczegółowe metadane ligi. Jawne aliasy kodów obejmują rzeczywiście zaobserwowane wartości, m.in. GER/DEU, NED/NLD, POR/PRT i DEN/DNK. INT i nieznane kody nie stają się zweryfikowanym krajem. | pitchapi_fixtures.py; competition_identity.py |
| R03 | Różnice nazw drużyn i znaków Unicode | Wspólny resolver stosuje wyłącznie jawne aliasy w jednej lidze i rzeczywistym zbiorze kandydatów. Kolizja nazwy dokładnej i aliasu, niejednoznaczne warianty oraz sprzeczne identyfikatory są odrzucane; brak fuzzy matching. | team_mapping.py; reviewed_team_aliases.py; reviewed_resolver.py |
| R04 | Historia ograniczona do pięciu lig | Rozdzielono parser 22 europejskich dywizji mmz4281 i odmiennego schematu 16 plików /new. Kraje, ligi, sezony, wyniki, duplikaty i rzeczywiste czasy odczytu są sprawdzane. Statystyk nie zastępują wyniki bramkowe. | public_results.py; additional_results.py; collect_events.py; event_parser.py |
| R05 | Limit 80 spotkań oraz granice UTC/Warszawa | Nowy kolektor badawczy pobiera wszystkie zwrócone fixtures bez limitu 80 i grupuje je według dni Warszawy. Zakres wymaga trzech, a przy granicy dat maksymalnie czterech zapytań o daty UTC. Błąd źródła nie jest pustym kompletnym kalendarzem. | pitchapi_fixtures.py; daily_queue.py |
| R06 | Niespójna identyfikacja prognoz i audytów | Wszystkie ścieżki korzystają z jednego resolvera i historii dostępnej w cutoff. Audyt rozdziela gotowość tożsamości, Elo, historii Dixon–Coles i rzeczywiście zapisane prognozy. | predict.py; coverage_audit.py; event_markets.py |
| R07 | Niebezpieczne rozliczanie przez przybliżoną datę | Usunięto dopasowanie daty ±1 dzień i odejmowanie dwóch dni od dowolnego czasu końca. Rozliczenie wymaga dokładnej ligi, kolejności drużyn i zweryfikowanej daty. Zamrożona tożsamość zachowuje dostawcę i oba warianty kluczy ID; identyfikatorów różnych dostawców nie utożsamia się. | settlement.py; market_settlement.py; settle.py; kb3_history_bridge.py |
| R08 | Wsteczny czas obserwacji i sztuczne podbijanie prób | Czas obserwacji powstaje po odczycie odpowiedzi, a cutoff po wszystkich odpowiedziach. Duplikat nie zwiększa N treningowego; sprzeczne wersje są wykluczane. Kontrole publikacji, ukończenia i kickoff pozostają aktywne. | public_results.py; collect_events.py; elo_engine.py; event_markets.py |
| R09 | Błędy matematyki Poissona i normalizacji | Naprawiono zerową intensywność, utratę małych ogonów i walidację parametrów. Linie całkowite wymagające zwrotu są jawnie poza kontraktem binarnym. Dixon–Coles koryguje wyłącznie dopuszczalny błąd zaokrąglenia, a nie dowolne błędne wagi. | event_markets.py; elo_engine.py; multimodel_v2/dixon_coles_shadow.py |
| R10 | Kartki o niejasnej definicji | Rynek cards oznacza HY+AY, czyli żółte kartki. Nie dopisano czerwonych kartek, fauli ani rożnych do źródeł zawierających tylko gole. | event_parser.py; event_markets.py; research_pdf.py |
| R11 | Niepełny przebieg badawczy i brak powtarzalnych wejść | Workflow wykonuje pełną regresję, pobiera rzeczywiste źródła, trenuje modele, oblicza wszystkie rynki, odczytuje istniejące archiwa rozliczeń i tworzy PDF. Artefakt zawiera macierze wejściowe, manifesty, snapshoty, prognozy i raport. | .github/workflows/github-models-independent.yml |
| R12 | Powtarzane identyczne dopasowania Dixon–Coles | Cache jest lokalny dla jednego przebiegu i związany z dokładnymi uporządkowanymi wejściami, dostępnością, cutoff, wersją, parametrami i klasą zależności. Walidacja działa przed odczytem cache; nieudane dopasowanie nie trafia do cache. Rzeczywisty replay ligi argentyńskiej dał identyczne pełne prognozy z cache i bez cache. | predict.py; dixon_coles_engine.py; multimodel_v2/dixon_coles_shadow.py |
| R13 | Nieczytelna prezentacja i nadinterpretacja prognoz | Raport ma sekcje, instrukcję interpretacji pięciu rynków, liczebności prób i krótkie uzasadnienia obserwacji. Prognozy są jawnie niekalibrowane; nie opisuje się ich jako potwierdzonych okazji bukmacherskich. Pełna macierz jest oddzielona od zwięzłego podsumowania. | research_pdf.py; reports/github_models/repair_2026-11-06/build_summary_pdf.py |
| R14 | Brak porównania każdej ligi na tej samej próbie | Stary kod uruchamia się w osobnym procesie i checkout. Raport zachowuje wszystkie ID lig i ten sam mianownik, także dla odrzuceń, oraz rozdziela zmianę zakresu historii od samej naprawy identyfikacji. Hashe wiążą wejścia i artefakt. | coverage_comparison.py; reports/github_models/repair_2026-11-06/verify_artifacts.py |

## Dane i kontrola czasu

Artefakt zawiera **42133** zweryfikowanych wyników z **38** lig oraz **25360** rekordów statystyk zdarzeń. Odczyty są opisane manifestami i hashami; czas obserwacji pochodzi z odczytu odpowiedzi, a nie z daty rozegrania meczu. Dla football-data.co.uk `completed_at_utc` pozostaje konserwatywną granicą data meczu + 2 dni, nie rzeczywistym końcowym gwizdkiem.

Zakres obejmuje 22 dywizje `mmz4281` i 16 dodatkowych plików krajowych `/new`. Osobno skonfigurowano Swiss Challenge League, ale dwa znalezione wyniki z 2020/21 są poza zakresem od 2023 r.; nie obniżono zakresu jakości, aby dopisać prognozy. Dodatkowe pliki z wynikami bez statystyk mogą zasilać 1X2 i bramki, lecz nie tworzą obserwacji kartek, fauli ani rożnych.

Cutoff oznacza dostępność wejść. Obliczenia i publikacja artefaktu mogą zakończyć się później; raport nie potwierdza formalnego forward ani oryginalnej publikacji każdej prognozy przed kickoff. Replay odtwarza obliczenia badawcze; nie jest nowym zamrożeniem historycznej prognozy.

## Rynki i matematyka

| Model / rynek | Zapisane pozycje |
| --- | --- |
| callumfm-dixon-coles | 277 |
| github-elo | 276 |
| Żółte kartki | 882 |
| Rożne | 882 |
| Faule | 882 |
| Bramki | 1656 |

Walidacja matematyki: **PASS**. Maksymalny błąd sumy 1X2: `1.1102230246251565e-16`; maksymalny błąd komplementarności OVER/UNDER: `0.0`. Maksymalna różnica względem `scipy.stats.poisson.sf`: `4.998369087516608e-07` z tolerancją wynikającą z zapisu do sześciu miejsc po przecinku. Sprawdzono zakres [0,1], skończoność, kompletne pary stron i monotoniczność ogonów.

Dla 1X2 suma trzech prawdopodobieństw wynosi 1. Dla tej samej linii połówkowej OVER i UNDER sumują się do 1. Kartki oznaczają żółte kartki HY+AY. Linie całkowite z możliwym zwrotem nie są przedstawiane jako taki rynek binarny. Poprawna matematyka nie dowodzi trafności, kalibracji, wspólnego rozkładu niezależnych modeli ani opłacalności zakładu.

## Testy i GitHub Actions

| Kontrola | Wynik |
| --- | --- |
| Pełna regresja bazowa | 1078 / PASS |
| Końcowa pełna regresja lokalna | 1226 / PASS |
| Końcowy pełny przebieg GitHub Actions | 42197854709 / success |
| SHA uruchomionego kodu | 703b533ed45ae005c2a0825cd6a50de640da797c |
| SHA256 pobranego artefaktu | 80c0ce7c0be80e8ebed61bd24e9c61d6473be2430e8d9c9017119bfce0eda5cc |
| Zachowane progi jakości | {"elo_team_min": 5, "dixon_coles_league_min": 30, "event_league_min": 60, "event_team_min": 8} |
| Zapisy do N | 0 |

W trakcie kolejnych rozszerzeń lokalne pełne zestawy przechodziły po 1182, 1201 i 1211 testów. Końcową liczbę oraz status ostatniego uruchomienia podano powyżej na podstawie przekazanej weryfikacji; liczby z etapów nie zastępują kontroli końcowego SHA.

W niezależnym teście na rzeczywistych danych argentyńskich pełne słowniki prognoz z cache i bez niego były identyczne. Pierwsze 5,3 s obejmowało rozgrzanie JIT; rozgrzane wywołania miały około 0,021 s z cache i 0,053 s bez niego. Nie przypisuje się pierwszego kosztu każdemu kolejnemu meczowi ani nie obiecuje takiego skrócenia całego workflow.

## PDF

| Dokument | Stan | Strony | Minimalna czcionka | SHA256 |
| --- | --- | --- | --- | --- |
| summary | PASS | 5 | 8.0 | 27cdc03466161e161c7b4e725992412bd6568efa7943085932a20f9d160821af |
| full_annex | PASS | 133 | 8.0 | e13d9f8b5f797789707f41600cbec438c2444096d8b3371f8b63d53612b7dfd2 |

Dostarczone PDF sprawdzono niezależnie PyMuPDF i pypdf; dokumenty mają numerację, polskie znaki, sekcje, instrukcję interpretacji oraz krótkie uzasadnienia wybranych obserwacji oparte na podanych prognozach i próbach. Jeżeli nie przekazano pliku, tabela jawnie pokazuje brak weryfikacji. Prognozy pozostają niekalibrowane i nie są potwierdzonymi okazjami bukmacherskimi.

## Pozostałe ograniczenia i przygotowane dalsze kroki

- Nieobsługiwane ligi i niejednoznaczne lub niepotwierdzone tożsamości pozostają w mianowniku i w rejestrze odrzuceń. Rozszerzenie wymaga zweryfikowanego źródła, kraju, ID i dostatecznej historii; nie wystarczy podobna nazwa drużyny.
- XGBoost pozostaje zablokowany jako model nietrenowany lub bez gotowego adaptera. Nie utworzono zastępczych prawdopodobieństw.
- Zachowano minima Elo 5 meczów drużyny, Dixon–Coles 30 meczów ligi i rynków zdarzeń 60 meczów ligi / 8 drużyny. Przykład Rodiny z dwóch obserwacji nie uzasadnia obniżenia progu Elo; status ostatniej kolejki wynika z jej rzeczywistych danych.
- Starsze rekordy bez zweryfikowanej daty meczu pozostają nierozliczone. Dane HG/AG są opisane jako full time, ale nie podają rzeczywistego końca meczu ani osobnego oznaczenia dogrywki; nie utożsamia się ich z gotowym rozliczeniem dowolnego regulaminu bukmachera.
- Źródło rosyjskie ma ograniczoną aktualność i zostało oznaczone przez dostawcę jako wycofywane. Daty ostatnich wyników w dostarczonym artefakcie podaje tabela historii poniżej; nie uzupełniano późniejszych wyników szacunkami.
- Nie wykonano niezależnego potwierdzenia całego światowego kalendarza, walidacji kalibracji poza próbą, potwierdzenia value/EV ani formalnego forward. Przed takimi zastosowaniami potrzebne są odrębne dowody, a nie zwiększenie samego pokrycia.
- Automatyczna retencja artefaktów Actions wynosi 30 dni. Do trwałego odtworzenia należy zachować oryginalny ZIP z podanym SHA256 i kod z SHA uruchomienia; samo ponowne pobranie dzisiejszego CSV nie odtworzy dawnego czasu obserwacji.

### Faktyczna historia według ligi

| Liga | Wyniki | Najwcześniejsza data | Ostatnia data |
| --- | --- | --- | --- |
| 2. Bundesliga | 1008 | 2023-07-28 | 2026-11-01 |
| Allsvenskan | 938 | 2023-04-01 | 2026-11-03 |
| Austrian Bundesliga | 645 | 2023-07-28 | 2026-11-01 |
| Brazilian Serie A | 1474 | 2023-04-15 | 2026-11-04 |
| Bundesliga | 990 | 2023-08-18 | 2026-11-01 |
| Championship | 1824 | 2023-08-04 | 2026-11-04 |
| Chinese Super League | 952 | 2023-04-15 | 2026-10-24 |
| Danish Superliga | 655 | 2023-07-21 | 2026-11-02 |
| Ekstraklasa | 1033 | 2023-07-21 | 2026-11-02 |
| Eliteserien | 924 | 2023-04-10 | 2026-11-01 |
| Eredivisie | 1017 | 2023-08-11 | 2026-11-01 |
| Irish Premier Division | 722 | 2023-02-17 | 2026-10-30 |
| J1 League | 1196 | 2023-02-17 | 2026-11-01 |
| Jupiler Pro League | 1025 | 2023-07-28 | 2026-11-04 |
| La Liga | 1249 | 2023-08-11 | 2026-11-02 |
| La Liga 2 | 1517 | 2023-08-11 | 2026-11-02 |
| League One | 1814 | 2023-08-05 | 2026-11-04 |
| League Two | 1820 | 2023-08-05 | 2026-11-03 |
| Liga MX | 1150 | 2023-07-01 | 2026-11-02 |
| Liga Profesional | 1745 | 2023-01-27 | 2026-11-03 |
| Ligue 1 | 999 | 2023-08-11 | 2026-11-02 |
| Ligue 2 | 1089 | 2023-08-05 | 2026-11-02 |
| MLS | 2078 | 2023-02-25 | 2026-11-02 |
| National League | 1845 | 2023-08-05 | 2026-10-31 |
| Premier League | 1230 | 2023-08-11 | 2026-11-02 |
| Premiership | 753 | 2023-08-05 | 2026-11-01 |
| Primeira Liga | 1008 | 2023-08-11 | 2026-11-02 |
| Romanian Superliga | 1069 | 2023-07-14 | 2026-11-02 |
| Russian Premier League | 740 | 2023-07-21 | 2026-08-02 |
| Scottish Championship | 604 | 2023-08-04 | 2026-10-31 |
| Scottish League One | 604 | 2023-08-05 | 2026-10-31 |
| Scottish League Two | 600 | 2023-08-05 | 2026-10-31 |
| Serie A | 1240 | 2023-08-19 | 2026-11-02 |
| Serie B | 1240 | 2023-08-18 | 2026-11-01 |
| Super League | 771 | 2023-08-18 | 2026-11-02 |
| Super Lig | 1118 | 2023-08-11 | 2026-11-02 |
| Swiss Super League | 758 | 2023-07-22 | 2026-11-01 |
| Veikkausliiga | 689 | 2023-04-05 | 2026-11-02 |

## Rejestr przebiegu i izolacja produkcji

Commity robocze: `6dd43aa` — wspólna identyfikacja i kontrola rynków; `581e951` — rozszerzenie historii o kolejne kraje; `3c2dc11` — domknięcie dostępnych dodatkowych źródeł; `703b533` — pełna obsługa obserwowanych kodów krajów oraz bezpieczny cache. Ostateczny SHA rzeczywiście użyty przez CI znajduje się w tabeli weryfikacji.

Problemy środowiska rozwiązano bez zmiany produkcji: początkowe połączenie z proxy wymagało jawnego dostępu sieciowego; niepełne odtworzenie plików przez API dało 59 braków plików i jeden błąd hasha fixture, po czym pełny klon przeszedł 1078 testów; instalację do katalogu tylko do odczytu zastąpiło lokalne venv. Nie zmieniano źródłowych fixture ani archiwów, aby ukryć te błędy.

W sprawdzonym diffie nie ma zmian w `tools/`, `config/`, `model/`, `data/`, `archive/`, natywnych raportach ani produkcyjnych workflow. Dopuszczony zakres to pakiet badawczy, jego testy, opcjonalny shadow Dixon–Coles, workflow badawczy i dokumentacja/artefakty naprawy. Nie wykonano merge do main, wdrożenia produkcyjnego ani zapisów obserwacji do N.

## Odtworzenie

1. Zachowaj oryginalny ZIP artefaktu i sprawdź jego SHA256 z tabeli. Rozpakuj go do osobnego katalogu; nie nadpisuj plików produkcyjnych.
2. Użyj kodu z SHA pełnego przebiegu i osobnego checkout bazy `f609427`. Zainstaluj izolowane zależności z `github_models/requirements.txt`.
3. Z archiwalnego `verified_results.json` wyodrębnij dawny zakres kodów E0/D1/I1/SP1/F1 bez zmiany rekordów i timestampów. Zachowaj pełną macierz jako wejście obu kodów wariantu „ta sama historia”.
4. Uruchom porównanie z dokładnym cutoff zapisanym w artefakcie. Następnie uruchom `verify_artifacts.py` oraz generatory PDF/tego raportu. To replay badawczy, nie nowy forward.

```bash
python -B -m github_models.coverage_comparison \
  --queue ARTIFACT/reports/github_models/queues/2026-11-06.json \
  --history ARTIFACT/data/github_models/verified_results.json \
  --events ARTIFACT/data/github_models/verified_events.json \
  --before-history OLD_SCOPE.json --baseline-root BASELINE_CHECKOUT \
  --as-of '2026-11-06T09:53:42.542940+00:00' --output coverage_comparison.json
```

Pełne powody odrzuceń i hashe wejść znajdują się w porównaniu JSON, trzech audytach wariantów i weryfikacji. Ten raport jest rejestrem badawczych zmian, a nie wpisem do produkcyjnego rejestru prognoz.
