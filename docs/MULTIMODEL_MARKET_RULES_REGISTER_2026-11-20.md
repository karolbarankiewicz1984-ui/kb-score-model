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
