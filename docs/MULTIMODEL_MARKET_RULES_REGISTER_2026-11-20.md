# MultiModel V2 — rejestr zasad rynków i plan ich rozliczania

**Ustalenie użytkownika:** 20.11.2026, Europe/Warsaw. Celem jest bezpieczne poszerzenie analiz fauli, kartek i handicapów bez zatrzymywania A/B/C i SHADOW. **Nie zmieniamy prawdopodobieństw, progów modeli ani wag**, dopóki kalibracja nie zostanie potwierdzona na prospektywnych wynikach.

## Kontrola stanu zastanego

Działające elementy: A/B/C; SHADOW BTTS i handicap ±1,5; zapisywanie zamrożonych prognoz i kursów Superbet; 2 końcowe PDF na dzień; konserwatywne dopasowywanie wybranych rynków. Istnieją `oddspapi_integration.py`, `oddspapi_market_gaps.py`, `shadow_superbet.py`, `shadow_audit.py` i `market_settlement.py`. Nie dublować ich bez konieczności.

Z rzeczywistego archiwum OddsPapi z 20.11.2026 (76 pobranych snapshotów, 48 915 zapisanych ofert) stwierdzono:
- **4 186** ofert `Over Under Player Fouls Committed (incl. overtime)` — dotyczą zawodników, nie liczby fauli całego meczu.
- **353** ofert `Bookings - Over Under Full Time` — nie wolno utożsamiać jednostek *bookings* z liczbą żółtych kartek bez niezależnej weryfikacji.
- **430** ofert `Asian Handicap` dla całego meczu i **636** ofert `European Handicap` dla całego meczu — brak potwierdzonego mapowania znaku, strony i warunków zakładu w API. Europejski rynek trzydrogowy nie jest równoznaczny z handicapem azjatyckim.
- W audycie luk: **137/137** analiz fauli i **117/117** analiz kartek bez zgodnych zweryfikowanych kursów Superbet. Nie zastępować braków innymi rynkami.

To stan jednej historycznej migawki, a nie gwarancja obecnej dostępności każdego rynku.

## Zmiany zaprogramowane w bieżącym PR

- `github_models/market_rule_gate.py` — samodzielna klasyfikacja nazwy, rodzaju, okresu, linii, strony, typu zawodnik/mecz, ceny i źródła; audyt **tylko odczyt** rzeczywistych ofert. Każdy przypadek fauli, bookingów i handicapu otrzymuje jawny kod blokady; żaden nie jest automatycznie promowany do rekomendacji lub rozliczenia.
- Funkcja `settle_half_goal_handicap` — matematyczny test warunku wygranej przy półbramkowej linii i określonej drużynie; **nie jest dowodem znaczenia znaku z OddsPapi**.
- `tests/test_multimodel_market_rule_gate.py` — regresje: faul zawodnika ≠ faule całego meczu, booking ≠ żółta kartka, europejski ≠ azjatycki handicap, pierwsza połowa ≠ cały mecz, kurs <1,20 odrzucony, wynik po rozpoczęciu meczu niedopuszczalny.
- `.github/workflows/multimodel-market-rules.yml` — automatyczne testy i audyt niezmienionych plików `collection.json` / `market_gaps.json` po każdym udanym procesie OddsPapi; zero płatnych zapytań API. Wynik to techniczny JSON `MARKET_RULES_AUDIT.json` (bez tworzenia trzeciego PDF dla użytkownika).
- `github_models/unified_output.py` — sekcja „Kontrola zgodności rynków Superbet” w **istniejącym** pliku `MULTIMODEL_AUDYT_YYYY-MM-DD.pdf`; drugi plik z prognozami pozostaje niezmieniony.
- Nie zmieniamy obliczeń p, wag A/B/C, oryginalnych raportów SHADOW, zamrożonego archiwum ani zapisanych kursów.

## Przyjęta kolejność dalszych prac

| Krok | Zadanie | Status | Kryterium zakończenia |
|---|---|---|---|
| 1 | Inwentaryzacja faktycznych rynków OddsPapi/Superbet | **WDRAŻANY** | Codzienny JSON nazw/identyfikatorów/okresów/linii i powodów braku dopasowania |
| 2 | Jednoznaczny słownik rynku: zakres mecz/zawodnik, czas, linia, strona, reguła, jednostka | **WDRAŻANY W TRYBIE BLOKUJĄCYM** | Brak nieudokumentowanego utożsamiania różnych rynków |
| 3 | Weryfikacja fauli PitchAPI kontra oficjalna statystyka rozliczeniowa Superbet | **DO POTWIERDZENIA ZE ŹRÓDEŁ** | Próbka identycznych meczów, id i statystyk; zapis danych i przyczyn różnic |
| 4 | Kartki i handicap: żółte/czerwone/bookings oraz strona i znak azjatycki/europejski | **TESTY I BLOKADY WDRAŻANE** | Zweryfikowane przykłady rzeczywistych ofert i rozliczeń (bez domysłów) |
| 5 | Testy historyczne i brzegowe reguł | **WDRAŻANE** | Unittest przechodzi; remis, graniczna linia, gospodarze/goście, karty i brak danych bez błędu |
| 6 | Rozliczanie prospektywnych prognoz po faktycznych wynikach | **ISTNIEJE, ROZSZERZENIE PO KROKACH 3–5** | Wpis wynik/hit lub jawne `pending`/`unresolved`, bez fałszywych porażek |
| 7 | Dwa raporty PDF z czytelnym statusem i ograniczeniami | **DODAWANY STATUS W AUDYCIE** | Raport prognoz + raport audytu, bez trzeciego użytkowego PDF |
| 8 | Kontrolne GitHub Actions, regresje i zachowanie budżetu API | **WDRAŻANE** | CI PASS, brak awarii A/B/C, zero nowych płatnych wywołań OddsPapi |
| 9 | Prospektywne próbki per rynek i identyczny koszyk meczów | **ZBIERANE** | Od pierwszych 20–30 rozliczeń diagnostyka, od min. ~100 niezależnych spotkań formalny przegląd; liczność per kategoria adekwatna |
| 10 | Kalibracja na niezależnym holdoucie i ewentualna zmiana modelu | **NIE URUCHAMIAĆ AUTOMATYCZNIE** | Poprawa Brier/log loss i kalibracji na niewykorzystanych do dopasowania spotkaniach, dokumentacja rollback |

## Zasady bezpieczeństwa i kontroli jakości

1. Jedynie polski Superbet — STS niedostępny w obecnej subskrypcji. Zachowujemy limit OddsPapi 200/250 i rezerwę 50.
2. Minimum rzeczywistego kursu **1,20**. Nie generować nieistniejących cen.
3. **67/100 nie jest obowiązkowym progiem punktowej oceny jakości**; nie utożsamiać z p=67%.
4. `SHADOW` pozostaje wyraźnie eksperymentalny. Brak właściwych danych nie blokuje A/B/C, ale blokuje automatyczne uznanie zakładu za sprawdzony.
5. Jeśli źródło nie pozwala rozstrzygnąć wyniku, status `pending` albo `unresolved`, z uzasadnieniem, a nie „przegrany”.
6. Nie udostępniać wycenionego handicapu z OddsPapi przed potwierdzeniem konwencji znaku i strony po stronie danego bukmachera.
7. Promocja modelu do produkcji i zmiana wag wymagają odrębnego przeglądu, nie wynikają automatycznie z zebrania 100 meczów.
8. Zachować 2 pliki PDF. Do ich wygenerowania używać tylko identycznych zamrożonych migawek.

## Źródła reguł — oficjalne dokumenty do dalszej weryfikacji

- Faule i kartki: https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r
- Źródła i zasady rozliczenia statystyk: https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122
- Wyjaśnienie handicapu azjatyckiego przez Superbet: https://support.superbet.pl/hc/pl-pl/articles/360018422859-Handicap-azjatycki-co-to-jest

Dokumenty opisują zasady bukmachera; **nie dowodzą**, że konkretne pola `handicap`/`market_type`/ `bookings` w OddsPapi znaczą to samo. Weryfikacja techniczna jest oddzielnym krokiem.

## Warunki wdrożenia

