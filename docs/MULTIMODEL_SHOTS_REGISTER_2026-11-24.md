# MultiModel V2 — strzały, start prac badawczych (24.11.2026)

Polecenie użytkownika: dołożyć **strzały ogółem** i **strzały celne**. Poprzedni warunek „dopiero po faulach i kartkach” zostaje zmieniony dla odizolowanych badań; blokady dyscyplinarne #84/#78 nadal obowiązują dla fauli i kartek.

## Stan PR przed kontynuacją
- [x] Zadanie #88 z kryteriami odbioru i zakazem fikcyjnych kursów.
- [x] Izolowany moduł `github_models/shots_research.py`: walidacja chronologii, IDs, definicji strzałów i braków; eksperymentalny baseline Poissona przy >=5 obserwacjach; filtr rzeczywistych archiwalnych kursów Superbet >=1,20; łączny mecz tylko z dwóch rzeczywistych stron.
- [x] Testy offline `tests/test_multimodel_shots_research.py` przygotowane. **CI i integracja produkcyjna niepotwierdzone**.
- [ ] Ustalić semantykę i niezależne publikowane źródła (PitchAPI / dane historyczne tylko read-only; żadnego API-Football jako nowego feedu). `stat_definition_verified=True` musi wynikać z dowodu, nie z założenia.
- [ ] Zbudować prawdziwy prematch pipeline snapshotów historycznych i prospektywnych (cutoff), kalibrację dystrybucji i statusy missing.
- [ ] Zmapować realne market IDs OddsPapi Superbet, scope (mecz/drużyna), line, period i wybór; **zero nowych płatnych API calls bez osobnej decyzji**.
- [ ] Użyć odrębnych prognoz strzałów w `SHADOW`, następnie po CI w istniejących **dwóch** PDF, nie dodawać trzeciego raportu.
- [ ] Prospektywne, niezależne rozliczenia i metryki Brier/log-loss na różnych meczach, holdout przed decyzją o promocji typu.

## Stałe ograniczenia
Nie zmieniamy A/B/C, ich wag, wcześniej zamrożonych N, historii prognoz ani filtrów. Poisson dla count jest **baseline badawczym**, nie skalibrowaną rekomendacją: nie wolno wystawiać PLAY, EV, ROI ani wartości kursowej na jego podstawie. Brak pokrycia / sprzeczna semantyka = brak prognozy. Historyczne wydarzenie rozegrane wcześniej, ale opublikowane później niż cutoff, jest niedostępne w przewidywaniu. Strzały celne nie są tożsame z xGOT; strzały ogółem nie są tożsame z golami.

## Kontynuacja PR #89

### Dane i chronologia

