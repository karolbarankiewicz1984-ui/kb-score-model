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

- [ ] PR z testami i kodem scalony do `main`.
- [ ] GitHub Actions z testami oraz odczytem archiwum przechodzi pomyślnie.
- [ ] W audycie końcowym istnieją dwa poprawne PDF; brak trzeciego raportu dla użytkownika.
- [ ] Przesłany raport stanowi dokumentację postępu, nie obietnicę, że handicapy czy kartki zostały już zatwierdzone do obstawiania.

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
- Bieżąca korekta opisowa PDF (w tym usunięcie sprzecznego komunikatu o niepotwierdzonym znaku AH) została dodana w osobnym PR do akceptacji.

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