- [x] PR z testami i kodem scalony do `main` (PR #70 i #71–#74).
- [x] GitHub Actions z testami i rzeczywistym archiwum przechodzi pomyślnie (19 testów, replay 200 ofert).
- [x] W audycie końcowym istnieją dwa poprawne PDF; brak trzeciego raportu dla użytkownika.
- [x] Raport wyraźnie odróżnia badawcze handicapy od zweryfikowanych wypłat bukmachera; kartki i faule pozostają zablokowane.

## Potwierdzenie wdrożenia produkcyjnego — 20.11.2026

- **PR #70 scalony do `main`:** https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/70
- **Regresje + analiza rzeczywistego archiwum: PASS** https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44728416499
  - 11/11 testów bezpieczeństwa zakończonych powodzeniem.
  - 48 915 ofert w 76 migawkach skontrolowanych bez wywołań OddsPapi.
  - 4 186 ofert fauli **zawodników**; **0** dopasowanych w tej migawce ofert fauli **całego meczu**.
  - 1 311 ofert szerokiej grupy bookings/kartki (różne okresy i drużyny, nie jest to 1 311 ofert żółtych kartek pełnego meczu).
  - 430 ofert azjatyckich handicapów pełnego meczu; 1 888 ofert europejskiego handicapu łącznie z okresami innymi niż cały mecz.
  - **0** niezweryfikowanych rynków automatycznie promowanych do rozliczenia.
- **Dwa końcowe PDF-y: PASS** https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44728416352
  - `MULTIMODEL_2026-11-20.pdf` — 10 stron; `MULTIMODEL_AUDYT_2026-11-20.pdf` — 1 strona (dodatkowy stan bezpieczeństwa rynków).
  - Automatyczny artefakt: `multimodel-final-two-pdfs`.
  - Zgodne zamrożone źródła, **0** dodatkowych płatnych wywołań, bez zmian wag modeli.
- **Etap I częściowo wykonany:** inwentaryzacja nazw, zakresów i blokad w codziennym CI. Zgodność statystyki fauli PitchAPI i jednostek kartek z regulaminem oraz konwencje linii i strony OddsPapi **jeszcze niepotwierdzone**.
- **Etap II częściowo wykonany:** regresje i bezpieczne raportowanie PASS, lecz rozszerzenie rzeczywistego rozliczenia fauli/kartek/handicapów pozostaje zablokowane do czasu potwierdzenia reguł i historii wyników.
- **Etap III oczekuje na dane:** brak wystarczającej prospektywnej próbki per rynek do formalnej kalibracji; nowo wygenerowane prawdopodobieństwa SHADOW nie mogą być uznane za skalibrowane.

Ostatnie sprawdzenie potwierdza sprawność kodu audytu i publikacji, **nie potwierdza** poprawności ani opłacalności żadnego niezweryfikowanego typu.

## Weryfikacja merytoryczna źródeł — 20.11.2026, kolejna faza

### 1. Faule — weryfikacja zgodności

**Wymaganie bukmachera:** Superbet w komunikacie dotyczącym piłki nożnej stwierdza, że do rozliczenia fauli bierze pod uwagę wyłącznie przewinienia odgwizdane przez sędziego, wyłączając akcje zakończone przywilejem korzyści. W osobnym komunikacie (widoczna treść 29.04.2026) potwierdza oficjalne statystyki **OPTA** jako główne źródło rozliczenia statystycznego:
- https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r
- https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122

**Weryfikacja danych MultiModelu:** `github_models/event_parser.py` w gałęzi `codex/multimodel-v2` importuje z `football-data.co.uk` kolumny `HF`/`AF`. W lokalnym odczycie zapisanego artefaktu `github-models-v2-abc-complete-44703910677-1` stwierdzono 25 571 rekordów statystyk `verified_events.json`; dostawca wszystkich rekordów to `football-data.co.uk`, nie udokumentowany zbiór OPTA. **Brak wspólnej próby zdarzeń z potwierdzonymi statystykami OPTA**, dlatego nie da się dziś wiarygodnie obliczyć zgodności liczbowej tego źródła z zasadami Superbet. `match_fouls` pozostaje bez statusu `bookmaker_settlement_verified`; nie podmieniamy fauli zawodnika na faule meczu.

**Wynik:** zasadę Superbet i pochodzenie statystyk zweryfikowano; **równoważności liczbowej nie potwierdzono**. Warunek dalszego uruchomienia: niezależne zakończone mecze z OPTA i `football-data.co.uk` identyczną datą, drużynami, periodem i statystyką, plus udokumentowane różnice.

### 2. Kartki — odrębne jednostki

Komunikat Superbet rozdziela:
- żółte kartki (jednostki żółtych; z wyłączeniem sztabu/rezerwowych/po gwizdku i szczegółowymi zasadami przerwy);
- łączną liczbę kartek z przeliczeniem: żółta **1**, bezpośrednia czerwona **2**, wykluczenie za drugą żółtą **3**;
- punkty kartkowe: żółta **10**, druga żółta/czerwona **25**, limit **35 punktów na zawodnika**, z dodatkowymi wyłączeniami.

Historyczne kolumny `HY`/`AY` z `football-data.co.uk` to liczba **żółtych kartek**, a nie `bookings` ani punkty kartkowe; brak zdarzeń czerwonych i informacji o uczestnikach/czasie potrzebnych do pozostałych jednostek. Sam `market_name="Bookings - Over Under Full Time"` i `market_type="totals-bookings"` z OddsPapi **nie określa pewnie sposobu punktacji** dla Superbet.

**Wynik:** definicje jednostek rozdzielono, automatyczne `cards ↔ bookings` nadal zablokowane. Do zamknięcia: uzyskać konkretne, oficjalnie rozliczone przykłady rynku `Bookings` z identyfikatorami oraz pełnymi zdarzeniami.

### 3. Azjatyckie handicapy ±1,5 — zweryfikowany znak

Dokumentacja producenta OddsPapi potwierdza, że pole `handicap` w katalogu jest linią **gospodarzy**, `outcome_name="1"` to gospodarze, a `"2"` to goście:
- https://oddspapi.io/blog/asian-handicap-calculator-python/
- https://oddspapi.io/us/docs/get-markets

Zatem:
- `Asian Handicap`, `spreads`, `fulltime`, `handicap=-1.5`, outcome `1` ↔ gospodarze **−1,5**;
- te same dane outcome `2` ↔ goście **+1,5**;
- `handicap=+1.5`, outcome `1` ↔ gospodarze **+1,5**, outcome `2` ↔ goście **−1,5**.

W migawce `collection.json` z 20.11.2026 oba wyniki `1`/`2` występują dla jednakowego `market_id`. Ścisłe dopasowanie zapisanej prognozy SHADOW i kursu `>=1,20` daje **114** dopasowanych pozycji w **43** meczach (wyłącznie archiwalne kursy do badań, nie rekomendacje).

**Wynik:** tożsamość i matematyczne warunki linii ±1,5 zweryfikowane źródłem operatora danych i kontrolą archiwum. Europejskie handicapy `spreads-european` i inne linie pozostają osobnymi, nieobsługiwanymi rynkami. Rzeczywiste rozliczenie u bukmachera nadal wymaga przykładowego kuponu/wypłaty; model używa niezależnego wyniku i nie udaje potwierdzenia Superbet.

### 4. Implementacja prospektywnego rozliczania tylko potwierdzonych kategorii

- **`github_models/priced_shadow_settlement.py`**: połączenie zamrożonych prognoz `BTTS Full Time` i `Asian Handicap ±1.5 Full Time` z realnymi cenami, pod warunkiem tożsamości meczu, katalogu, strony, znaku, czasu publikacji przed kickoff oraz kursu **>=1,20**. Wszystkie inne rynki wykluczone. Brak odpytywania OddsPapi.
- Niezależny resolver `github_models.shadow_audit.settle_one` weryfikuje wynik według **rzeczywiście dostępnych po meczu** danych; brak finalnego wyniku daje `pending`/`unresolved`, nie automatyczne przegranie. Zwracane `hit/Brier` i symulowana stopa zwrotu z zapisanej ceny to **badanie**, nie rzeczywista wypłata u bukmachera.
- W nocnym `.github/workflows/oddspapi-audit.yml` do istniejącego pobrania niezależnych zakończonych wyników dodano replay kursów na zgodnych, niemodyfikowanych archiwach SHADOW. Publikacja jako `PRICED_SHADOW_SETTLEMENT.json` w **technicznym** artefakcie `oddspapi-rolling-audit`, bez trzeciego PDF.
- `github_models/unified_output.py`: pierwsza strona ma jednoznacznie oznaczone archiwalne kursy AH/BTTS, audyt jako drugi PDF pokazuje liczbę rozliczonych i nierozliczonych. Zachowuje układ **dwóch** dokumentów.
- `tests/test_priced_shadow_settlement.py`: brak mapowania fauli/kartki, testy znaku handicapu, pełnego okresu, ceny minimum, źródła, rozbieżności dat i brak udawanych rozliczeń.

### Status wykonania etapów po tej zmianie

| Krok | Wynik | Nadal niezbędne |
|---|---|---|
| 1. Rynki | Skatalogowane istniejące oferty i znaki AH | Monitorować zmiany katalogu |
| 2. Definicje | Rozdzielone mecz/zawodnik, okres, jednostka, AH home/away | Uzupełniać nowe rynki dopiero z dowodem |
| 3. Faule | Oficjalna zasada i źródło `HF/AF` potwierdzone | **Brak porównania tej samej próby z OPTA** |
| 4. Kartki/AH | Jednostki rozdzielone, znak AH ±1,5 potwierdzony | **Brak oficjalnych próbek wypłat bookings** |
| 5. Testy | Nowe testy regresyjne w PR | CI na main i weryfikacja archiwów |
| 6. Rozliczanie | Kod automatycznego replay BTTS/AH z final score | Potwierdzić pierwszy przebieg; brak oficjalnych payoutów |
| 7. PDF | Dokładne ceny AH w głównym PDF i opis rozliczeń w audycie | Weryfikować pierwszy produkcyjny artefakt |
| 8. Workflow | Dodany replay do nocnego audytu, bez API | Potwierdzić pierwszy przeprowadzony run |
| 9. Próba | Archiwizacja i deduplikacja cen, statusy finalne | Zebrać niezależne zakończone mecze |
| 10. Kalibracja | **Nie włączona** | Dane z >=100 niezależnych meczów + poprawa na holdoucie |

Ten wpis jest rejestrem implementacji i stanu wiedzy. Nie oznacza automatycznej zgody na promowanie SHADOW lub na przekazywanie niesprawdzonych kursów fauli i kartek.

## Kontrola końcowa i stan potwierdzony — 20.11.2026 (po PR #71–#73)

**Decyzja operacyjna:** wdrożono rozliczanie wyłącznie niezależnych wyników rynków `BTTS Full Time` i `Asian Handicap ±1,5 Full Time`, przyporządkowanych do rzeczywiście zapisanych ofert Superbet. W publikacjach pozostaje etykieta **SHADOW / badawcze / niekalibrowane**. Nie nastąpiła promocja modeli, wag lub fauli/kartek.

### Zmiany scalone

- PR **#71** — źródłowo udokumentowany znak handicapów OddsPapi + deduplikacja archiwów i rozliczanie po rzeczywistym wyniku, testy: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/71
- PR **#72** — prawidłowe rozpoznanie pola dostawcy w `collection.json` (`OddsPapi`) przy odrębnym `oddspapi-v4` dla snapshotów: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/72
- PR **#73** — poprawne ograniczenie siedmiodniowego archiwum kursów do bieżącej daty każdego PDF: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/73
- Kontrolę zakończenia wykonano w CI, z udokumentowanymi dwoma błędami pośrednimi PDF na `main` i następczymi poprawkami; **nie traktować starych czerwonych runów jako aktualnej awarii**.
- Korektę opisową PDF (w tym usunięcie sprzecznego komunikatu o niepotwierdzonym znaku AH) scalono w PR #74.

### Dowody z GitHub Actions

- [Regresja #71 — 19/19 testów PASS](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44732720862).
- [Nowy nocny audyt rynków — PASS](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44732878148): 9 zamrożonych archiwów odds w istniejącym audycie, 1 archiwum można było bezpiecznie połączyć z odpowiednią zamrożoną prognozą SHADOW; odrzucono pozostałe 9 plików, dla których nie znaleziono unikalnego identycznego archiwum SHADOW (brak dopasowania **nie** oznacza przegranej).
- Z tego audytu: **200** unikalnych wycenionych pozycji badawczych z **43** meczów = **86 BTTS** + **114 handicapów ±1,5**. Wszystkie mają `status=pending`, **0 `settled`**, brak liczonych hit rate/Brier/ROI z przyszłych wyników. `PRICED_SHADOW_BROKEN_GATES=0`, dodatkowe zapytania OddsPapi **0**.
- [Dwa końcowe PDF-y — PASS](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44733417657): w raporcie 20.11 jest **65** spotkań, **98** unikalnych propozycji A/B/C i **144** SHADOW; **29** pozycji z rzeczywistą zapisaną ceną, w tym **12** cen AH (i 8 BTTS w komplecie SHADOW dla tej daty). Wygenerowano **tylko 2 PDF**: prognozy 10 stron i audyt 2 strony; bez zmian historycznych danych.

### Rezultat weryfikacji fauli i kartek

**Faule — NIEZATWIERDZONE DO ROZLICZENIA JAKO SUPERBET:** oficjalne kryterium faulu i OPTA zostały odnalezione, a pochodzenie źródła `HF/AF` z `football-data.co.uk` potwierdzono. **Nie istnieje w archiwum druga, wspólna próba oficjalnych wyników OPTA**, zatem brak jest rzetelnego dowodu równoważności; rynki fauli zawodnika nie są rynkami fauli meczu.

**Kartki — NIEZATWIERDZONE DO ROZLICZENIA JAKO SUPERBET:** oficjalne jednostki żółte / czerwone / łączna liczba kartek / punkty kartkowe są rozdzielone, `HY/AY` to tylko żółte karty. Nadal brak danych czerwonych kart oraz graczy i godzin kartek do rekonstrukcji wypłaty dla `bookings`.

**Handicapy — ZATWIERDZONO TYLKO TOŻSAMOŚĆ RYNKU, NIE WYPŁATĘ BUKMACHERA:** home-line, outcome `1`/`2`, podział na azjatycki i europejski potwierdzony dokumentacją operatora; matematyczne rozliczenie ±1,5 bazuje na niezależnym końcowym wyniku. Bez kuponu/wyciągu Superbet nie nazywać tego oficjalnym rozliczeniem przez bukmachera.

### Zadania otwarte, według priorytetu (stan po odczycie ostatniego audytu)

1. **[BLOCKER FAULE]** Uzyskać rzeczywiste, zgodne identyfikatorowo statystyki OPTA dla tej samej próby spotkań co `HF/AF` i opublikować zestawienie różnic; do tego czasu brak wyceniania/rozliczania statystycznego fauli jako Superbet.
2. **[BLOCKER KARTKI]** Udokumentować dokładną jednostkę `Bookings - Over Under Full Time` w Superbet/OddsPapi i wyjaśnić czerwone, drugie żółte, rezerwowych oraz kartki po gwizdku, przed dodaniem jakiejkolwiek ceny do propozycji kartek.
3. **[BLOCKER WYPŁATA]** Potwierdzić rzeczywistym zakończonym kuponem rozliczanie ±1,5 oraz BTTS w Superbet (kod nie sugeruje wypłaty).
4. **[CZAS]** Zebrać rozliczone niezależnie wyniki meczów z 20.11 i dni późniejszych, odświeżać archiwum z cenami; obecnie 0 `settled`, nie wyliczać ROI ani kalibracji.
5. **[CI]** Obserwować kolejne cykle dzienne i nocne, w szczególności zmienność źródeł `OddsPapi`/`oddspapi-v4`, zgodność kolejnego PDF po aktualizacji oraz częściowy terminarz 25–26.11.
6. **[HISTORIA]** Zwiększać liczbę poprawnie powiązanych zamrożonych archiwów SHADOW; starszych 9 archiwów odds nie można automatycznie potraktować jako zgodnych prognoz SHADOW.
7. **[DANE]** Zweryfikować możliwość pozyskiwania historycznych statystyk strzałów, strzałów celnych i spalonych, bez wymyślania danych.
8. **[KALIBRACJA]** Po pierwszych 20–30 niezależnych wynikach tylko diagnostyka; formalny przegląd od ~100 różnych rozliczonych spotkań i reprezentatywnej liczby na rynek, a zmiana wag dopiero po poprawie na niezależnym holdoucie.
9. **[PRODUKT]** STS nadal niedostępny w subskrypcji, a dodatkowego harmonogramu e-mail z PDF nie ustanowiono; aktualny system utrzymuje wyłącznie 2 artefakty PDF dziennie.

Wyniki historyczne A/B/C w audycie, szczególnie dla `fouls` i `cards`, są statystykami badań `football-data.co.uk`; **nie stanowią potwierdzonego rozliczenia bukmacherskiego OPTA/Superbet**.

## Weryfikacja źródłowa OPTA i Bookings — 21.11.2026

Status: **częściowe potwierdzenie empiryczne, bez promocji rynków do rozliczenia produkcyjnego**.

### OPTA: oficjalne źródło i pierwsza próba porównawcza

- Superbet, komunikat obowiązujący od 29.04.2026: OPTA jest podstawowym źródłem statystyk bukmacherskich, z określonymi wyjątkami i źródłami zastępczymi. https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122
- Superbet, komunikat obowiązujący od 16.12.2025: rozliczenie fauli tylko odgwizdanych (bez przywileju korzyści), szczegółowe zasady kartek. https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r
- Premier League oficjalnie potwierdza, że dostawcą jej statystyk meczowych jest Opta/Stats Perform: https://www.premierleague.com/en/stats/clarification
- Football-data podaje zróżnicowane źródła statystyk (BBC, ESPN i inne), nie gwarantuje jednej definicji dla całego zbioru: https://football-data.co.uk/data
- W dokumentacji kolumn HF/AF, HY/AY, HR/AR i HBP/ABP opisano różnice księgowania żółtych kartek w rozgrywkach angielskich/szkockich i europejskich; HFKC/AFKC obejmują więcej przewinień niż faule. Nie zastępować HF/AF przez HFKC/AFKC. https://www.football-data.co.uk/notes.txt

Porównanie wykonane ręcznie na rzeczywistym zapisanym pliku `data/github_models/verified_events.json` z artefaktu A/B/C run 44703910677, SHA-256: `5f8dc727c4b8941e4927614d61556d6bba11091fd04030de00350d5bd855e63a`. Zbiór zawiera 25 571 rekordów, w tym 1240 z kodem E0.

| Data | Mecz | ID źródłowe w archiwum | HF/AF | OPTA faule | HY/AY | OPTA żółte |
|---|---|---|---|---|---|---|
| 2026-01-24 | Bournemouth–Liverpool | 2526:E0:226 | 7/7 | 7/7 | 1/1 | 1/1 |
| 2026-01-24 | Fulham–Brighton | 2526:E0:224 | 10/6 | 10/6 | 1/1 | 1/1 |
| 2026-01-24 | Manchester City–Wolves | 2526:E0:225 | 16/14 | 16/14 | 1/3 | 1/3 |

Oficjalne strony odpowiednio:
- https://www.premierleague.com/en/match/2562115/bournemouth-vs-liverpool/stats
- https://www.premierleague.com/en/match/2562121/fulham-vs-brighton-hove-albion/stats
- https://www.premierleague.com/en/match/2562122/manchester-city-vs-wolverhampton-wanderers/stats

Dodatkowa kontrola samej sumy fauli: Newcastle–Liverpool, 25.08.2025, archiwum 2526:E0:21: 17+15=32; oficjalny artykuł Premier League podaje 32 faule: https://www.premierleague.com/es/news/4391961/newcastle-united-2-liverpool-3-august-2025-is-another-classic-premier-league-match

Wynik: 3/3 zgodności fauli i żółtych kartek po obu stronach; dodatkowo zgodna suma fauli w czwartym meczu (4/4 sumy fauli). Próba mała, nielosowa, wyłącznie Premier League, trzy mecze bez czerwonych kartek. Nie potwierdza pełnej zgodności wszystkich lig, sezonów ani oficjalnej wypłaty Superbet. Poprzedni zapis o całkowitym braku porównania OPTA jest od tej chwili nieaktualny: istnieje pierwsza ręczna próba źródłowa. Nadal brak zweryfikowanych ofert fauli całego meczu z poprzedniej migawki OddsPapi.

### Bookings: identyfikatory potwierdzone, przelicznik Superbet niepotwierdzony

Przeanalizowano rzeczywisty `collection.json` z 20.11.2026 09:14 UTC, SHA-256 `7229787d090e83365949bc1a0b38885c95f1666202354f7934b284e84f00bacb`. Dla superbet.pl znaleziono 353 zapisane ceny w 53 meczach, w rodzinie `Bookings - Over Under Full Time` / `totals-bookings`:

| Linia | market_id | Liczba zapisanych cen |
|---|---|---:|
| 0.5 | 10914 | 1 |
| 1.5 | 10918 | 4 |
| 2.5 | 10922 | 60 |
| 3.5 | 10926 | 104 |
| 4.5 | 10930 | 104 |
| 5.5 | 10934 | 62 |
| 6.5 | 10938 | 18 |

Skala jest charakterystyczna dla liczby kartek, nie standardowych punktów 10/25, ale sama nie dowodzi sposobu liczenia wykluczeń. Superbet rozróżnia żółte kartki, łączną ważoną liczbę kartek (1/2/3) oraz punkty (10/25, limit 35). Dokumentacja katalogu OddsPapi opisuje pola, nie zawiera specyficznego dla Superbet przelicznika bookings. https://oddspapi.io/en/docs/get-markets

Odkryto endpoint `GET /v4/settlements`, który zwraca WIN/LOSE/PUSH/HALFWIN/HALFLOSS/CANCELLED/UNDECIDED dla fixtureId, marketId, outcomeId i playerId. https://oddspapi.io/us/docs/get-settlements . Nie przyjmuje parametru bookmaker, więc sam nie dowodzi wypłaty Superbet. Jest płatny (1 wywołanie z limitu), https://oddspapi.io/us/docs/requests-and-quota . Nie wywoływano go w tej weryfikacji.

### Następne kryteria i decyzja

1. Poszerzyć próbę OPTA/football-data do co najmniej 30 różnych meczów wstępnie, z czasem do 100, z różnych kolejek/lig i przypadkami czerwonych oraz drugich żółtych kartek; podawać per-team i per-match różnicę oraz zgodność progów.
2. Uzyskać pisemne potwierdzenie od OddsPapi/Superbet, czy IDs 10926/10930 oznaczają ważoną liczbę kartek 1/2/3 w superbet.pl. Alternatywą jest porównanie rzeczywiście rozliczonych ofert badawczych na meczach z dyskryminującymi czerwonymi kartkami.
3. Wynik z `/v4/settlements` przechowywać oddzielnie od rzeczywistego statusu wypłaty bukmachera; przed użyciem sprawdzić `/v4/account`, nie przekraczać 200/250.
4. Do czasu tych dowodów pozostawić blokady fauli/kartek, bez zmiany A/B/C, wag, prawdopodobieństw i dwóch PDF. Brak ceny i brak danych to nie przegrana. Nowe płatne wywołania: 0.

## Rozszerzenie weryfikacji OPTA oraz pilotaż Settlements — 21.11.2026

### Porównanie dodatkowych dziewięciu meczów z tym samym archiwum verified_events.json

Wartości w tabeli podano gospodarz/gość. Źródło w kolumnie ID to publiczna strona statystyk Premier League; liga deklaruje Opta jako dostawcę. Dane historyczne odczytano z archiwum A/B/C run 44703910677. Próba celowo obejmuje mecze z czerwonymi kartkami, nie stanowi losowej reprezentacji wszystkich lig.

| Data | Mecz | Rekord FD | Faule FD / OPTA | Żółte FD / OPTA | Czerwone OPTA | ID strony PL |
|---|---|---|---|---|---|---|
| 2024-11-09 | Crystal Palace – Fulham | 2425:E0:103 | 10:11 / 10:11 | 1:1 / 1:1 | 1:0 | 2444573 |
| 2025-09-20 | Man United – Chelsea | 2526:E0:47 | 13:14 / 13:14 | 0:5 / 0:5 | 1:1 | 2561941 |
| 2025-10-25 | Brentford – Liverpool | 2526:E0:86 | 7:10 / 7:10 | 3:2 / 3:2 | 0:0 | 2561978 |
| 2026-01-01 | Liverpool – Leeds | 2526:E0:189 | 10:8 / 10:8 | 0:2 / 0:2 | 0:0 | 2562080 |
| 2026-01-01 | Sunderland – Man City | 2526:E0:191 | 9:6 / 9:6 | 1:1 / 1:1 | 0:0 | 2562083 |
| 2026-01-18 | Aston Villa – Everton | 2526:E0:220 | 15:13 / 15:13 | 1:2 / 1:2 | 0:0 | 2562105 |
| 2026-02-07 | Newcastle – Brentford | 2526:E0:249 | 14:18 / 14:18 | 2:2 / 2:2 | 0:0 | 2562143 |
| 2026-02-08 | Brighton – Crystal Palace | 2526:E0:250 | 12:9 / 12:9 | 1:3 / 1:3 | 0:0 | 2562137 |
| 2026-03-05 | Tottenham – Crystal Palace | 2526:E0:292 | 14:14 / 14:14 | 3:2 / 3:2 | 1:0 | 2562183 |

Źródła:
- https://www.premierleague.com/en/match/2444573/crystal-palace-vs-fulham/stats
- https://www.premierleague.com/en/match/2561941/manchester-united-vs-chelsea/stats
- https://www.premierleague.com/en/match/2561978/brentford-vs-liverpool/stats
- https://www.premierleague.com/en/match/2562080/liverpool-vs-leeds-united/stats
- https://www.premierleague.com/en/match/2562083/sunderland-vs-manchester-city/stats
- https://www.premierleague.com/en/match/2562105/aston-villa-vs-everton/stats
- https://www.premierleague.com/en/match/2562143/newcastle-united-vs-brentford/stats
- https://www.premierleague.com/en/match/2562137/brighton-hove-albion-vs-crystal-palace/stats
- https://www.premierleague.com/en/match/2562183/tottenham-hotspur-vs-crystal-palace/stats

Łącznie z poprzednią próbą: 13/13 zgodnych sum fauli, w tym 12/12 meczów z porównaniem obu drużyn (24/24 wartości) i 12/12 zgodnych żółtych kart (24/24 wartości). Trzy mecze z czerwonymi kartkami (cztery wykluczenia). Przypadek Manchester United–Chelsea pokazuje, że Opta wykazuje 0 żółtych dla gospodarzy mimo wykluczenia Casemiro po drugiej żółtej. To istotne dla rozróżnienia HY/AY, liczby kartek oraz punktów kartkowych. Nie utożsamiać wyłącznie sumy żółtych z ważoną jednostką łącznej liczby kartek. W próbie nie weryfikowano wypłaty Superbet. Pozostało minimum 17 meczów do bramki 30 oraz inne ligi i przypadki kartkowe. Otwieranie niektórych publicznych stron PL zwracało wyłącznie szkielet strony; takich spotkań nie dopisano do liczników.

### Pilotaż /v4/settlements: ograniczenia i plan

- Najnowszy audyt 44850299149, 21.11.2026 01:32 UTC: 200 wycenionych prognoz SHADOW, 180 pending, 20 unresolved, 0 settled, dwa dopasowane archiwa i 200 duplikatów. Nie liczyć trafności/ROI; brak niezależnych wyników nie oznacza przegranej.
- Najnowszy zapis OddsPapi 44776156677: limit 250; 58 wykorzystanych przed pobraniem, 4 wywołania tego procesu. To stan historyczny, nie bieżące saldo.
- Z archiwum wybrano cztery oddzielne fixtureId z pełnoczasowymi liniami Bookings: Barnsley–Sheffield Wednesday, Guingamp–Rodez, Red Star–Pau i Hellas Verona–Cesena (20.11.2026). Nie twierdzimy, że w tych czterech meczach wystąpiły czerwone kartki; ich zdarzenia muszą zostać potwierdzone niezależnie.
- Dodano `github_models/bookings_settlement_pilot_20261121.py` i jednorazowy workflow `multimodel-bookings-pilot-20261121.yml`. Sprawdza aktualny bezpłatny account i dopuszcza maksymalnie 4 płatne próby, przy limicie min(200, request_limit-50); współdzieli blokadę concurrency z kolektorem, nie ma harmonogramu ani automatycznego ponawiania. Nie ujawnia klucza ani odpowiedzi account. Odczytuje tylko 7 znanych linii Bookings z powiązanej migawki Superbet; zapisuje wynik WIN/LOSE itd. oraz przedział/ewentualnie jednoznacznie wyliczoną liczbę jednostek dostawcy.
- Settlements nie przyjmuje parametru bookmaker; dane rozliczeń dostawcy zachowujemy oddzielnie od oficjalnej wypłaty Superbet. https://oddspapi.io/en/docs/get-settlements ; https://oddspapi.io/us/docs/requests-and-quota
- Brak automatycznego odblokowania Bookings/fauli, bez zmian modeli, dwóch głównych PDF, limitu 1,20 i braku obowiązkowej oceny punktowej 67/100. Wyniki pilotażu zostaną dopisane po otrzymaniu odpowiedzi API; na ten moment nie uznajemy go za wykonany.

### Rozszerzenie próby do 32 meczów — dalszych 19 porównań, 21.11.2026

Dane archiwalne `verified_events.json` (run 44703910677) vs oficjalna Premier League. Pary gospodarz/gość, poniżej wartości identyczne w obu źródłach; czerwone to licznik OPTA (nie wypłata bukmachera). Każda strona statystyk jest identyfikowalna po numerze meczu w oficjalnej domenie `premierleague.com/en/match/<ID>/<slug>/stats`.

| Data | Mecz | Rekord FD | Faule | Żółte | Czerwone OPTA | ID PL |
|---|---|---|---|---|---|---|
| 2025-02-12 | Everton – Liverpool | 2425:E0:241 | 9:20 | 2:2 | 1:1 | 2444613 |
| 2025-05-25 | Man United – Aston Villa | 2425:E0:376 | 10:10 | 2:2 | 0:1 | 2444844 |
| 2024-12-26 | Liverpool – Leicester | 2425:E0:178 | 17:5 | 3:2 | 0:0 | 2444644 |
| 2025-01-18 | Newcastle – Bournemouth | 2425:E0:211 | 7:18 | 1:6 | 0:0 | 2444687 |
| 2025-01-15 | Arsenal – Tottenham | 2425:E0:208 | 16:9 | 3:1 | 0:0 | 2444670 |
| 2025-02-15 | Leicester – Arsenal | 2425:E0:243 | 9:10 | 2:1 | 0:0 | 2444714 |
| 2024-12-01 | Chelsea – Aston Villa | 2425:E0:128 | 21:6 | 2:2 | 0:0 | 2444592 |
| 2025-04-16 | Newcastle – Crystal Palace | 2425:E0:321 | 9:15 | 2:3 | 0:0 | 2444758 |
| 2024-12-26 | Man City – Everton | 2425:E0:171 | 5:10 | 1:4 | 0:0 | 2444645 |
| 2025-04-20 | Leicester – Liverpool | 2425:E0:330 | 11:7 | 1:2 | 0:0 | 2444796 |
| 2025-01-18 | Leicester – Fulham | 2425:E0:213 | 8:8 | 3:1 | 0:0 | 2444685 |
| 2024-05-02 | Chelsea – Tottenham | 2324:E0:348 | 12:16 | 0:1 | 0:0 | 2367792 |
| 2024-03-09 | Bournemouth – Sheffield United | 2324:E0:271 | 12:11 | 3:5 | 0:0 | 2367808 |
| 2024-03-02 | Everton – West Ham | 2324:E0:261 | 9:6 | 1:2 | 0:0 | 2367800 |
| 2023-09-30 | Bournemouth – Arsenal | 2324:E0:62 | 11:10 | 0:1 | 0:0 | 2367598 |
| 2024-02-24 | Aston Villa – Nottingham Forest | 2324:E0:252 | 7:16 | 1:2 | 0:0 | 2367790 |
| 2023-09-16 | Wolves – Liverpool | 2324:E0:41 | 10:4 | 1:3 | 0:0 | 2367587 |
| 2023-09-24 | Brighton – Bournemouth | 2324:E0:57 | 12:17 | 3:3 | 0:0 | 2367590 |
| 2023-08-12 | Arsenal – Nottingham Forest | 2324:E0:3 | 12:12 | 2:2 | 0:0 | 2367540 |

**Wynik łączny:** 32/32 zgodnych sum fauli; 31/31 meczów z danymi obu drużyn (62/62 wartości); 31/31 zgodnych sum żółtych i 62/62 wartości per drużyna. Trzy sezony: 2023/24, 2024/25, 2025/26; 5 meczów z czerwonymi w statystyce OPTA i 7 zarejestrowanych czerwonych. Pierwsza bramka 30 meczów przekroczona. Próba wygodnościowa, tylko Premier League; nie dowodzi zgodności innych lig ani oficjalnego rozliczenia Superbet. Kolejna bramka: reprezentatywna próba między ligami, 100 meczów, ocena rozbieżności per próg. Nie odblokowywać ryczałtowo rynku fauli (brak odpowiadających ofert całego meczu) lub kartek na podstawie tej próby.

**Przypadek krytyczny:** 12.02.2025 Everton–Liverpool: statystyka OPTA pokazuje czerwone 1:1, ale oficjalny raport Premier League potwierdza, że obie kartki zawodnicy otrzymali po końcowym gwizdku, a kartki po zakończeniu i sztabu są wyłączone z rozliczania Superbet. https://www.premierleague.com/en/news/4237353 ; https://www.premierleague.com/en/match/2444613/everton-vs-liverpool/stats ; https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r . To rzeczywisty kontrprzykład dla automatycznego przeliczania sumy YC/RC bez osi czasu. Wciąż potrzebna rekonstrukcja zdarzeń, nie tylko sumy żółtych i czerwonych.

**Pilotaż:** PR #75 scalony; run 44880735020 ukończył raport, ale druga natychmiastowa kontrola bezpłatnego `account` zwróciła HTTP 429; 62/250 w pierwszym odczycie, 0 prób płatnych, nie uzyskano danych settlements. Naprawa PR #76: jedna kontrola rezerwuje maksymalnie 4 próby pod wspólną blokadą kolektora, odstępy 3 s, kontrola końcowa, stop przy 401/403/429. Dokumentacja cooldown: account 1000 ms, settlements 2000 ms. Drugi jednorazowy run 44880815830, wynik do odczytania. Brak zmian w modelach i harmonogramie.

## Kontrola po pilotażu Settlements i odtwarzalność próby OPTA — 21.11.2026, godz. ok. 16:00 Europe/Warsaw

### Wynik faktycznie wykonanych wywołań OddsPapi (nie mylić PASS workflow z sukcesem danych)

- **Pierwszy jednorazowy run** [44880735020](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44880735020): zakończył workflow sukcesem, ale sam test zatrzymał się przy `http_429` na odczycie `account`. `attempted_billable_calls=0`; brak nowych danych Bookings.
- **Drugi jednorazowy run** [44880815830](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44880815830): odczyt konta **62/250** (limit operacyjny 200), wykonano **4 płatne wywołania** `GET /v4/settlements?fixtureId=...&playerId=0` na zakończonych spotkaniach z zapisanym rynkiem `Bookings - Over Under Full Time`. Wszystkie cztery zwróciły **HTTP 500**:
  - Barnsley – Sheffield Wednesday: `id1000002472341382`;
  - Guingamp – Rodez: `id1000018272037454`;
  - Red Star – Pau: `id1000018272037464`;
  - Hellas Verona – Cesena: `id1000005373093090`.
- Końcowy odczyt konta: **66/250**; stan dotyczy zakończenia testu, nie jest gwarancją bieżącego salda.
- Wniosek: **0 odpowiedzi rozliczeniowych**, **0 potwierdzonych jednostek Bookings**, brak danych potwierdzających faktyczne wypłaty Superbet. `workflow success` oznacza jedynie bezpieczne zachowanie artefaktu diagnostycznego.
- Dokumentacja dostawcy: `/v4/settlements` ma chłodzenie **2000 ms**, a HTTP 500 oznacza błąd wewnętrzny. Pomoc techniczna jest właściwym kolejnym krokiem po powtarzalnych 500. https://oddspapi.io/us/docs/get-settlements ; https://oddspapi.io/es/docs/errors . Może istnieć problem dostępności danych tuż po zakończeniu meczu, ale na tej podstawie nie wolno rozstrzygać przyczyny.
- Nowa ochrona w `github_models/bookings_settlement_pilot_20261121.py`: **natychmiastowy STOP przy pierwszym 5xx**, 401/403/429, bez ponawiania i wydawania czterech kolejnych jednostek. Dotychczasowy jednorazowy workflow nie otrzymuje nowego harmonogramu ani kolejnego wywołania; testy są bezpłatne.
- Dokumentacja `GET /v4/settlements` nie wymaga `playerId=0`, jest parametrem opcjonalnym. **Do wyjaśnienia u dostawcy**: czy `playerId=0` dla rynku zespołowego jest obsługiwane oraz czy settlements działa dla wymienionych meczów w chwili zapytania. Nie testować alternatywy kosztem kolejnych zapytań bez nowej przesłanki.

### Ustrukturyzowane źródła i automatyczny test OPTA

Zarejestrowano `research/multimodel/opta_fd_benchmark_20261121.json` — **31** par gospodarz/gość (dokumentowane obserwacje z publicznych stron Premier League / Opta) odpowiadających źródłowym `source_record_id` z `data/github_models/verified_events.json`. Czwarty, odrębny typ dowodu to mecz Newcastle–Liverpool, gdzie wcześniejszy rejestr potwierdzał wyłącznie sumę fauli — nie wprowadzamy fałszywych danych per drużyna.

Dodano `github_models/opta_fd_reconciliation.py`, `tests/test_opta_fd_reconciliation.py` i `.github/workflows/multimodel-opta-crosscheck.yml`: test przetwarza autentyczny plik `verified_events.json` z **run 44703910677**, odporny na powtórzone ID i brakujące rekordy. Raport techniczny pokazuje osobno różnice fauli i żółtych kartek; nie jest to nowa niezależna kontrola wszystkich ręcznie podanych wartości OPTA, nie jest dowodem na oficjalne rozliczenie Superbet.

Na koniec dnia wynik GitHub Actions powinien zostać odnotowany poniżej, z numerem run i liczbą rozbieżności, zamiast z góry deklarować PASS.

### Priorytety po obecnej weryfikacji

1. Nie uruchamiać ponownie płatnego endpointu `settlements` w tym samym stanie bez wyjaśnienia serwerowych HTTP 500. Przygotować dla dostawcy cztery `fixtureId`, czasy, parametry bez klucza i identyfikatory linii `Bookings`; uzyskać informację, czy `playerId=0` jest obsługiwane.
2. Utrzymać rozdzielenie `bookings` od żółtych, czerwonych i punktów kartkowych — brak rozliczonego kuponu, brak jednostki.
3. Rozszerzać próbę OPTA **poza Premier League**, zachować per-team wartości, okres i zdarzenia po końcowym gwizdku. Próba 32 jest wygodnościowa; nie usprawiedliwia wdrożenia w innych ligach.
4. Obserwować nowe rzeczywiście zakończone mecze w SHADOW; na końcu oddzielać kursy historyczne od rzeczywistych wygranych i nie włączać kalibracji automatycznie.

### Wynik automatycznego odtworzenia archiwum — 21.11.2026, 15:09 UTC

- [GitHub Actions run 44917662068](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44917662068) **SUCCESS**; 6/6 testów poprawności, brak płatnych wywołań OddsPapi.
- Bezpośrednio porównano **31** zapisanych w benchmarku ręcznie zweryfikowanych par gospodarzy/gości z rzeczywistym niezmienionym plikiem `verified_events.json` z archiwum run 44703910677: **0 różnic fauli** i **0 różnic żółtych kartek**.
- Liczba 32 w wcześniejszym rejestrze obejmuje również **jedno dodatkowe porównanie tylko sumy fauli** Newcastle–Liverpool. Nie dodawać go do licznika par, bo nie mamy w tej samej tabeli obu oddzielnych wartości.
- Rezultat niezależnego sprawdzenia **spójności danych z archiwum**, nie pozyskanie 31 nowych wartości OPTA, i w żadnym przypadku nie potwierdzenie jednostki `Bookings` u Superbet.
- Techniczny artefakt `multimodel-opta-fd-archive-crosscheck` zawiera `OPTA_FD_RECONCILIATION.json` z parami źródłowymi i różnicami; 2 główne PDF nie uległy zmianie.

### Zakończenie bieżącej realizacji i odczyt końcowy — 21.11.2026

- **PR #77 scalony do `main`**: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/77
- **Ostateczny workflow na głównej gałęzi: PASS** https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44917754853 — 31 par z zamrożonego archiwum, 0 rozbieżności fauli i żółtych, bez wywołań OddsPapi. Odrębna 32. obserwacja nadal dotyczy tylko sumy fauli.
- **Zewnętrzna przeszkoda**: cztery HTTP 500 z API OddsPapi; brak skutecznych `Settlements`. Utworzono [issue #78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78) z czterema identyfikatorami, godzinami UTC, pytaniem o `playerId=0`, katalog i jednostki Bookings. Nie wysłano wiadomości do dostawcy; zgłoszenie do wsparcia jest oddzielnym krokiem otwartym.
- **Nie przeprowadzono** kolejnych płatnych wywołań po pilotażu; ostatni widoczny stan 66/250 pochodzi z godz. 07:34 UTC, nie jest bieżącym odczytem.
- **Otwarta lista po ponownym przeglądzie:** (1) dostawca musi wyjaśnić 500/Book­ings i dane wypłat; (2) analiza fauli poza Premier League, z niezależnym licencjonowanym źródłem OPTA; (3) uzupełnienie danych zdarzeń czerwonych/po gwizdku przed przelicznikiem kartek; (4) kolejne niezależnie rozliczone prognozy SHADOW; (5) dopiero kalibracja na odpowiednio dużej próbie.
- **Utrzymane blokady:** nie utożsamiać `Bookings` z HY/AY, nie utożsamiać HF/AF ze wszystkimi źródłami OPTA, nie nazywać statusu OddsPapi oficjalną wypłatą Superbet. Model A/B/C i SHADOW, dwa PDF, minimalny rzeczywisty kurs 1,20, próg punktowy 67/100 nieobowiązkowy — bez zmian.


## Potwierdzenie i eskalacja Bookings do OddsPapi — 21.11.2026

- Wysłano z połączonego konta Gmail wiadomość do zweryfikowanego oficjalnego adresu pomocy `support@oddspapi.io`; temat: **OddsPapi v4 /settlements — four HTTP 500 errors and Superbet Bookings settlement-unit clarification**.
- Poproszono o potwierdzenie: sposobu obliczania `Bookings - Over Under Full Time` dla Superbet (żółte, czerwona bezpośrednia, wykluczenie po drugiej żółtej), wyłączeń kartek sztabu/rezerwowych/po gwizdku, prawidłowości `playerId=0` w `/v4/settlements`, przyczyny czterech odpowiedzi HTTP 500 oraz wpływu tych błędów na wykorzystany limit.
- Zgłoszenie powiązano z [issue #78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78), komentarz ID `7064746778`; **czekamy na stanowisko źródłowe**. Nie ujawniono API key.
- Oficjalna dokumentacja endpointu określa `playerId` jako **opcjonalny**, a `500 INTERNAL_ERROR` jako błąd po stronie dostawcy mogący wystąpić nawet dla prawidłowego żądania: https://oddspapi.io/us/docs/get-settlements i https://oddspapi.io/fr/docs/errors .
- Dostawca potwierdza rodzinę rynków `Bookings – Over Under Full Time`, ale publiczna dokumentacja nie podaje dokładnego sposobu liczenia zdarzeń dla konkretnego Superbet; nie wywodzić rozliczenia tylko z nazwy rynku: https://oddspapi.io/blog/corners-cards-odds-api/ .
- **Status techniczny:** `Bookings` niezatwierdzone do oficjalnego rozliczania; brak nowych płatnych testów, modeli A/B/C, SHADOW, limitu ceny 1,20 i dwóch PDF nie zmieniano. Po odpowiedzi sprawdzić jej treść, uzupełnić mapowanie jednostek i testy rozliczania tylko dla potwierdzonych zdarzeń.

## Diagnoza rozliczania historycznych SHADOW — 21.11.2026, kolejny przegląd

**Wniosek:** bazowy moduł `github_models.shadow_audit.settle_one`, `github_models.priced_shadow_settlement.settle_quotes`, `github_models.settlement.matching_outcomes` i automatyzacja auditów **istniały już wcześniej**. Nie należy przepisywać ich od podstaw. Główny problem zaobserwowany dzisiaj to **zbyt wczesne oznaczanie brakującego źródła jako `unresolved`**, a nie potwierdzone błędne dopasowanie meczu.

### Udokumentowane dane wejściowe

1. Faktycznie pobrano artefakt `oddspapi-rolling-audit` z udanego runu [44850299149](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44850299149), z datą audytu **2026-11-21T01:32:26Z**. Plik `PRICED_SHADOW_SETTLEMENT.json`: **200 wycenionych prognoz** w **43** meczach; **180 `pending`**, **20 `unresolved`**, **0 `settled`**. Wszystkie 20 mają `reason=no_exact_final`, dotyczą dokładnie **czterech** spotkań z 20 listopada (Red Star–Pau, Guingamp–Rodez, Verona–Cesena, Barnsley–Sheffield Wednesday). Pozostałe 180 występują w meczach z 21, 22 i 24 listopada, które w chwili audytu jeszcze się nie rozpoczęły.
2. Niezależny `source_manifest.json` z tego samego uruchomienia raportuje **88/88 udanych pobrań** piłkarskich CSV, 4 sezony **2023/24–2026/27**. Brak rozliczenia nie wynika z całkowitego braku sezonu 2026/27.
3. Z osobnego późniejszego archiwum modelu (run [44918574707](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44918574707)) pobrano `data/github_models/verified_results.json` utworzony 21.11 o 15:22 UTC: **42 472** rekordy, **0** rekordów dopuszczonych do rozliczenia z datą **20.11.2026**.
4. Przyczyna: importer `github_models.public_results.parse_csv` jawnie odrzuca rekordy, dla których `completed_bound = match_date (00:00 UTC) + 2 dni` nie nastąpiło przed czasem obserwacji. Jest to świadome zabezpieczenie przed przedwczesnym wykorzystaniem lub przyjęciem wyników i uniemożliwia rozliczenie 20 listopada już 21 listopada. Najwcześniejsza granica dla daty **20.11** wynosi **22.11.2026 00:00 UTC**; źródło CSV musi ponadto faktycznie zawierać zakończony mecz. Nie wnioskujemy z tego, że 22.11 na pewno będą wyniki.
5. Historyczny `REPLAY_AUDIT.json` w tym samym 01:31 UTC runie ma odrębnie **727** unikalnych zapisanych cen A/B/C: 674 przyszłe, 53 nierozstrzygnięte i 0 rozliczonych. Nie sumować tego z 200 SHADOW — to różne populacje.

### Zmiany naprawcze

- `github_models/priced_shadow_settlement.py`: po próbie uzyskania prawdziwego niezależnego wyniku, jeśli `no_exact_final` występuje przed upływem bezpiecznego **48-godzinnego bufora od rozpoczęcia**, nadajemy status **`pending`** i jawny powód `independent_result_publication_grace_48h`. Jest to wyłącznie etykieta diagnostyczna: kod nadal próbuje rozliczyć prawdziwy dostępny wynik **od razu**, niezależnie od bufora. Po buforze brak dokładnego wyniku pozostaje `unresolved/no_exact_final`, a błędy identyfikacji nie są maskowane.
- Nowe zagregowane pola `status_reason_counts` i `distinct_fixtures_by_status` w technicznym `PRICED_SHADOW_SETTLEMENT.json` pozwalają odróżnić oczekiwanie na publikację od rzeczywistej nieweryfikowalności. Nazwa schematu zostaje bez zmiany i starsze czytniki mogą pominąć te nowe pola.
- `tests/test_priced_shadow_settlement.py`: test udowadnia relabel 20.11 przy audycie 21.11 oraz zachowanie `unresolved` po buforze; istniejący test wcześniej potwierdził obliczenia z realnego wyniku.
- `github_models/unified_output.py`: drugi użytkowy PDF wyświetla osobno liczbę oczekujących z 48-godzinnego bufora i ostrzeżenie, że bazowe SHADOW może nadal oznaczać opóźnione wyniki jako `unresolved`.
- `.github/workflows/oddspapi-audit.yml`: rozszerzenie wyzwalacza na zmiany kodu klasyfikacji, aby po scaleniu odświeżyć audyt realnymi CSV bez nowych zapytań do OddsPapi.

### Granice potwierdzenia i następne działania

- [ ] Potwierdzić **CI na `main`** dla nowych testów i automatycznego audytu; zapisać numer runu i wynik, nie dopisywać go z góry.
- [ ] Po następnej publikacji CSV (najwcześniej 22 listopada dla 20 listopada) sprawdzić, czy 4 zakończone spotkania rozliczają się niezależnie; jeśli nie, zebrać dokładne przyczyny `unresolved` i dopiero wtedy naprawiać mapowanie drużyn / krajów / dat.
- [ ] Przeanalizować osobno 53 nierozstrzygnięte pozycje A/B/C z `REPLAY_AUDIT`, z tym samym uwzględnieniem daty publikacji, bez mieszania ich z SHADOW.
- [ ] Wydzielić ewentualnie późniejszy status `source_lag` także w bazowym module SHADOW, ale dopiero po testach w jego **odrębnej** gałęzi. Nie zmieniać nieprzetestowanych źródeł zamrożonych prognoz i nie ruszać wag.
- [ ] Utrzymać osobny problem `Bookings`/OPTA — nie ma związku z brakiem finalnych bramek w terminie 48 h.
- [ ] Kalibracja nadal wymaga niezależnie rozliczonych meczów; statusy `pending` i `unresolved` nie są ani trafieniami, ani przegranymi.

**Stabilne zasady:** dwie końcowe PDF, minimalny faktyczny kurs 1,20, brak obowiązkowego filtra punktowego 67/100, żadnych fikcyjnych kursów lub ROI, brak zmian wag i prognoz produkcyjnych. Wprowadzona poprawka nie kosztuje żadnych dodatkowych jednostek OddsPapi.

### Wdrożenie klasyfikacji opóźnionych wyników — 21.11.2026, 18:11 UTC

- **PR #79 scalony do `main`**: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/79
- Testy regresyjne na gałęzi [44934084567](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934084567): **21/21 PASS**. W pierwszym podejściu [44934035001](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934035001) test ujawnił nadpisywanie powodu `independent_result_publication_grace_48h` przez `no_exact_final`; poprawiono `setdefault('reason',...)` i udokumentowano pomyślny ponowny przebieg.
- Po scaleniu GitHub uruchomił na `main` trzy zadania: test zgodności rynków [44934125602](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125602), dwa raporty PDF [44934125551](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125551), niezależny nocny audyt z archiwów [44934125549](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125549). Ich końcowy status wymaga osobnej weryfikacji; nie traktować samego startu jako PASS.
- W `priced_shadow_settlement` zaktualizowano wyłącznie diagnostyczne statusy 20 nierozliczonych prognoz z czterech meczów 20 listopada, pod warunkiem że wynik nie jest jeszcze dostępny. Żaden wynik nie został dopisany, nie zmieniła się trafność, nie wyliczano nowego ROI.
- Pozostałe trudniejsze zadania (53 nierozstrzygnięte wpisy A/B/C z wcześniejszego `REPLAY_AUDIT`, wyniki po zakończeniu 48-godzinnej ochrony, przeliczniki `Bookings`, pozostałe ligi) nadal są otwarte i wymagają odrębnych dowodów.

### Wyniki testów po scaleniu — 21.11.2026, 18:11 UTC

- [GitHub Actions 44934125602](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125602): **SUCCESS na `main`**, 21/21 regresji, analiza 19 449 rzeczywiście zapisanych ofert rynku, wszystkie bramki bezpieczeństwa PASS.
- [GitHub Actions 44934125551](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125551): **SUCCESS na `main`**, dokładnie dwa PDF: prognozy (18 stron) i audyt (2 strony), dzień 21.11, 68 meczów, 170 A/B/C, 288 SHADOW, 3 ceny bez dopisywania kursów; nowe opisy nie łamią generatora.
- Niezależny przegląd `oddspapi-audit` [44934125549](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934125549) został uruchomiony automatycznie po zmianie kodu; wynik powinien być oceniony oddzielnie, nie wliczać uruchomionego zadania jako ukończonego.
- Kluczowe: **nie ma nowych wygranych ani przegranych do wyliczenia z daty 20.11 na dzień 21.11** w konserwatywnym źródle niezależnym. Same oznaczenia pending/no_exact nie podnoszą skuteczności modelu i nie zmieniają zbioru prognostycznego.

## Etapy 1–5 wykonane równolegle — 23.11.2026, przegląd i wdrożenie audytu

Zakres: **MultiModel repo `kb-score-model`**, nie KB Score 3.0. Ostatni potwierdzony przed zmianami audyt: [GitHub #45090939091](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45090939091), 23.11 godz. 00:50–01:08 UTC. Wynik wyjściowy: SHADOW **501 wycenionych typów / 108 meczów**, 481 `pending`, **20 `unresolved:no_exact_final` z czterech meczów 20 listopada**, 0 `settled`. A/B/C replay: **1330 unikalnych wycenionych pozycji**, 657 `pending_future`, 673 `unresolved` (568 `no_exact_verified_outcome`, 105 `no_verified_final_yet`), 0 `settled`. To **dwie różne próbki**, nie sumować ich.

### 1. Niezależne wyniki i naprawa przepływu SHADOW

Znaleziono i udokumentowano cztery faktycznie zakończone mecze:
- **Red Star–Pau 2:1**: oficjalny [raport Red Star](https://www.redstar.fr/2026-11-21/les-pros/red-star-fc-pau-2-1/), wtórnie FBref. Uwaga: część agregatorów podawała 1:1; wybrano potwierdzony raport klubu i zgodny wynik FBref, nie wpis z niezweryfikowanego agregatora.
- **Guingamp–Rodez 1:3**: raport [Centre Presse](https://www.centrepresseaveyron.fr/sports/resultats-sportifs/football/ligue-2/rencontre/548038/guingamp-rodez) oraz FBref.
- **Hellas Verona–Cesena 0:2**: [Lega B](https://www.legab.it/seriebkt/calendario/2026-2027/stagione-regolare/12) i [oficjalny raport Verona](https://www.hellasverona.it/news/serie-bkt-2026-27-al-bentegodi-passa-il-cesena?cat=669).
- **Barnsley–Sheffield Wednesday 1:2**: [EFL](https://www.efl.com/news/2026/november/20/lowe-double-sees-sheffield-wednesday-win-at-barnsley/) i [oficjalny raport Sheffield Wednesday](https://www.swfc.co.uk/news/2026/november/20/report---barnsley-v-wednesday-/).

Rejestr dowodów: `data/github_models/independent_final_evidence_2026-11-20.json` — wynik, dokładne źródła URL, niezmienne `fixture_id`, kraj, liga, natywne identyfikatory drużyn i kickoff z zamrożonego PitchAPI. Skrypt `github_models/independent_final_score_bridge.py` potwierdza zgodność z oryginalnym archiwum, wymaga dwóch różnych domen i zakończenia spotkania, porównuje istniejące niezależne wyniki pod kątem sprzeczności, a **czas pierwszego odczytu ustala na moment wywołania**. Źródła dodawane są **wyłącznie do późniejszego audytu, nigdy do historycznego wejścia prognoz**. W archiwum znajdują się izolowane przebiegi smoke bez identyfikatorów drużyn: nie są dowodem tożsamości i są pomijane; rozbieżne kompletne rekordy są blokowane. Brak domniemanej wypłaty bukmachera.

### 2. Naprawa rozliczania cen A/B/C bez przepisywania modelu

Zachowano kod oryginalnego `github_models.oddspapi_replay_audit`, `market_settlement`, `shadow_audit` i zamrożone kursy. W `.github/workflows/oddspapi-audit.yml` źródło z czterema dokładnie zweryfikowanymi wynikami jest dodawane **po pobraniu niezależnych CSV**, następnie jeden replay A/B/C i SHADOW wykorzystuje tę samą rzeczywistą historię. Umożliwia to matematyczne rozliczenie wyłącznie obsługiwanych rynków (1X2/gole, BTTS i azjatycki handicap ±1,5) dla poprawnie dopasowanego spotkania; faule i kartki bez pełnej zgodności pozostają zablokowane.

Błędy początkowe rozdzielone: (a) wyniki zakończonych spotkań niewidoczne w źródłowym CSV, (b) rynki bez potwierdzonej jednostki, (c) opóźnione publikacje, (d) przyszłe spotkania. Oznaczeń `pending`/`unresolved` nie wolno uznawać za przegrane. Prawdopodobieństwa i pierwsze ceny przedmeczowe pozostają identyczne.

### 3. OddsPapi / Bookings — dalsza kontrola

23.11 sprawdzono połączony Gmail pod kątem odpowiedzi `from:support@oddspapi.io after:2026/11/20`: **brak otrzymanej odpowiedzi**. Otwarte [issue #78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78) dokumentuje cztery płatne HTTP 500 oraz pytania o jednostkę `Bookings` i `playerId=0`. Nie wykonano nowych płatnych zapytań. **Bookings, faul zawodnika/meczu, OPTA/Superbet payout — nadal niepromowane**. Kolejny test API dopiero po potwierdzeniu przez dostawcę, z budżetem i bez automatycznego ponawiania błędów 5xx.

### 4. Rozszerzenie OPTA poza Premier League — rzeczywisty poziom dowodu

Poprzedni audyt [44917754853](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44917754853) potwierdził zgodność archiwum z **31 odnotowanymi parami Premier League**, 0 rozbieżności. To nie dowód dla innych lig. Sprawdzono obecnie źródła oficjalne Serie B (Lega B, Hellas Verona), Ligue 2 (Red Star), League One (EFL). Oficjalny komunikat Hellas Verona jawnie przypisuje statystyki przedmeczowe `Opta – Stats Perform` (https://www.hellasverona.it/en/news/serie-bkt-2026-27-veronacesena-stats-and-where-to-watch-the-match?cat=2), ale **nie publikuje zweryfikowanych po meczu liczebności fauli gospodarze/goście**. Zapisano `research/multimodel/non_pl_opta_source_inventory_20261123.json`: **0 dodatkowych zweryfikowanych meczów OPTA spoza PL**. Nie podmieniano wartości z nieopisanych agregatorów na OPTA; nadal blokada porównania z faulami u bukmachera.

### 5. Bramka gotowości do kalibracji (bez zmian wag)

`github_models/multimodel_calibration_gate.py` zapisuje **oddzielnie A/B/C i SHADOW**, diagnostykę na bazie minimum **20 odrębnych zakończonych meczów**, dopiero od około **100** meczów przegląd formalny, i osobne warunki udokumentowanego holdoutu oraz payoutów. Nie sumuje skorelowanych linii z jednego meczu jako niezależnych próbek. Niezależnie od liczby prognoz `calibration_authorized=False`, `model_weights_changed=False`. Publikuje tylko techniczne `MULTIMODEL_CALIBRATION_READINESS.json` w istniejącym artefakcie audytu, bez trzeciego użytkowego PDF. Pozostają dwa PDF, kurs od 1,20 i brak obowiązkowego progu punktowego 67/100.

### Testy i wdrożenie

- [PR #80](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/80), testy zaufanego źródła i archiwalnych ofert bez płatnych zapytań.
- [CI na oryginalnym archiwum, pierwszy poprawny przebieg](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45137638541): **29/29 testów PASS**, **24 rozliczenia testowe SHADOW** z 4 spotkań z odrębnego zweryfikowanego wyniku. Liczba 24 obejmuje wszystkie prognozy w próbie testowej, nie tylko wycenione kupony z rzeczywistego audytu.
- Dodatkowe testy przeciw pełnej historii ponad 42 tys. rekordów i główny produkcyjny cykl 1X2/gole/BTTS/AH wymagają końcowego sprawdzenia. Status `settled` w dotychczasowej produkcji pozostaje 0 dopóki nie ma nowego pomyślnego raportu. Nie nazywać samego PR lub PASS testowego dowodem aktualizacji produkcji.

**Otwarte po pięciu krokach:** (1) przyjęcie nowej historii przez pełny replay bez konfliktów nazw, (2) potwierdzenie liczby naprawdę rozliczonych w najnowszym audycie, (3) wypłaty Superbet/Book­ings po odpowiedzi OddsPapi, (4) liczby fauli OPTA z innych lig, (5) odpowiednia liczebność próby i niezależny holdout. Te zależności nie uzasadniają zmiany wag dzisiaj.

### Końcowy wynik pełnego audytu produkcyjnego — 23.11.2026, 08:41 UTC

**WYKONANE i potwierdzone w GitHub Actions:** https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45137989936 — **SUCCESS**. Dane wynikowe odczytano bezpośrednio z faktycznie opublikowanego artefaktu `oddspapi-rolling-audit` ID **14802141037**. Nowy score bridge: `CURATED_FINAL_EVIDENCE=4`, **4** rzeczywiście nowe niezależne zakończone wyniki, `not_backdated=true`, brak potwierdzonej wypłaty bukmachera. Odpowiadają dokładnie czterem źródłowo zweryfikowanym meczom z 20 listopada; źródła i niezmienione identyfikatory zapisane w `outcomes/independent_final_bridge_manifest.json`.

**A/B/C replay** (`REPLAY_AUDIT.json`, 12 archiwów, 6229 zachowanych notowań, 1330 unikalnych wycenionych propozycji):
- **30 `settled` z dokładnie 4 różnych meczów**: 8 zakładów `1X2`, 22 zakłady bramkowe `goals`; kurs co najmniej 1,20, przyjęty ze źródłowej migawki przed meczem, nie ustalony retrospektywnie.
- **657 `pending_future`**, **643 `unresolved`**, w tym 546 `no_exact_verified_outcome` i 97 `no_verified_final_yet` (w stosunku do 673 nierozstrzygniętych sprzed zmiany poprawnie rozliczono 30). Nie traktować 643 jako przegranych i nie scalać przyczyn z kategoriami niezweryfikowanych fauli/kartek. `market_agreement_test`: jedynie 4 różne zakończone mecze, decyzja `NOT_ENOUGH_INDEPENDENT_SETTLED_MATCHES`.
- Diagnostyka `model_only`: 30 powiązanych wycenionych pozycji z 4 meczów, trafność 40%, Brier 0,161804 i log loss 0,503424; liczby nie mają wystarczającej mocy do porównania modeli. Symulowana stopa zwrotu z historycznych kursów jest czysto hipotetyczna, bez potwierdzenia wypłat Superbet, opłat, podatku i bez niezależności typów.

**SHADOW replay** (`PRICED_SHADOW_SETTLEMENT.json`, 4 poprawnie połączone archiwa, 501 unikalnych rzeczywistych wycenionych ofert w 108 meczach):
- **20 `settled` z tych samych 4 spotkań**, w tym **8 BTTS** oraz **12 handicapów azjatyckich ±1,5**. 5 propozycji na mecz, każda z rzeczywistą archiwalną ceną; **nie jest to 20 niezależnych próbek**.
- **481 `pending`**, w tym 175 oczekuje na publikację źródła końcowego w okresie buforowym, 306 przed rozpoczęciem. **0 `unresolved`** w tym przebiegu; nie oznacza to automatycznego rozliczenia wszystkich meczów po zakończeniu bufora.
- W każdej z obu kategorii wstępne 50% trafności; Brier 0,202472 (BTTS) i 0,147662 (AH), log loss 0,597137 i 0,483271. Te wartości **wyłącznie opisowe, korelowane, próba 4 meczów**; bez zmian modelu, ewaluacji wypłat i rzekomego edge.

**Kalibracja:** `MULTIMODEL_CALIBRATION_READINESS.json`: A/B/C 30 pozycji, SHADOW 20, ale **4 odrębne mecze w obu próbach**; minimum 20 do diagnostyki i 100 do przeglądu **NIEOSIĄGNIĘTE**. `calibration_authorized=false`, `model_weights_changed=false`, `holdout_evidence_available=false`, `bookmaker_payout_confirmed=false`. Liczba `conservative_max_distinct_fixtures=4` jest konserwatywną **dolną granicą liczby unikalnych meczów łącznej próby** (max liczności obu podzbiorów), nie matematyczną górną; dla tych konkretnych wyników z tych samych czterech fixtureId suma unikalnych nadal wynosi 4.

**Stabilność techniczna:** https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45137990035 — testy na `main` **29/29 PASS**, rozliczenia w produkcji bez błędów, brak nowych płatnych wywołań OddsPapi, `PRICED_SHADOW_BROKEN_GATES=0`. Artefakt audytu zawiera wyniki techniczne w JSON oraz dotychczasowy audyt PDF; nie wygenerowano trzeciego użytkowego raportu. Opis `hit rate` i ROI nie jest twierdzeniem o przewadze nad bukmacherem.

**Status pięciu kroków po wdrożeniu:** (1) **zamknięto cztery dokładne brakujące wyniki** i rozliczono ich ceny; (2) **zakończono audyt A/B/C**, nadal 643 nierozstrzygnięte pozycje innych meczów/rynków wymagają dowodu; (3) **OddsPapi nadal bez odpowiedzi**, otwarte issue #78, brak nowych zapytań; (4) **OPTA poza PL niepotwierdzone per-team**, świadomie nie promowano fauli; (5) **bramka kalibracyjna przetestowana i działająca, STOP dla wag** z powodu 4<20<100. Kolejny priorytet: systematyczne rozliczanie kolejnych zakończonych meczów i źródłowa weryfikacja rynku Bookings, a potem prospektywny holdout.

## Rozszerzenie 1–5 w uzgodnionej kolejności — 23.11.2026

Polecenie: najpierw **podwójna szansa**, potem **linie bramek i rożnych**, następnie **faule i kartki**, dopiero na samym końcu **strzały ogółem i celne**. Wszystkie zadania dotyczą MultiModelu `karolbarankiewicz1984-ui/kb-score-model`. Zasady: wyłącznie rzeczywiste, zarchiwizowane kursy Superbet >=1,20; brak obowiązkowej oceny 67/100; nie zmieniać wag ani historii zamrożonych predykcji; brak dodatkowych płatnych prób OddsPapi.

### Etap 1. Podwójna szansa 1X / X2 / 12 — KOD SCALONY DO SILNIKA

- [x] [PR #81](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/81) scalony do **`codex/multimodel-v2`**, czyli źródła używanego w codziennym workflow A/B/C. W `github_models/abc_filter.py` dodano `market=double_chance` i dokładnie trzy wybory: `1X=p_home+p_draw`, `X2=p_draw+p_away`, `12=p_home+p_away`. Sumowanie *oddzielnie* we wcześniej zamrożonych Elo i Dixon–Coles, potem konserwatywne minimum obu wartości. Zachowano istniejące ograniczenie różnicy modeli maks. 10 punktów procentowych i progi A/B/C; nie utożsamiano skorelowanych wariantów z niezależnymi próbkami.
- [x] `abc_settlement.py`: niezależne rozliczenie `1X`, `X2` i `12` na podstawie tego samego wiarygodnego wyniku końcowego, którego używa `1X2`. Brak wyników → unresolved, nie przegrana. Kod tabel PDF `abc_report.py` i `abc_chronological_pdf.py` drukuje polskie nazwy, a dwa użytkowe PDF obsługuje `main/github_models/unified_output.py`.
- [x] [Testy na archiwum A/B/C, run 45220508059](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45220508059): **8/8 PASS**; 457 wierszy wariantów A/B/C `double_chance` na źródłowych danych, dla podzbioru 20 rozegranych w przyszłości spotkań; 0 wywołań bukmachera. [CI po scaleniu do gałęzi silnika, run 45220830774](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45220830774) SUCCESS.
- [x] Potwierdzono w **rzeczywistym archiwum OddsPapi** z 22.11.2026 nazwę `Double Chance Full Time`, `marketType=doublechance`, `period=fulltime`, `handicap=0`, dokładnie trzy strony `1X`, `2X`, `12`. `2X` u dostawcy jest jawnie przemapowane na kanoniczne `X2` modelu. Należy odróżniać ten rynek od odpowiedników `p1` i `p2`.
- [x] [PR #83](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/83) scalony do `codex/oddspapi-odds-layer`. Dokładne porównanie dopuszcza tylko kompletną trójkę ze wspólnym `market_id`, stałym `fixtureId`, stemplem czasu dostawcy sprzed kickoff, bez propozycji gracza, przy braku błędów dat. Nie wylicza kursów z `1X2` i nie dopisuje ceny, której w archiwum nie ma. `oddspapi_replay_audit.py` potrafi rozliczać dopasowaną podwójną szansę jako niezależną obserwację wyniku, a NIE wypłatę na realnym kuponie.
- [x] [CI OddsPapi run 45222743135](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45222743135): **4/4 testy PASS**, na zapisanych już ofertach **163** dopasowane typy DC z **68 różnych meczów**, w tym **129** z kursami >=1,20. To stan zamrożonego archiwum z 22 listopada, NIE bieżąca oferta, NIE rekomendacje ani 129 niezależnych historii rozliczeń. Zero nowych płatnych zapytań. Po aktualizacji `oddspapi-daily.yml` używane będzie przetestowane źródło z SHA `f9aa94343efff7911fddcf5957b31884e150fc31`; usunięto automatyczne uruchamianie płatnego kolektora na sam `push` zmiany workflow (zostawiono cykl po A/B/C i ręczny dispatch).

### Etap 2. Dodatkowe linie bramek i rożnych — KOD SCALONY DO SILNIKA

- [x] `github_models/event_markets.py` `THRESHOLDS`: bramki **0,5 / 1,5 / 2,5 / 3,5 / 4,5**, rożne **6,5 / 7,5 / 8,5 / 9,5 / 10,5 / 11,5**. Ten sam wcześniej oceniony Poisson, te same liczby zdarzeń, bez dodawania informacji z przyszłości i bez zmian obecnych linii fauli/kartek. Tylko linie niecałkowite; brak ignorowanych zwrotów przy liniach całkowitych.
- [x] Na testowym, rzeczywistym podzbiorze 20 zamrożonych spotkań wygenerowano **406 wierszy event-market** z nowymi liniami. Wrażliwa walidacja źródła nadal wymaga minimum 60 meczów w lidze i po 8 dla obu drużyn; brak danych oznacza blokadę, a nie wymyśloną prognozę. 8/8 testów przebiegło pomyślnie.
- [x] Ekspozycja w 7-dniowych raportach `ABC` odbywa się przez istniejący, zamrożony generator. Dwudokumentowy generator `main` zna teraz `double_chance`, nowe linie liczbowo nie wymagają osobnego parsera.

### Etap 3. Faule — walidacja reguł ukończona, źródłowa zgodność NIEPOTWIERDZONA

- [x] Oficjalny komunikat Superbet o piłce nożnej obowiązujący od **16.12.2025**: [Superbet — zasady](https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r). Rozliczane są **wyłącznie przewinienia odgwizdane przez sędziego**; faule przy zastosowaniu przywileju korzyści nie są liczone. To ograniczenie należy uwzględnić przed promocją `fouls`.
- [x] Superbet w [komunikacie OPTA obowiązującym od 29.04.2026](https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122) podaje oficjalne statystyki OPTA jako główne źródło zdarzeń statystycznych. `HF/AF` z football-data.co.uk stanowi źródło wtórne i bez obserwacji OPTA nie wystarcza do oficjalnego rozliczenia Superbet.
- [x] `github_models/disciplinary_rules.py` wprowadza audyt wymaganych pól, w tym flagi fauli rzeczywiście odgwizdanych, wyłączenia przewagi, źródłowego identyfikatora OPTA, daty obserwacji i drużyn. Bieżący importer `HF/AF` nie posiada pełnej rekonstrukcji zdarzeń; `automatic_market_promotion=False`. To dowód ograniczenia danych, nie syntetyczna weryfikacja brakujących statystyk.
- [ ] Realny komplet par per-team OPTA dla innych lig niż Premier League nadal nie istnieje w repo; dotychczasowe 31 udokumentowanych par PL bez różnic nie dowodzi podobnej zgodności w innych krajach. Pozostaje zależność od licencjonowanego źródła lub ścisłego audytu na nowych źródłach.

### Etap 4. Kartki — walidacja reguł ukończona, Bookings NIEPOTWIERDZONE

- [x] Superbet: w rynku łącznej liczby kartek **żółta = 1, bezpośrednia czerwona = 2, wykluczenie po dwóch żółtych = 3 łącznie**; kartki sztabu, rezerwowych i po ostatnim gwizdku wyłączone, kartka w przerwie wymaga wznowienia gry przez zawodnika. Punkty kartkowe są inną jednostką, nie `HY+AY`.
- [x] `github_models/disciplinary_rules.py`: wymagane odrębne zdarzenia czerwonych / drugiej żółtej, status zawodnika, przerwy i końca spotkania; testowana arytmetyka z jednoznacznym odrzucaniem sprzecznych zdarzeń. Użycie wyłącznie w diagnostyce na testowych przypadkach, NIE jako rozliczanie faktycznych meczów z niepełnym `HY/AY`.
- [x] `github_models/market_rule_gate.py` raportuje źródła reguł i brakujące pola, wciąż wymaga zweryfikowanej jednostki `Bookings` OddsPapi. W PDF audytu pojawia się czytelna informacja o tym ograniczeniu.
- [ ] Brak odpowiedzi `support@oddspapi.io` (kontrola Gmail 23.11.2026), issue [#78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78): 4 wcześniejsze HTTP 500 dla `/v4/settlements`, nadal brak uzgodnionej jednostki `Bookings`, bez powtórzeń płatnych wywołań. Nie promujemy tego rynku mimo ustalonego oficjalnego sposobu liczenia kartek Superbet.

### Etap 5. Strzały ogółem i celne — CELOWO OSTATNI, NIEROZPOCZĘTY

- [ ] Nie implementować żadnych prognoz strzałów ani celnych przed spełnieniem kryteriów źródłowych fauli i kartek. Wymagany osobny, datowany, meczowy, przedmeczowo dostępny i niezależnie rozliczany zestaw zdarzeń, dokładny identyfikator rynku całego meczu oraz potwierdzenie jego zgodności z definicjami Superbet. Nie mylić strzałów zawodnika z sumą meczu.

### Ciągłość i wdrożenie

- `codex/multimodel-v2` jest silnikiem badawczym wywoływanym przez `main/.github/workflows/github-models-v2-daily-audit.yml`; nowe typy pojawią się **w następnej rzeczywiście wygenerowanej i zamrożonej prognozie**, nie są dopisywane do dawnych archiwów.
- `codex/oddspapi-odds-layer` jest adapterem kursów przypinanym przez `main/.github/workflows/oddspapi-daily.yml`; pin musi wskazywać przetestowany SHA z PR #83, bez kosztownego `push` dodatkowego pobrania. Zwykły codzienny cykl ma pozostać.
- Dotychczasowe dwa wynikowe PDF-y, granica kursu 1,20, bez zmian wag i brak twardej punktowej oceny 67/100 — bez zmian. Wszystkie szacunki `P` są badawcze i niekalibrowane; minimum 4 niezależnie rozliczonych meczów dotychczas nie usprawiedliwia zmian modelu.
- CI końcowe dla `main`, przyszłe archiwa i zewnętrzna walidacja fauli/kartek mają być raportowane osobno; nie utożsamiać testu syntetycznego z potwierdzonym rozliczeniem Superbet.

**Formalne zadanie na brakujące dowody:** [issue #84](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/84), otwarte 23.11.2026. Oddzielnie od istniejącego problemu dostawcy Bookings [#78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78). Do czasu dowodów na faul odgwizdany, event-level karty i źródło OPTA: `automatic_market_promotion=false`.

### Potwierdzenie na głównej gałęzi po scaleniu etapów — 23.11.2026, 17:05 UTC

- [PR #82](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/82) **MERGED do `main`**, commit `a0698dbec5ba4acc4030c2791bf3fe777287d3d6`. Załączniki zawierają też rejestry, testy źródeł OPTA/Bookings, oficjalne reguły fauli i kartek oraz oznaczenia 1X/X2/12 w dwóch użytkowych PDF-ach.
- [Market rules na `main`, run 45223679412](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45223679412): **SUCCESS, 36/36 testów PASS**, semantyczne bramki bezpieczeństwa PASS; zero dodatkowych wywołań OddsPapi.
- [Generator dwóch PDF na `main`, run 45223679448](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45223679448): **SUCCESS, dokładnie dwa otwieralne dokumenty (14 i 2 strony)**. Użyto ostatnich zgodnych, istniejących archiwów **OddsPapi run 45045069985** i **A/B/C run 45037233530** z 22 listopada. Nie mylić weryfikacji rendererów z opublikowaniem *nowych* prognoz i cen 1X/X2/12 — te pojawią się dopiero z następnego zasilenia według zwykłego harmonogramu.
- [Audyt historycznych cen, run 45223679417](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45223679417) ruszył na `main` i nadal trwał podczas ostatniego odczytu. Nie zakładać końcowego `success` ani wzrostu liczby rozliczeń bez jego artefaktu.
- [Issue #84](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/84) utrzymuje blokadę niezależnej walidacji OPTA poza PL i szczegółowych zdarzeń kartek. [Issue #78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78) nadal blokuje ustalenie jednostki OddsPapi Bookings oraz oficjalnego payout. **Strzały ogółem/celne pozostają nieimplementowane z wyboru użytkownika, jako ostatni etap**. Każde przejście do rekomendacji fauli/kartek wymaga dowodu źródłowego, a nie samego PASS testu syntetycznego.

### Aktualizacja po zakończonym audycie wieczornym — 23.11.2026, 17:21 UTC

Potwierdzono [run 45223679417](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45223679417), zakończony **SUCCESS**, artefakt `oddspapi-rolling-audit` ID `14844766150`. Wcześniejszy stan 4 zakończone mecze / 30 A/B/C / 20 SHADOW **zastąpiono nowszymi obserwacjami (nie łączymy ze starszym przebiegiem)**:

- `REPLAY_AUDIT.json`: **592 rozliczone wycenione prognozy A/B/C z 50 niezależnych spotkań**; 1330 unikalnych ofert w próbie, 81 nierozstrzygniętych (70 `no_exact_verified_outcome`, 11 `no_verified_final_yet`), 657 `pending_future`. Zakończone historyczne oferty obejmują 1X2, bramki i rożne; ceny archiwalne Superbet, bez potwierdzenia oficjalnej wypłaty.
- `PRICED_SHADOW_SETTLEMENT.json`: **175 rozliczonych typów SHADOW z 38 różnych meczów**: BTTS 76 (38 meczów, surowa trafność 50%), handicap ±1,5 99 (38 meczów, surowa trafność 32,32%); pozostałe 326 `pending`, w tym 20 oczekujących na final source w okresie buforowym i 306 przed kickoff. To różne typy z wielu tych samych spotkań, nie 175 niezależnych próbek. Brak 4xx/5xx dodatkowych płatnych żądań.
- `MULTIMODEL_CALIBRATION_READINESS.json`: **próg eksploracyjnej diagnostyki 20 meczów osiągnięty**, ale **formalny przegląd 100 różnych meczów jeszcze nie**; `holdout_evidence_available=false`, `calibration_authorized=false`, `model_weights_changed=false`. `conservative_max_distinct_fixtures=50` oznacza minimalną dolną granicę liczby meczów w łącznej próbie A/B/C i SHADOW, nie potwierdzony rozmiar sumy zbiorów.
- Przedmiot audytu 1X2/goals/corners to rynki z **wcześniej zamrożonych archiwów**. Nowe `double_chance` i dodatkowe linie muszą najpierw pojawić się w nowej, rzeczywiście prospektywnej prognozie i niezależnym audycie. Test dwóch PDF `45223679448` na *starszym* archiwum nie jest dowodem nowej produkcji z bieżącego dnia.
- Podgrupa `market_agreement_test` wybrała **116 skorelowanych pozycji z 50 meczów** (83,62% trafności w selekcji, symulowane gross ROI +12,77%); w odrębnych zbiorczych, nieselektywnych próbkach bramek/rożnych/1X2 gross ROI było ujemne. Wybór po fakcie, zależność typów i brak payout sprawiają, że **nie jest to dowód przewagi nad Superbet ani powód do podnoszenia wag**. Nie utrwalać eksperymentalnego progu 0,67 jako obowiązkowego filtra.
- **Następne działania:** (1) niezależny audyt jakości na 50 meczach, z Brier/log loss według rynku, sezonu, przedziału prawdopodobieństwa i zamrożenia; (2) zdiagnozowanie 70+11 nierozstrzygniętych prognoz bez automatycznej zamiany na przegrane; (3) weryfikacja pierwszych nowych 1X/X2/12 i linii 0,5/4,5 oraz 6,5/10,5/11,5 w kolejnym cyklu; (4) dowody OPTA dla fauli i event-level kartek oraz odpowiedź dostawcy Bookings (#84 i #78); (5) dopiero po >=100 meczach i niezależnym prospektywnym holdoucie rozważyć ponowną kalibrację. Strzały ogółem i celne na koniec, po zamknięciu dyscyplinarnych dowodów.

## Kontynuacja na polecenie użytkownika — 23.11.2026, godz. 19:33 Europe/Warsaw

**Polecenie:** „Zapisz w rejestr i rób co proponujesz”. Kolejność: (1) kontrola nowych 1X/X2/12, dodatkowych linii bramek i rożnych w codziennym 2-PDF i dopasowaniu prawdziwych kursów Superbet; (2) diagnoza i dalsze rozliczanie 81 nierozstrzygniętych rynków; (3) źródłowa walidacja fauli i kartek, ze szczególną uwagą na OPTA poza Premier League i jednostkę OddsPapi Bookings; (4) prospektywny audyt i kalibracja dopiero na odpowiedniej liczbie **niezależnych spotkań** z chronologią danych i holdoutem; (5) strzały ogółem i celne **dopiero po** źródłowej walidacji dyscyplinarnych. Nie wolno uruchamiać dodatkowych płatnych skanów OddsPapi, uzupełniać danych przyszłością, zmieniać wag ani utożsamiać wyniku matematycznego z oficjalną wypłatą.

**Pomiar wejściowy:** [historyczny audyt 45223679417](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45223679417), stan 23.11.2026 17:08–17:20 UTC: 12 archiwów A/B/C; 1 330 różnych wycenionych pozycji, **592** rozliczone z **50** różnych meczów, **81** nierozstrzygniętych (70 no_exact_verified_outcome, 11 no_verified_final_yet), 657 przyszłych; SHADOW **175** rozliczonych wycen z **38** meczów. To nie 767 niezależnych meczów. 50/100 na potrzeby przeglądu formalnego, 20/20 osiągnięte tylko dla wstępnej diagnostyki. Niezależnego prospektywnego holdoutu i oficjalnego potwierdzenia payout nie ma; calibration_authorized=false, model_weights_changed=false.

**Wykonanie i kryteria odbioru:** Aktualizować poniżej o rzeczywiste artefakty i status CI, odróżniać kod gotowy od *świeżego* raportu. Stare archiwa z 22.11 nie zawierają prognoz utworzonych po wdrożeniu rozszerzeń — nie wolno ich dopisywać wstecznie. Raport powinien zachować maksymalnie 3 pozycje na mecz w bloku najlepszych, zachowując różnorodność rynków i wskazania statusu rzeczywistego archiwalnego kursu. Wszystkie pozycje per mecz pozostają w pełnej tabeli. Rozliczanie powinno rozpoznawać brak dokładnego wyniku zdarzeniowego, nawet kiedy końcowy wynik bramkowy jest znany, ale nie zastępować go liczbą zero. Source gaps fauli i kartek muszą być wykazane na danych, a nie na syntetycznych wynikach.

**Status otwarcia:** w realizacji. Oddzielne issue [#84](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/84) zbiera wymagania licencjonowanych statystyk OPTA, [#78](https://github.com/karolbarankiewicz1984-ui/kb-score-model/issues/78) czeka na znaczenie OddsPapi Bookings.

### Implementacja i wyniki w bieżącej kontynuacji (23.11.2026)

**1. Raportowanie i nowe typy:**
- [x] W generatorze dwóch PDF poprawiono **normalizację linii 1X2**: brak linii w modelu ABC jest tym samym rynkiem, co OddsPapi `line=0`; dotychczas ten szczegół mógł ukrywać rzeczywiście zapisany kurs 1X2. `1X/X2/12` dopuszczają tylko linię brak/zero; rynki Over/Under zachowują ścisłe dopasowanie liczbowej linii.
- [x] Skrót maksymalnie 3 pozycji na mecz uwzględnia **różne rodziny rynków**, zanim wybierze drugą pozycję z tej samej rodziny. Wynik 1X2 i podwójna szansa to jedna rodzina (silnie skorelowane). Wysokie P nadal jest badawcze, kursy to zapisane i dokładnie dopasowane przedmeczowe Superbet. Wszystkie rynki bez zmian pozostają w sekcji pełnej.
- [x] Dzienny manifest (techniczny plik JSON, nie trzeci PDF) zapisuje rzeczywiście widziane typy 1X/X2/12, linie 0,5 i 4,5 bramek oraz 6,5/10,5/11,5 rożnych, liczbę dopasowanych ofert na rynek i przekrój najlepszych. `new_markets_observed` jest prawdą tylko, gdy obserwowane są nowe typy/linie; dla starszego archiwum jawny status `awaiting_fresh_market_output_or_source_coverage`. Nie powstają sztuczne prognozy lub kursy. `tests/test_multimodel_rollout_observation.py` sprawdza sortowanie i tożsamość linii.

**2. Nierozliczone pozycje:**
- [x] [PR #85](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/85) **scalony** do adaptera archiwalnego OddsPapi (`codex/oddspapi-odds-layer`), commit `db83245f2504c1d3b11159bb049d3199a0e9d820`. Dopisano wynikową listę identyfikatorów **naprawdę rozliczonych różnych spotkań** i pełne szczegóły nierozstrzygniętych wyborów `fixture_id/market/line/selection`; w przypadku braku dokładnej liczby zdarzeń diagnoza rozdziela `verified_final_score_exists_event_total_missing` od `independent_final_score_not_found`. Nie podmienia statusów, nie dopisuje fikcyjnego wyniku, nie wybiera lepszej ceny po meczu.
- [x] [CI #45241690368](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45241690368): 2/2 offline PASS; nowy audyt na `main` zostanie skierowany na dokładnie przetestowany SHA bez dodatkowych płatnych zapytań. Znane 70 i 11 pozostają statusem wejściowym, dopóki nowy rzeczywisty przebieg nie da dowodów zmiany.

**3. Faule i kartki, bez zgadywania jednostek:**
- [x] `github_models/disciplinary_source_coverage.py` oblicza **rzeczywiste**, wtórne pokrycie agregatów HF/AF oraz HY/AY per liga i kraj na podstawie odczytanych publicznych plików football-data.co.uk, z obsługą sprzecznych duplikatów, daty publikacji i brakujących par. Nie nazywa tych danych oficjalnym OPTA.
- [x] Nowy artefakt archiwalnego audytu `DISCIPLINARY_SOURCE_COVERAGE.json` podsumuje źródłowe statystyki, a w dwóch PDF-ach audytowych pokażemy pokrycie per liga z wyraźną blokadą. `official_opta_event_level_source_observed=false`; `market_promotion_allowed=false`; bez zgody na `Bookings = HY+AY`. Testy: `tests/test_multimodel_disciplinary_source_coverage.py`.
- [ ] Ostateczny dowód dla fauli/kartek nadal wymaga zewnętrznych, meczowych statystyk OPTA poza PL i odpowiedzi dostawcy OddsPapi co do jednostki Bookings. Zależności zapisane w #84 i #78; kod nie generuje fałszywej walidacji.

**4. Gotowość do kalibracji:**
- [x] `multimodel_calibration_gate.py`: zidentyfikowane rzeczywiste `settled_fixture_ids` A/B/C pozwalają teraz liczyć **dokładną sumę zbiorów** meczów A/B/C i SHADOW, bez podwójnego liczenia wspólnych spotkań. Dotychczasowa wartość `max(A,B)` jest wyraźnie nazwana konserwatywną **dolną granicą**, a nie górną.
- [x] Audyt wyświetli gotowość według rynku A/B/C, liczbę brakujących różnych meczów do przeglądu 100 oraz plan przyszłego holdoutu: chronologiczny podział całymi meczami, te same spotkania nie mogą wystąpić w treningu i walidacji, dane i kursy zamrożone przed kickoff.
- [ ] Wagi modelu i wybór kalibratora **bez zmian**. Niezależnego holdoutu nadal nie ma; samą liczbą 100 nie wolno zatwierdzać modelu.

**5. Strzały ogółem i celne:** odłożone na koniec, bez kodu prognozującego i bez sztucznego źródła.

**Wdrożeniowe testy i obserwacja kolejnego normalnego cyklu** są warunkiem końcowego potwierdzenia. Wspomniane testy na przykładowych rekordach nie są niezależnie rozliczonymi meczami. 0 dodatkowych płatnych wywołań OddsPapi.

### Potwierdzenie wdrożenia na main — 23.11.2026, godz. 19:55 Europe/Warsaw

- [PR #86](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/86) został scalony do main, commit `5f387c2b6e51593db3a3d4a45540ef6a1c9b6317`. Diagnostyka rozliczeń #85 jest wcześniej scalona do izolowanego adaptera OddsPapi, którego precyzyjnie przypięty kod pobiera bieżący workflow audytu.
- [Testy po scaleniu — Actions 45242940270](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45242940270) **SUCCESS, 49/49 PASS**, w tym blokady rynku Bookings/OPTA, rozliczeń i kalibracji (bez sztucznych wyników).
- [Dwudokumentowy raport po wdrożeniu — Actions 45242940478](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45242940478) **SUCCESS**, dokument prognoz 14 stron, audyt 2 strony. Źródłowe prognozy są nadal ze snapshotu 22.11; nie potwierdzono na nich jeszcze nowych 1X/X2/12, co jest prawidłowe i nie może być naprawiane wsteczną estymacją.
- [PR #87](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/87) **MERGED**, commit `b713cb73363deae10613b836036fb6d48c410cab`. Przyszłe manifesty pokrycia rynków zapisujemy jako osobny artefakt JSON **multimodel-market-rollout-evidence**, nie trzeci PDF. [Actions 45243378195](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45243378195): **SUCCESS**, dokładnie dwa PDF (14 i 2 strony) + osobny artefakt techniczny. Manifest z poprzedniego snapshotu 22.11 ma status `awaiting_fresh_market_output_or_source_coverage`, rzeczywiste, historyczne 16 wycenionych pozycji (4 BTTS, 2 rożne, 4 bramki, 6 handicap); nie zgłasza jeszcze 1X/X2/12 z nowego silnika.
- [Szczegółowy rolling-audit 45242940289](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45242940289) uruchomiony na main; na moment rejestracji **w trakcie** odtwarzania archiwów. Dopiero po sukcesie jego artefaktu wolno podać liczbę nowych rozliczeń, rzeczywisty podział braków i per-ligowe liczby HF/AF i HY/AY.
- **Wagi bez zmian; nadal nie ma źródłowo potwierdzonej równoważności OPTA dla fauli i OddsPapi Bookings dla kartek.** Strzały są celowo ostatnie. Kolejny normalny cykl A/B/C i Superbet powinien opublikować dopiero nową zamrożoną prognozę, której nowości można ocenić na utrwalonym manifeście.

### Stan zewnętrznego potwierdzenia Bookings — 23.11.2026 wieczór

Ponownie sprawdzono korespondencję Gmail: istnieje wysłane zgłoszenie „OddsPapi v4 /settlements — four HTTP 500 errors and Superbet Bookings settlement-unit clarification”, ale **brak odnotowanej odpowiedzi dostawcy**. Publiczny artykuł [OddsPapi — Corners & Cards API](https://oddspapi.io/blog/corners-cards-odds-api/) potwierdza ofertę rynku „Bookings – Over Under Full Time”, nie objaśnia jednak w sposób wystarczający **jednostki rozliczenia konkretnego produktu Superbet**. [Dokumentacja GET settlements](https://oddspapi.io/en/docs/get-settlements) opisuje endpoint, ale 4 wcześniejsze wywołania HTTP 500 nie potwierdzają faktycznej wypłaty. Nie przenosić zasad Betfair/Paddy Power na Superbet. Blokady kart i fauli, issue #78 i #84, pozostają otwarte; żadnego kolejnego zapytania płatnego nie wykonano w tej kontroli.


## 24.11.2026 — blokada cofniętej daty w dwóch PDF MultiModel

**Zgłoszenie użytkownika:** PDF z „propozycjami” z 22.11 został pokazany 24.11. Testowy replay nie jest bieżącym kuponem, nawet gdy techniczny job jest zielony. Przyczyną był brak kontroli aktualnej daty w `multimodel-two-pdfs.yml`, który przy uruchomieniu ręcznym lub przez push wybierał *ostatni udany* archiwalny run zamiast sprawdzać dzień publikacji. `unified_output.py` filtrował jedynie datę spotkania względem archiwum, bez odrzucania rozpoczętych już meczów.

**Zmiana na gałęzi `fix/multimodel-current-pdf-freshness-20261124`:**
- Dodano `github_models/report_freshness.py` z niezależną walidacją w strefie `Europe/Warsaw`: kolejka PitchAPI oraz zapisany `market_overlay.as_of_utc` muszą pochodzić z **dzisiejszej** daty, być dostępne przed chwilą publikacji i mieć najwyżej **6 godzin**; źródłowy snapshot kursów musi być po kolejce. Timestampy wymagają strefy czasowej.
- Z aktywnego PDF wyłącza się mecze rozpoczęte oraz mające mniej niż **5 minut** do rozpoczęcia. Jeżeli brak aktualnych źródeł albo choć jednego nadchodzącego spotkania, nowy PDF z propozycjami **nie jest publikowany**, zamiast podstawienia wczorajszego.
- Walidacja `current_window` wykonywana jest przy pobraniu źródła oraz ponownie po utworzeniu PDF i tuż przed uploadem. Ostatnia weryfikacja nie pozwala publikować meczu, który rozpoczął się w czasie przetwarzania. Zmiana daty w Warszawie między przygotowaniem a publikacją także wstrzymuje wysyłkę.
- `github_models/unified_output.py` domyślnie działa jako raport aktualny; historyczny replay musi być jawny (`--historical-replay`), z tytułem **ODTWORZENIE HISTORYCZNE, NIE AKTUALNE TYPY** i nazwami plików `MULTIMODEL_ODTWORZENIE_*.pdf` / `MULTIMODEL_AUDYT_ODTWORZENIE_*.pdf`. Audyt historyczny pozostaje audytem — nie zamienia się w dzisiejsze rekomendacje.
- Testowy CI z archiwum 22.11 używa jawnie `--historical-replay`, natomiast normalny workflow nigdy nie ustawia tej opcji. Nie zmieniono modelowych prawdopodobieństw, progów, archiwalnych danych, cen, wag ani API.
- Przygotowano `tests/test_multimodel_report_freshness.py` dla starej kolejki, starej oferty, braku nadchodzących meczów, rozpoczętych meczów, publikacji po kickoff, przekroczenia 6 godzin, zmiany daty w Polsce oraz świadomego replay.

**Status przed CI:** kod zapisany do osobnego PR, **jeszcze nie wdrożony na `main`**, wyniki nowych testów do potwierdzenia. Dzienny cykl może mieć status `CURRENT_PDF_BLOCKED`, co jest prawidłową odmową publikacji, a nie porażką prognozy. Historyczne wyniki modelu są nadal dostępne w niezależnym audycie.


### Kontrola i wynik poprawki PDF — 24.11.2026

- [x] PR [#90](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/90) obejmuje kontrolę daty i świeżości danych, ograniczenie do przyszłych spotkań oraz osobny historyczny replay.
- [x] Testy [GitHub Actions — shots 45328234152](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328234152): **SUCCESS, 58/58**. Oryginalny archiwalny replay 22.11 nadal tworzy dokładnie dwa otwieralne PDF-y z nazwą `ODTWORZENIE`. Test negatywny potwierdził `MULTIMODEL_CURRENT_PDF_BLOCKED: queue_not_today_warsaw`; pliki o aktualnych nazwach nie zostały utworzone.
- [x] [GitHub Actions — market-rules 45328234091](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328234091): **SUCCESS**; istniejące zabezpieczenia rynków i archiwów utrzymane.
- [ ] Osobna weryfikacja **pierwszego produkcyjnego przebiegu** po merge: bieżąca data i źródła, liczba wyłączonych rozpoczętych spotkań, manifest `publication_mode=current`, ostatnia kontrola `CURRENT_PDF_PUBLICATION_GUARD=PASS`. Nie opisywać testowego replay jako rzeczywistego produkcyjnego raportu.

- [x] **PR #90 MERGED do `main`**: commit [`80f4903e6ce371ec21258eba5cba24b9ae70060f`](https://github.com/karolbarankiewicz1984-ui/kb-score-model/commit/80f4903e6ce371ec21258eba5cba24b9ae70060f). Po merge sprawdzono fizycznie `github_models/report_freshness.py` i oba aktywne zabezpieczenia w `.github/workflows/multimodel-two-pdfs.yml`. **Pierwszy zwykły cykl po merge pozostaje do sprawdzenia**; brak udokumentowanego nowego PDF-u nie uprawnia do podawania historycznych jako dzisiejsze.


## 24.11.2026 — zlecone wykonanie kolejnych zadań 1–3 (P0/P1)

**Polecenie użytkownika:** „Wpis w rejestrze i rób co proponujesz”. Zakres:
1. P0 ustabilizować łańcuch bieżących danych PitchAPI→A/B/C→OddsPapi→dwa PDF; wykluczyć stare kolejki PRZED płatnym zbieraniem kursów.
2. P0 opublikować samodzielny aktualizowany audyt historyczny, nawet gdy dziś brak aktualnych propozycji i świeżych kursów.
3. P1 wygenerować trzy A5 PDF z aktualnie zamrożonej kolejki: dziś, jutro, pojutrze, bez wstecznych typów i bez wymyślonych kursów.

**Stan wejściowy potwierdzony źródłowo:**
- [Actions 45328381165](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328381165) po PR #90: workflow prawidłowo zatrzymany przez `queue_not_today_warsaw`; wykorzystywał oddspapi-daily run `45261236775` z `INPUT_DAY=2026-11-23`, a próbował raportować 24.11. Nie oznacza to nieskuteczności typów, lecz brak świeżego source bundle.
- Normalny ABC workflow `.github/workflows/github-models-v2-daily-audit.yml` ma 7-dniową kolejkę i raporty na branch `codex/multimodel-v2`; stan nowego zamrożenia dla 24.11 **niepotwierdzony**. Oddspapi collector `oddspapi-daily.yml` przyjmuje od ręcznego wywołania 48-h kolejki i może spalić limit na wczorajsze spotkania; bramka ma wejść **przed** wywołaniem API.
- [Rolling audit 45328390911](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328390911), `REPLAY_AUDIT.json`: 673 rozliczone wycenione pozycje A/B/C z 58 meczów; 6 unresolved (rożne). `PRICED_SHADOW_SETTLEMENT.json`: 195 rozliczonych z 42 meczów. `MULTIMODEL_CALIBRATION_READINESS.json`: union 58, 42 brakujące do przeglądu 100, holdout brak, auto-calibration zabroniona.
- Nowy PDF audytu nie musi być powiązany z dzisiejszą ofertą. Kursy i prognozy z archiwum zawsze pozostają historyczne. Nie promować wcześniejszych wycen do PLAY. Dodatkowe płatne wywołania OddsPapi: 0.

**Plan wykonania, gałąź `fix/multimodel-current-cycle-audit-three-days-20261124`:**
- Wdrożyć fail-closed selekcję źródła na etapie OddsPapi, brak API call przy starej kolejce, dokładne trigger-run binding.
- Dodać niezależne, read-only raportowanie PDF audytu z najnowszego rzeczywistego audytu GitHub Actions i kontrolą manifestu/proweniencji.
- Wykorzystać istniejące zamrożone dane 7-dniowej kolejki ABC do trzech osobnych A5 PDF (badawczych) dziś/jutro/pojutrze; brak dopasowanego kursu = brak kursu, bez wyborów po rozpoczęciu meczu.
- Testy CI na syntetycznych danych wyłącznie dla reguł i formatu oraz integracja na rzeczywistych archiwach; oddzielić wynik testu od produkcyjnych nowych prognoz. Po testach uaktualnić ten rejestr o SHA/CI/status.


### Wykonanie i testy zlecenia 1–3 — 24.11.2026, kontynuacja

- [x] **P0 source:** `.github/workflows/oddspapi-daily.yml` nie wybiera już archiwalnej kolejki 48 h. Wybór przed odpłatnym kolektorem wymaga tego samego dnia `Europe/Warsaw`, cutoff nie starszego niż 6 h i co najmniej jednego meczu tego dnia z kickoff > now+5 min. Wywołania `workflow_run` są wiązane z dokładnym runem ABC; ręczne uruchomienia nie mogą użyć wczorajszego archiwum. Brak źródła to jawne `ODDSPAPI_SOURCE_BLOCKED`, bez pobierania płatnych kursów.
- [x] **P0 niezależny audyt:** `github_models/audit_only_pdf.py` i `.github/workflows/multimodel-independent-audit-pdf.yml` czytają wyłącznie artefakt `oddspapi-rolling-audit` (historyczny audit po `workflow_run`, możliwy także manualny). Rozdziela pozycje od różnych meczów; warunkuje zgodność sum z `MULTIMODEL_CALIBRATION_READINESS.json` i odmawia fikcyjnych wyników. Gdy brak dzisiejszych propozycji, audyt nadal może zostać wygenerowany z rzeczywiście rozliczonych archiwów. Zero dodatkowych płatnych API, zero auto-calibration.
- [x] **P1 trzy A5:** `github_models/three_day_a5.py` i `.github/workflows/multimodel-three-day-a5.yml` tworzą dziś / jutro / pojutrze z jednego rzeczywistego świeżego artefaktu ABC, bez zgadywania kursów, ranking badawczy maks. 3 propozycje na mecz i pełny wykaz pozostałych linii. Źródłowa kolejka i filtr ABC muszą mieć ten sam cutoff; rozpoczęte/zbyt bliskie pozycje są odrzucone; brak danych jest jawnie oznaczony. Osobne PDF A5, dane badawcze bez kursów, NIE gotowy kupon.
- [x] [CI read-only real archive #45418387124](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45418387124) — **SUCCESS**: 12 nowych testów + 13 regresji daty, 3 prawdziwe A5 z archiwum z 23.11 `CI ONLY` oraz niezależny historyczny audyt PDF (2 strony) z audytu [#45328390911](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328390911). Manifest audytu: 673 wycenione pozycje A/B/C rozliczone z 58 różnych meczów, 195 SHADOW, dokładna unia 58, kalibracja wyłączona. *Żaden archiwalny raport testowy nie jest publikowany jako aktualny.*
- [ ] Po merge nie potwierdzono jeszcze nowego codziennego ABC snapshotu 24.11 ani wygenerowania operacyjnych raportów A5 z rzeczywistego dzisiejszego źródła. GitHub scheduled workflow dla prognoz to zależność, nie wolno prezentować replay jako dziś.
- [ ] Issue #56 pozostaje częściowo otwarte: pierwotny zakres PitchAPI-first obejmował także integrację natywnego archiwum i exact-market quotes; nowy trzydniowy raport A5 jest jawnie badawczy i nie zastępuje dokumentu z rzeczywistymi kursami.


**Finalna kontrola PR #91 (przed merge):**
- [x] [CI nowego cyklu #45418387124](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45418387124): **SUCCESS**, 12 testów source/generator/independent audit + 13 regresji daty; 3 A5 z oryginalnego archiwum ABC z 23.11 w trybie CI-only oraz niezależny audyt ze źródłowych rozliczeń #45328390911 (673/58 A/B/C, 195/42 SHADOW). Brak nowych wywołań OddsPapi i brak fikcyjnych kursów.
- [x] [CI niezależny SHADOW #45418387373](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45418387373): **SUCCESS**, rzeczywiste archiwum BTTS/handicap, siedem PDF/regresja bez nowych zapytań.
- [ ] Pierwszy rzeczywisty codzienny przebieg workflow **po merge** nadal do obserwacji. Oddspapi gate celowo odmówi płatnego zapytania, gdy ABC udostępni kolejkę z poprzedniego dnia. Brak nowego aktualnego snapshotu nie może zostać „naprawiony” starym.


**Status wdrożenia po scaleniu — 24.11.2026:**
- [x] [PR #91](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/91) **MERGED** do `main`, commit [`623950bcd8f24eddb5bcf3c118277343d9a811ee`](https://github.com/karolbarankiewicz1984-ui/kb-score-model/commit/623950bcd8f24eddb5bcf3c118277343d9a811ee).
- [x] Zweryfikowano bezpośrednio na `main` obecność zabezpieczenia OddsPapi oraz obu nowych workflow i obu generatorów Python. Nowy proces nie obciąża limitu dostawcy przy braku świeżego źródła.
- [x] Niezależny audyt na danych z rzeczywistego `oddspapi-rolling-audit` został też fizycznie wygenerowany i obejrzany jako `MULTIMODEL_AUDYT_NIEZALEZNY_2026-11-24.pdf` (bez bieżących propozycji). Służy do podsumowania historycznych wyników z #45328390911.
- [ ] **Monitoring pierwszych produkcyjnych uruchomień nowego kodu pozostaje otwarty**: audit-only po kolejnym `oddspapi-audit.yml`; trzy A5 po nowym udanym `github-models-v2-daily-audit.yml`; wycenione dwudokumentowe po udanym OddsPapi z kolejką z tego samego dnia. Aktualny brak nowej kolejki 24.11 nie pozwala stwierdzić, że dzisiejsze typy już istnieją. Nie obchodzić blokady starym archiwum.


## 24.11.2026 — Priorytet: pierwszy realny cykl po PR #91

**Polecenie użytkownika:** „Wykonaj priorytet” — sprawdzić i uruchomić rzeczywisty łańcuch A/B/C → OddsPapi Superbet → raporty bieżące (3 A5 oraz 2-PDF); dokumentować rzeczywisty brak aktualnego źródła bez retroaktywnych typów.

**Odczyt GitHub Actions i dowody, stan wejściowy:**
- Najnowszy zarejestrowany **udany** `GitHub Models V2 — A/B/C | daily forecast and audit`: [#45246471045](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45246471045), uruchomiony 23.11.2026. Brak udanego runu ABC z 24.11 po wdrożeniu PR #91 na moment kontroli.
- `Superbet OddsPapi market layer`: ostatni udany [#45261236775](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45261236775), 23.11; brak potwierdzonej nowej oferty Superbet na 24.11. Generator 2-PDF prawidłowo odrzuca wczorajszą kolejkę, [#45328381165](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328381165), `queue_not_today_warsaw`.
- PitchAPI nie jest zupełnie niedostępny: **odrębny** pipeline prematch context [#45418595675](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45418595675) zakończył się SUCCESS; archiwum `pitchapi-prematch-context` zawiera datowane konteksty na 24.11 (47 fixture), 25.11 (45), 26.11 (56) i 27.11 (59). To **nie** jest wynik nowego A/B/C, nie zawiera gwarantowanych notowań i nie upoważnia do typowania bez zamrożenia.
- Audyt rzeczywistych, wycenionych archiwów [#45328390911](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45328390911) nadal 673 rozliczone A/B/C z 58 różnych meczów, 195 SHADOW z 42 meczów; nie zwiększać tych liczb bez nowego niezależnego rozliczenia.

**Wykonanie w PR przygotowującym kontrolowane uruchomienie normalnego pipeline:**
- `.github/workflows/github-models-v2-daily-audit.yml`: dodany jawny test `Verify Warsaw-day frozen ABC queue and preserve source health` przed tworzeniem PDF i archiwizacją. Weryfikuje `FROZEN_AT == queue.generated_at_utc`, seven-day Warsaw dates, maks. 6 h, poprawne przedmeczowe `kickoff_utc` i unikalne ID. Zapisuje `reports/github_models/coverage/CYCLE_SOURCE_HEALTH_DAY.json`, status i liczności per dzień do istniejącego artefaktu forecast oraz `GITHUB_STEP_SUMMARY`.
- Aktualizacja **samego** pliku workflow wyzwala istniejący `push.paths` na `main`, więc po scaleniu jest to **jednorazowe, zwykłe uruchomienie istniejącego ABC**, bez nowego cyklicznego cron i bez uruchomienia dodatkowego skanera OddsPapi w teście; dotychczasowa normalna łańcuchowa integracja Oddspapi z quota guard pozostaje bez zmian. Nie włączamy dawnego API-Football.
- Test reguł kolejki na świeżych oraz przeterminowanych danych w `tests/test_multimodel_current_cycle.py`, CI na PR przez `multimodel-current-cycle-ci.yml`.
- [ ] Po CI PASS i ewentualnym merge odczytać faktyczny **nowy** run ABC, oryginalną kolejkę/freeze, status 3 A5, kolektor (czas, limit, exact-match) i 2-PDF. Gdy run nie powstanie albo źródła nie spełnią warunków — pozostawić blokadę i zapisać stan. Nie deklarować nowej oferty bez artefaktów; brak = brak, nie „0 trafień”.


### Potwierdzone uruchomienie produkcyjne po PR #92 — 24.11.2026

- [x] [PR #92](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/92) **MERGED** do `main`, squash [`bf2881fd4454483300f6ee98e00b643eb21e1f00`](https://github.com/karolbarankiewicz1984-ui/kb-score-model/commit/bf2881fd4454483300f6ee98e00b643eb21e1f00). Zmiany jedynie dla chronologii źródła i kontrolowanego uruchomienia zwykłego workflow — wagi prognoz, zamrożone archiwa i plany płatnych skanów bez zmian.
- [x] [CI #45421444860](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45421444860): **SUCCESS, 13+13 testów**. Nowy test uruchamia rzeczywisty kod diagnostyki ABC na świeżej kolejce testowej i weryfikuje, że stary cutoff jest odrzucony, a plik `CYCLE_SOURCE_HEALTH_*.json` powstaje. To test kodu, nie nowa realna prognoza.
- [x] **Rzeczywisty push-run ABC został uruchomiony:** [#45421765716](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45421765716), trigger `push`, SHA `bf2881fd`, start `2026-11-24T15:07:11Z`. Odczyt podczas pracy: krok `Install isolated dependencies` IN_PROGRESS, wcześniejsze checkout/setup zakończone sukcesem. Nie wpisywać `SUCCESS`, nowej liczby propozycji, plików 3 A5 ani kursów Superbet przed faktycznymi artefaktami i zakończonym downstream.
- [ ] Po ABC: zweryfikować `CYCLE_SOURCE_HEALTH_2026-11-24.json` w artefakcie forecast; `multimodel-three-day-a5` (trzy A5 z dat 24, 25, 26); normalny `oddspapi-daily` z kolejką tego samego dnia i dokładnymi archiwalnymi kursami; `multimodel-final-two-pdfs`. Wszystkie nieobecne źródła oznaczyć jako SOURCE_BLOCKED, bez powrotu do wczorajszych prognoz. W tym sprawdzeniu nie wykonano żadnych bezpośrednich płatnych wywołań providerów.


## 25.11.2026 — Wymaganie funkcjonalne prywatnego panelu WWW: AUDYT I KALIBRACJA (specyfikacja, bez zmiany silnika)

**Dyspozycja użytkownika (rozwinięcie projektu React/PWA na OPPO z ręcznym przyciskiem odświeżenia):** audyt ma graficznie i opisowo wskazywać, *które kategorie prognoz sprawdzają się lepiej, a które gorzej*. Kalibracja ma prezentować osiągnięcie lub etap osiągania **każdego przyjętego warunku** oraz umożliwiać wykorzystanie zweryfikowanych rezultatów do dopracowania modelu. Panel prywatny, łatwy w modyfikacji, bez Base44, bez dodatkowych zapytań do płatnych API przy odświeżaniu UI. Niniejsza sekcja jest wymaganiem produktowym, **nie twierdzeniem, że panel już wdrożono**.

### A. Audyt — diagnoza skuteczności, a nie tylko licznik trafień

- Widoki graficzne *i* tekstowe dla: A/B/C i SHADOW; wyniki 1X2/1X/X2/12, bramki O/U, BTTS, handicap, rożne, faule O/U, kartki (tylko jeżeli definicja źródła jest zweryfikowana), strzały tylko jako SHADOW z niezależnie potwierdzonym event-level wynikiem.
- W każdej kategorii osobno: konkretna linia (np. faule >19.5 vs <19.5), liga, model, próg oceny, przedział rzeczywiście zamrożonych kursów (kurs >=1.20), okres/wersja. Użytkownik może przejść od kategorii do listy meczów i pełnego dowodu frozen prediction -> source final -> exact settlement. Kategorie bez dowodów pokazywać jako BRAK DANYCH / NIEROSTRZYGNIĘTE, nie 0% skuteczności.
- Grafika: ranking kategorii z próbką, wskaźnik trafień, krzywe kalibracji prognozowanych vs rzeczywistych częstości, Brier, Log Loss, przedziały niepewności, trend 7/30/90 dni i audyt historyczny, tabelaryczne rozliczenia. Każdy wykres z krótkim wnioskiem po polsku: „w tej próbce lepiej/gorzej/za mało danych”, plus dowody, data audytu i definicje rynku.
- Porównywać jakościowo tylko zgodne rynki/metody/okresy i identyczne zasady selekcji; nie mylić wysokiej surowej trafności niskich kursów ze skutecznością lepszą od prawidłowego benchmarku; podawać Brier/Log Loss wobec baseline i kursu z marżą (po normalizacji, jeżeli dostępna).
- Pokazywać liczbę *pozycji* osobno od *różnych meczów*; skorelowane rynki/linie jednego fixture nie są niezależnymi obserwacjami. Wyniki o małej liczebności otrzymują neutralną etykietę „wstępne”, brak arbitralnych rankingów.
- ROI wyłącznie jako symulacja na utrwalonym kursie prematch (z jawnie zdefiniowaną stawką), nie jako realny zysk ani oficjalne rozliczenie Superbet bez dowodu. Brak danych o jednostkach fauli/kartki/Bookings = brak potwierdzonego rozliczenia.

### B. Kalibracja — tablica założeń, etapów i użycia poprawek

- Każde założenie jako osobny „warunek/gate” ze stanem: BRAK DANYCH -> ZBIERANIE -> DIAGNOSTYKA -> PRÓG DO PRZEGLĄDU -> HOLDOUT GOTOWY -> EKSPERYMENT -> WALIDACJA -> KANDYDAT DO AKCEPTACJI -> WDROŻONE (lub BLOKADA/ODRZUCONE). Podać licznik i mianownik, brakujące dowody, daty i link do źródłowych artefaktów.
- Obowiązkowe kamienie milowe: zamrożenie predykcji przed kickoff, jednoznaczna identyfikacja fixture, niezależny finał i statystyka rynku, dokładna jednostka rynku bukmacherskiego, minimum 20 różnych meczów dla diagnostyki, próg przeglądu 100 **niezależnych meczów** (również per rynek), spójność i jakość danych, oddzielny chronologiczny holdout całymi meczami, brak leakage i overlap, ocena stabilności w czasie/ligach, porównanie Brier i Log Loss z niezmienionym baseline.
- Dla każdego warunku wyraźnie oznaczać „osiągnięty/nieosiągnięty/zablokowany/nie dotyczy”; nie stosować zielonej zgody tylko na podstawie 100 meczów; brak potwierdzonego holdoutu lub jednostki rynku blokuje odpowiednie użycie.
- Funkcja **„Przygotuj eksperyment kalibracji”**: osobny, wersjonowany kandydat (np. Platt, isotonic, wariant modelu/range) trenowany tylko na dozwolonym fragmencie historycznym; SHADOW/out-of-sample na następnych różnych meczach; wykres „przed vs po”, zmiana Brier/Log Loss, liczebność i przedziały niepewności per rynek oraz konserwatywna decyzja GO/NO-GO. Bez „naprawy” zamrożonych starych prognoz nowym kalibratorem.
- **„Zgłoś do zatwierdzenia”** i **„Wdróż zaakceptowaną wersję”** mają być celowymi, uwierzytelnionymi czynnościami uruchamianymi dopiero po wymaganych testach i zgodzie użytkownika (PR, CI, linki do porównania i rollback). Nie pozwalać lokalnemu PWA ani samemu renderowi uruchamiać uprzywilejowanych zmian na GitHubie z osadzonym tokenem. W razie braku bezpiecznego mechanizmu w v1: eksport opisowego wniosku/Issue/PR do ręcznego potwierdzenia.
- Rejestr wersji modeli, dat obowiązywania, dowodów i możliwości rollback; odrębna konfiguracja UI (filtry/układ) od matematyki modeli, tak aby zmiany wizualne nie przeliczały prognoz ani nie zacierały historii.

### C. Architektura i kolejność realizacji

- Repo GitHub zostaje źródłem obliczeń; po audycie publikuje tylko gotowe, wersjonowane, odczytowe JSON: AUDIT_DASHBOARD, CALIBRATION_READINESS, CALIBRATION_EXPERIMENTS, DATA_PROVENANCE. PWA pobiera je po naciśnięciu „Pobierz dane” i może przechować lokalnie na telefonie. Żadnych nowych wywołań PitchAPI/OddsPapi dla samego panelu.
- Repo i artefakty pozostają prywatne. Nie osadzać PAT, kluczy GitHub/odds/PitchAPI w kliencie; do synchronizacji użyć bezpiecznego dostępu lub pierwszej wersji z lokalnym importem archiwum.
- Kolejność: **I** audytowe JSON z aktualnego liczenia (bez zmiany logiki wyników), **II** mobilne widoki i komentarze opisowe, **III** karta postępu gate'ów kalibracji, **IV** odseparowane kalibratory eksperymentalne i holdout, **V** mechanizm świadomej akceptacji, wersjonowania i rollback. Brak zgody na samoczynne modyfikowanie produkcyjnych wag z poziomu UI.
- Aktualny stan kodu w chwili wpisu: `github_models/multimodel_calibration_gate.py` liczy Brier i Log Loss dla BTTS/handicapów, porównuje dokładną unii różnych fixture i zawsze ustawia `calibration_authorized=false`, `model_weights_changed=false`, `holdout_evidence_available=false`. Jest to **diagnostyka**, nie działający kalibrator. Ostatni audyt [#45540568991](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45540568991) był w trakcie, bez zatwierdzonego nowego wyniku liczebności.


## 25.11.2026 — MM-01 — audyt integracyjny (tylko odczyt)

**Status:** inwentaryzacja źródeł i kodu wykonana; pełna walidacja zawartości ZIP oraz kontraktu eksportowego przechodzi do MM-02. Bez zmian silnika, wag, progów, istniejących archiwów i workflow. Bez nowych wywołań dostawców API.

- Stan repozytorium przy odczycie: main `e9c37957fae6c0e914f59468a1bce6f4793d2531`; metadane GitHub zwracają visibility=public. Nie zmieniono widoczności ani uprawnień. Wstrzymać publikację nowych prywatnych danych do czasu rozwiązania kontroli dostępu. Nie umieszczać sekretów w kliencie.
- Silnik ABC jest wykonywany przez workflow `github-models-v2-daily-audit.yml` z kodem na `codex/multimodel-v2`; rozszerzenia raportowania, settlement i gate znajdują się również na main. Nie dublować istniejących obliczeń.
- Źródła eksportu: `reports/github_models/queues/*.json` (fixture, kickoff, źródło), `predictions/*.json`, `markets/*.json`, `filters/ABC_*.json`, `shadow/*.json`, `filters/AUDIT_*.json`, `shadow/SHADOW_AUDIT_*.json`, `data/github_models/settlement_verified_results.json`, `settlement_verified_events.json`, `coverage/CYCLE_SOURCE_HEALTH_*.json` i manifesty. Potwierdzono przykładowe nagłówki kolejki i zamrożonych predykcji; większe JSON i ZIP wymagają osobnej pełnej inspekcji.
- Trwałe zamrożenia: branch `research/github-models-frozen`, katalogi `queues/`, `frozen/`, `markets/`, `shadow/`, ścieżki data/run_id.json. Przykład: 24.11 run 45463976377. Istnienie plików potwierdzone, nie wykonano pełnego audytu wszystkich rekordów. Artefakty ABC mają retencję 30 dni; OddsPapi i audyt 90 dni, więc nie traktować samych artefaktów jako trwałego archiwum.
- Warstwa OddsPapi: `pitch_queue.json`, `collection.json`, `market_overlay.json`, `market_gaps.json`, `market_health.json`, `SHADOW_SUPERBET_OVERLAY.json` (opcjonalny). Zachować exact match i zgodność czasową ze źródłową kolejką, wzorując się na `multimodel-two-pdfs.yml`. Nie dopisywać kursów do dawnych prognoz.
- Audyt: `REPLAY_AUDIT.json`, `PRICED_SHADOW_SETTLEMENT.json`, `DISCIPLINARY_SOURCE_COVERAGE.json`, manifesty źródeł i `MULTIMODEL_CALIBRATION_READINESS.json`, generowane przez `oddspapi-audit.yml`. Diagnostyka w `github_models/multimodel_calibration_gate.py`: 20/100 różnych meczów, dokładna unia fixture, miary eksploracyjne BTTS/handicap; holdout nie jest skonstruowany ani oceniony, autoryzacja kalibracji=false. Brak gotowego systemu eksperymentów i promocji.
- Odczyt Actions: ABC 45463976377, OddsPapi 45474771818, trzy A5 45474771621, dwa PDF 45475070115 (wszystkie SUCCESS, 24.11); niezależny audyt 45543443825 i audyt OddsPapi 45540568991 (SUCCESS, 25.11). Log job 138957772554 potwierdził CALIBRATION_DISTINCT_MATCHES_FOR_GATE=59, CALIBRATION_EXACT_FIXTURE_UNION=True, CALIBRATION_GO=false oraz PRICED_SHADOW_SETTLED=195. Do progu przeglądu 41 różnych meczów, nie do automatycznej kalibracji. ABC 45669953949 w toku przy odczycie; nie przypisywać mu końcowego sukcesu.
- Wniosek: ponownie wykorzystać istniejące JSON i mechanizmy odczytu; brak jednolitego, wersjonowanego pakietu aplikacyjnego z kompletnym manifestem oraz pełnej walidacji jego integralności. MM-02: sprawdzić faktyczną zawartość ZIP, mapować istniejące źródła do kontraktu danych, określić klucze rekordów, statusy braków, zgodność cutoff i run ID, sumy kontrolne, testy importu i ochronę przed starszą migawką. Najpierw odczyt/import lokalny; automatyczną synchronizację dopiero po zapewnieniu kontroli dostępu. Nie publikować nowych danych w publicznym repo.
- Testy: odczyt metadanych repo, katalogów, kodu, fragmentów dwóch rzeczywistych zamrożeń, statusów runów, listy artefaktów i logu udanego audytu. Nie uruchamiano nowych testów CI, nie weryfikowano całej zawartości binarnych ZIP ani wszystkich historycznych rekordów. Nie deklarować ukończenia MM-02.


## 25.11.2026 — MM-02 — kontrakt eksportu i prototyp pakietu

**Status:** prototyp transportu lokalnego wykonany i sprawdzony na rzeczywistych danych; PR #93 draft, bez wdrożenia produkcyjnego. Pełne zamknięcie MM-02 wymaga uzupełnienia poniższych blokad.

- Odczytano MM-01; pobrano i otwarto cztery istniejące ZIP: ABC forecast 14953708712, ABC complete 14958667707 (run 45463976377), OddsPapi 14958553479 (run 45474771818), rolling audit 14990018488 (run 45540568991). CRC wszystkich poprawne. Kolejki ABC i OddsPapi identyczne bajtowo. Zamrożenie 24.11, audyt 25.11; nie przedstawiać pakietu jako bieżącego.
- Kontrole rekordów: 559 fixture, 585 predykcji bazowych, 7360 wierszy event markets, 5240 kandydatów ABC, 1752 SHADOW; brak nieznanego fixture, późnego freeze lub różnego cutoff w sprawdzonych wierszach. 1354 porównania ABC z kursami (191 poniżej 1.20, zachować do archiwum, nie do TOP), 122 wycenione wiersze SHADOW; żadnego kursu po kickoff w sprawdzonych overlay. 32341 ofert w kolekcji to nie liczba rekomendacji. Audyt 679 rozliczonych pozycji ABC z 59 różnych meczów, 195 SHADOW z 42; unia 59, brak 41 do przeglądu, kalibracja zabroniona.
- Wykryto `v2_score=not_computed` w ABC; nie zastępować oceną p*100. TOP 67/100 blokowany. `reports/github_models/api_final_manifest.json` zawiera literalne znaki backslash-n po obiekcie (JSON Extra data); opcjonalny manifest odizolowany w SOURCE_HEALTH z hashem, źródło niezmienione. Wyniki i eventy mają obce identyfikatory dostawcy; nie łączyć automatycznie po nazwie.
- [PR #93](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/93) — gałąź feat/mm02-panel-export, head d064e7c14653a93315705a8c2b62e907df75f136: `github_models/panel_export.py`, `tests/test_multimodel_panel_export.py`, `docs/MULTIMODEL_PANEL_EXPORT_V1.md`. Kod eksportera na GitHub ma blob 84b8acb5305d86da0e1488eca1c36e1a70edd4bf, identyczny z uruchomionym lokalnie.
- Wygenerowano lokalny ZIP 1899857 B, dziewięć sekcji + MANIFEST (SHA-256, rozmiary, source run IDs, hashe ZIP i członów, cutoff prognoz i niezależny as-of audytu). Zachowane oryginalne struktury danych, brak eksperymentów oznaczony jawnie, wersje modeli częściowe. Nie opublikowano ZIP ani danych na publicznym GitHubie. Brak płatnych wywołań API, brak zmian silnika i harmonogramów.
- Lokalny test rzeczywistego eksportu i ponownego odczytu PASS; 8 testów jednostkowych PASS (poprawny pakiet, modyfikacja, obcy plik, nieznany schemat, starsze forecast/audit, duplikat klucza, NaN). Nie uruchamiano dedykowanego CI na GitHubie; PR nie został scalony. Walidator transportu nie potwierdza autentyczności nadawcy ani pełnego znaczenia wszystkich sekcji; ID runów dostarcza operator.
- Pozostałe: poprawić źródłowy manifest w odrębnym PR, formalnie rozwiązać definicję oceny 67/100, ustalić dokładne klucze i zweryfikowane wiązanie ABC/SHADOW z kursami i wynikami per linia, rozszerzyć walidację schematów i testy negatywne budowania, zabezpieczyć import przy identycznych znacznikach czasu lecz różnych hashach, dodać trwałe prywatne archiwum i uwierzytelnienie w odpowiednim etapie. MM-03 może wykorzystywać kontrakt do prototypu lokalnego bez TOP i bez publikacji, ale pełne zamknięcie MM-02 pozostaje otwarte.


## 25.11.2026 — MM-02.1–02.4 — zamknięcie technicznego eksportu lokalnego

**Decyzja:** budowa aplikacji nie czeka na 100/150 meczów. Rozdzielić gotowość panelu od gotowości matematyki modeli. MM-02 w zakresie lokalnego transportu i widoku badawczego gotowy do MM-03; nie oznacza pełnej produkcyjnej synchronizacji ani potwierdzenia wszystkich źródłowych rynków.

- Odczytano istniejący rejestr, PR #93 i rzeczywiste ZIP. Polityka na codex/multimodel-v2: A=.70, B=.75, C=.80, zgodność modeli maks. 10 pp dla wyników; v2_score=not_computed pending validated features. Nie wyliczać fikcyjnej oceny 67/100 i nie utożsamiać p z jakością. Widok badawczy możliwy na obecnych kryteriach; pole quality_score=null, top_eligible=false do uzgodnienia i walidacji osobnej oceny.
- PR #93 rozszerzony o panel_links.py: klucz fixture, market, selection, line, model, variant, freeze; zgodność źródłowego p z tolerancją 1e-5 jak w dotychczasowym PDF, Superbet, dokładny identyfikator rynku/wyboru ABC, wycena nie wcześniej niż freeze i przed kickoff, brak arbitralnego wyboru przy niejednoznacznym dopasowaniu. SHADOW pozostaje badawczy, overlay może nie zawierać ID źródłowej oferty; nie twierdzić, że to oficjalne rozliczenie. Nie mapować wyników po nazwie. Zachowano istniejące rozliczone dowody SHADOW z source_fixture_id; szczegółowe rozliczenia ABC nie są eksponowane przez obecny audyt (tylko agregaty), więc pozostają jawnie niedostępne.
- Wykonano lokalną próbę na poprzednim rzeczywistym pakiecie z 24.11 (audyt 25.11) za pomocą identycznego pliku panel_links.py (blob b67be67d2516f347a86b80b9fe7d316d33c232d4). 6992 wiersze ABC/SHADOW, 459 archived_research_quote (337 ABC, 122 SHADOW), 517 below_minimum_odds, 6016 missing_verified_quote, 195 zachowanych rozliczonych historycznych dowodów SHADOW. Wiersze wariantów nie są liczbą niezależnych meczów. Nie jest to aktualna oferta. Lokalny ZIP review zaktualizowany z istniejącego pakietu i zweryfikowany CRC/SHA-256, bez publikacji danych. Nie wykonano w tym przebiegu pełnego nowego wywołania zmienionego build() na trzech źródłowych ZIP.
- Exporter dodatkowo weryfikuje schemat event i SHADOW; odrzuca różne payload hashes przy identycznym cutoff forecast i audit, zachowuje idempotentny import. Dodano 8 testów (łącznie 16) i odizolowany workflow CI bez providerów. [CI 45687166249](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45687166249) SUCCESS, log job 139462699411: 16/16 OK. [PR #93](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/93) scalony squash do main: 70045dd48b63b2913ba39c43b0528467614e7363. Nie zmieniono wag ani harmonogramów.
- Naprawa literalnego backslash-n w źródłowym generatorze JSON przygotowana w odrębnym [PR #94](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/94), commit f64fcbec684dd64b7e37e75c9e16ed1a8c2d8a1b. Na rzeczywistym uszkodzonym pliku potwierdzono, że zamiana samej końcówki na newline daje poprawny JSON. PR #94 pozostawiono draft, ponieważ merge workflow uruchamia normalny ABC i potencjalnie płatny downstream; nie zmieniać harmonogramu w celu obejścia. Archiwalny plik nadal odizolowany, nie nadpisany.
- Otwarte ograniczenia nieblokujące MM-03: pełny semantyczny import PWA, mapowanie szczegółowych wyników ABC, pełna historia wersji, osobna zatwierdzona ocena jakości, prywatne przechowywanie i uwierzytelnienie (MM-05), formalna kalibracja/holdout. Publicznego repo nie zmieniono; żadnych nowych prywatnych danych ani tokenów na GitHub. Zero wywołań płatnych API w tej pracy. Następny krok MM-03: mobilne PWA z importem lokalnym, wykazem rynków i jawnie oznaczonymi brakami; TOP z wymaganiem 67/100 pozostaje zablokowany, widok badawczy działa.