- PitchAPI daily z 12.10–22.11.2026: 37 zapisów, 1771 wierszy z 2962 dostępnych wg inwentarza, 1602 z kompletnym xG obu drużyn i 44 z błędem pobrania lub identyfikacji strzałów. Limit 75 spotkań dziennie i luki w datach wykluczają traktowanie tego zbioru jako kompletnego. Pola `shot_count` i `shots_with_xgot` zliczają zdarzenia i dostępność wartości xGOT. Archiwum nie zawiera typów zdarzeń, dowodu kompletności wszystkich prób ani rozdzielenia 90 minut od dogrywki. `shots_with_xgot` nie służy jako licznik strzałów celnych.
- PitchAPI prematch z 16.10–27.11.2026: 40 zapisów. Zawierają stemple czasu i historyczne próbki xG oraz identyfikatory meczów, bez odpowiednich liczników strzałów. Dla prognoz terminarz musi być zaobserwowany przed odcięciem. Dane daily służą wyłącznie do ustalenia tożsamości na innych ukończonych spotkaniach. Dostępność wymaga zarówno `observed_at_utc`, jak i znacznika commitu archiwum przed cutoffem.
- API-Football daily, backfill i international tylko z Git: 489 plików, 2444 wiersze. Odrzucono 58 wpisów z niepotwierdzonym pełnym okresem i 8 z rozbieżną wersją tego samego spotkania. Z 2370 unikalnych spotkań w pełnym okresie 1735 ma komplet potwierdzonych arytmetycznie liczników obu drużyn. 643 wiersze źródłowe nie miały kompletnych liczników dla żadnej strony. `Total Shots` zawiera celne, niecelne i zablokowane próby wg schematu archiwum. Walidacja wymaga `Shots on Goal + Blocked Shots <= Total Shots`, a liczba pozostałych prób wynika z różnicy. Mecze z dogrywką lub karnymi odpadają na podstawie zapisanej struktury wyniku. Dostępność licznika opiera się na czasie commitu zapisanego pliku i wskazaniu jego SHA. To przybliżenie czasu dostępności w archiwum, brak stempla pierwotnej publikacji u dostawcy.
- Dokładne dopasowanie obu drużyn, rozgrywek, wyniku i kickoff w granicy 15 minut dało 251 par oraz 169 dwukierunkowo jednoznacznych ID drużyn. W 223 z 251 par liczniki ogółem zgadzały się po obu stronach. Różnic z pozostałych 28 par nie interpretujemy jako konkretnej klasy zdarzenia. Brak dostatecznego dowodu równoważności PitchAPI, dostawcy archiwalnego i OPTA.
- Dla Superbet oficjalnym źródłem jest OPTA, następnie oficjalna strona organizatora. W OPTA celne obejmują gole z prób, obrony oraz wybicia ostatniego obrońcy z linii bramkowej. Zwykłe zablokowanie to osobna kategoria, a słupek lub poprzeczka bez gola zaliczają się do prób niecelnych. Porównanie prognoz z niezależnym źródłem liczy wyniki badawcze. [Superbet, komunikat 12/2024](https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122) · [Stats Perform, definicje zdarzeń](https://www.statsperform.com/opta-event-definitions/)

### Wdrożenie

- Dwie rodziny `shots_total` i `shots_on_target`, trzy zakresy `home`, `away`, `match`, Over/Under na jawnych liniach połówkowych. Średnia 5–10 ostatnich dostępnych obserwacji drużyny ze wszystkich boisk zasila rozkład Poissona, a dla meczu sumujemy obie średnie. Użycie sumy zakłada niezależność liczników stron. Ten uproszczony model pozostaje niekalibrowany.
- Zamrożenie używa faktycznego czasu pracy reportera i tych samych tożsamości z kolejki co raport A/B/C. Model sprawdza datę spotkania, stempel kolejki, identyfikatory, zakończenie i dostępność każdej historycznej obserwacji oraz wyklucza ten sam mecz. Ślad JSON zachowuje liczności, historie ze SHA, wyniki i przyczyny braków. Starszy replay z ustalonym cutoff ma osobną etykietę i nie wchodzi do prospektywnych metryk.
- Generator dołącza pełne listy strzałów i statusy niedostępności przy meczach. Skrót zawiera najwyżej trzy różne rodziny na mecz. W PDF audytu są zakresy z prognozą, liczba sprawdzonych ofert, rozliczone mecze, Brier i log loss. Techniczne JSON są oddzielnymi artefaktami, z dwoma PDF w istniejącym pakiecie.
- Weryfikacja cen korzysta wyłącznie z `collection.json` OddsPapi. Wymaga dokładnej tożsamości meczu i bukmachera, potwierdzonych ID rynku i wyniku, zakresu drużyna/mecz, okresu `fulltime`, strony, linii, rzeczywistego kursu >=1.20, stempla dostawcy i pobrania dostępnego przy zamrożeniu przed kickoff. Katalog pozycji o nazwie związanej ze strzałami jest audytowany. Bez potwierdzonej mapy kurs pozostaje niedostępny.
- Rozliczanie czyta wcześniejsze artefakty z tą samą selekcją i czasem publikacji przed kickoff. Wyniki po minimum 48 h są odczytywane z publicznych CSV Football-Data.co.uk dla obsługiwanych lig. Wymagana jednoznaczność kraju, ligi, kolejności klubów i daty lokalnej. Pola HS/AS i HST/AST są odrębne. Brak wyniku lub pokrycia pozostawia status oczekiwania albo niedostępności oraz puste metryki. Rozliczenia weryfikują prawdopodobieństwa wyłącznie względem niezależnych agregatów ligowych. [Opis pól CSV](https://www.football-data.co.uk/notes.txt)
- Odczyt Git, artefaktów GitHub i publicznych CSV nie uruchamia kolektora OddsPapi ani API-Football. Zachowano dotychczasowe dane A/B/C, zamrożenia i rejestry liczności. Kalibracja pozostaje wyłączona.

### Testy i blokery

- Wyjściowy zestaw PR #89: 7/7 testów. Po zmianach: 42/42 testy z grupy `test_multimodel*.py`; test źródłowy czyta Git i sprawdza cutoff oraz rzeczywiste porównania.
- Lokalna integracja z oryginalną kolejką run 45037233530 z 22.11 i odcięciem 15:45 UTC: 288 wierszy badawczych w 48 dostępnych zbiorach rodzina/zakres, 59 meczów w kolejce dnia. Odtworzenie na rzeczywistą datę 24.11 i cutoff 02:00 UTC: 0 wierszy z 48 meczów, głównie brak mapy drużyn dla niższych lig i blokery tożsamości Champions League. Badanie #88 biegnie niezależnie od #78 i #84.
- Brak prospektywnych archiwów strzałów opublikowanych przed kickoff i zakończonej niezależnej próby do pomiaru Brier/log loss. Brak potwierdzenia identycznej klasyfikacji strzałów między Football-Data.co.uk i OPTA, dlatego wynik audytu nie oznacza rozliczenia Superbet.
- Archiwa Actions odczytano w CI z użyciem uprawnień tylko do odczytu. Gdy brak zweryfikowanego rynku, ceny pozostają niedostępne.

- Pełna lokalna regresja: 674/674 testy. Pierwszy [przebieg CI strzałów](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324119639) potwierdził archiwa, odtworzył 168 prognoz przy rzeczywistym cutoff kolekcji i wykrył przesłonięcie zmiennej z metadanymi kursów w generatorze PDF. Poprawiono nazwę zmiennej. [Regresja reguł rynków](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324119627) przeszła.
- W kolekcji z 22.11 (run 45045069985) przejrzano 30 036 zapisanych ofert Superbet. 14 identyfikatorów strzałów to wyłącznie `playertotals-shots` i `playertotals-shotsongoal`, `period=result` z dogrywką. Zero dokładnych ofert na strzały drużyny lub meczu w okresie `fulltime`. Rynki zawodników pozostają poza zakresem.
- Druga [integracja GitHub Actions](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324349458) zakończyła się powodzeniem. W PDF z 22.11 są 119 istniejących pozycji A/B/C, 216 istniejących SHADOW i 168 prognoz strzałów (84 ogółem, 84 celne) przy odcięciu kolekcji 16:40:28 UTC. Powstały dwa otwieralne PDF. [Regresja reguł rynków](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324349141) przeszła. W kolejnej iteracji skompresowano powtarzające się statusy niedostępności w PDF przy zachowaniu wszystkich selekcji z prognozą.
- Kolekcja z 19.11 (run 44571730918) dała 44 748 ofert, w tym 8921 wpisów typu strzał zawodnika z dogrywką. Kolekcja 22.11 zawierała 1150 wpisów tego typu. Łącznie przejrzano 74 784 wiersze ofert w dwóch archiwach. Zero dokładnych pełnoczasowych rynków gospodarzy, gości lub meczu. Jest to wynik dla sprawdzonych kolekcji, z odnotowanym brakiem pokrycia tej części oferty.
- Weryfikacja jednostki na konkretnym meczu Liverpool–Manchester United, 22.11.2026, PitchAPI `m_4Pdd0e`: PitchAPI zapisało 28 i 10 zdarzeń z xGOT, zaś oficjalny raport klubu podaje 28 i 10 strzałów ogółem oraz 11 i 3 celne. Ewidencja dotyczy weryfikacji semantyki i nie zasila prognozy ani prospektywnych metryk. [Statystyki Liverpool FC](https://www.liverpoolfc.com/matches/mens-team/liverpool-v-manchester-united-english-premier-league-20261122?tab=live)

- [Końcowa integracja strzałów](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324633649) i [regresja reguł rynków](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324633688) zakończyły się powodzeniem dla kodu `c0f0741`. CI wykonało 42 testy MultiModel. Pakiet ma dwa PDF (25 i 2 strony) oraz techniczne JSON. Test PDF sprawdził sekcję Brier/log loss przy zerowej próbie, z pustymi wartościami i wyłączoną kalibracją. Lokalna pełna regresja: 674/674. [PDF i ślad odtworzenia](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324633649/artifacts/14888574114)


## Kontynuacja 24.11.2026 — polecenie „Zapisz w rejestr. I wykonuj kolejne kroki”

**Punkt kontrolny (stan przed nowymi poprawkami, PR #89):**
- GitHub Actions [45324633649](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324633649) — job `shots` SUCCESS, sprawdzony przez odczyt zadań Actions; źródłowy replay 22.11.2026: 168 pozycji (84 strzały ogółem, 84 celne), dwa otwieralne PDF. To **replay**, nie nowe prognozy z 24.11.
- GitHub Actions [45324633688](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45324633688) — job `market-rules` SUCCESS; część etapów opcjonalnego odczytu archiwum została SKIPPED, nie stanowi osobnego potwierdzenia ceny strzałów.
- Rejestr Codexa podaje 674/674 testów lokalnych i 42/42 testy MultiModel w CI. Samo CI potwierdza sukces testów MultiModel, nie niezależny prospektywny hit-rate.
- Historyczne archiwa OddsPapi z 19 i 22.11: 74 784 wpisy, **zero** dokładnych pełnoczasowych ofert na strzały drużyn i całego meczu. Nie zmieniać tego statusu na kursy dostępne.
- Próba 24.11 o cutoff 02:00 UTC: **0 wygenerowanych pozycji dla 48 meczów**, przede wszystkim brak potwierdzonych przejść identyfikatorów drużyn i blokady tożsamości; nie mylić z negatywną oceną skuteczności.
- Na `main` brak jeszcze modułu strzałów; PR #89 pozostaje osobną gałęzią. Bez przejścia nowych testów i prospektywnego run nie scalać.
 
**Plan kolejnych kroków, bez rozszerzania ryzyka:**
1. Jawne raportowanie `shots` na produkcyjnym workflow: nawet jeżeli strzały zawiodą, dwa dotychczasowe PDF mają wyjść, ale wynik podzadania ma zostać odnotowany jako WARNING/DEGRADED w artefakcie technicznym i podsumowaniu Actions (bez fałszywego SUCCESS modułu).
2. Diagnostyka brakujących powiązań PitchAPI→legacy na poziomie drużyny i meczu, rozróżnienie: `unverified_prematch_fixture`, `unverified_team_crosswalk`, `insufficient_history`, `fixture_already_started`; brak automatycznej identyfikacji na podobieństwie nazw.
3. Testy regresyjne dla braku zamrożenia, brakującego audytu, archiwalnego replay oraz statystyk dostępności. Wymagać CI PASS.
4. Po CI: niepromowanie do PLAY; dalsza walidacja źródłowa i zbieranie prospektywnych prognoz po osobnej decyzji o merge. Kalibracja dopiero po niezależnym rozliczeniu.
