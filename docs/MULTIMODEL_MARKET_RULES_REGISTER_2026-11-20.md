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
