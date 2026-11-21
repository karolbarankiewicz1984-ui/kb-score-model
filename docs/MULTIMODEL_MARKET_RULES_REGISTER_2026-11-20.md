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
