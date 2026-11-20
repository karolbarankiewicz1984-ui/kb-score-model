# MultiModel V2 — etap I/II SHADOW i Superbet — rejestr wdrożenia 2026-11-20

## Ustalenia użytkownika
- Punktowa ocena jakości **67/100 NIE jest obowiązkowym filtrem**. NIE utożsamiać jej z prawdopodobieństwem 67%.
- Warianty A/B/C mają nadal własne niezmienione prawdopodobieństwa i progi (A >=70%, B >=75%, C >=80%). Nie zmieniamy wag, kalibracji ani istniejących prognoz.
- Kurs rzeczywisty musi być **>=1,20**, dokładnie dla zadanego rynku, strony, linii i okresu, zapisany przed rozpoczęciem meczu.
- Maksymalnie 3 najważniejsze propozycje na mecz w skrócie; kompletny wykaz pozostaje w PDF/JSON.
- Bez dodatkowych płatnych wywołań OddsPapi przez rozszerzenia; collector Superbet nadal chroni miesięczny limit 200/250, rezerwę 50.
- Brak danych statystycznych/rynku nie może zablokować oryginalnego procesu A/B/C; braki muszą być widoczne w raporcie.

## Co zostało zakodowane na osobnej gałęzi SHADOW
1. \`github_models/shadow_markets.py\`: dodatkowe BTTS TAK/NIE oraz handicap półbramkowy ±1,5 z niezależnej historii opublikowanych wyników i ostrożnego uproszczonego Poissona. Status **uncalibrated_research**, bez zakładania trafności.
2. \`shadow_runner.py\`: JSON zawierający pełną listę, źródłowe liczności próbek i przyczyny wykluczeń.
3. \`shadow_reports.py\`: 7 osobnych dziennych polskich PDF \`MULTIMODEL_V2_SHADOW_YYYY-MM-DD.pdf\`, manifest i pełne listy bez fałszywych kursów.
4. \`shadow_audit.py\`: dopasowanie końcowych wyników według zamrożonej tożsamości, deduplikacja archiwów, hit rate/Brier/log loss osobno dla BTTS i handicapu. Brak ROI bez realnych kursów.
5. \`shadow_superbet.py\`: **tylko odczyt** z istniejącego \`collection.json\`, ścisłe dopasowanie BTTS Full Time Yes/No do Superbet; oddzielny PDF \`MULTIMODEL_V2_SHADOW_SUPERBET.pdf\`, JSON z pełną pulą i audyt katalogu pobranych rynków.

## Status rynków
| Rynek | Model SHADOW | Weryfikowany kurs Superbet | Ograniczenie |
|---|---|---|---|
| BTTS pełny mecz | Tak, niezależna estymacja z wyników | Tak, **tylko** Yes/No Full Time >=1,20 z archiwum | P niekalibrowane |
| Handicap ±1,5 | Tak, modelowa strona home/away | **Nie** do czasu weryfikacji znaczenia znaku i zasad rozliczania azjatyckich handicapów u dostawcy | Tylko testowy, bez oznaczenia PLAY |
| Faule i żółte kartki | Istniejące prognozy A/B/C; bez modyfikacji | Nadal brak zweryfikowanych exact-total quotes; osobne ostrzeżenia zdrowotne | Nie podmieniaj fauli zawodników; bookings nie musi oznaczać yellow cards |
| Strzały, strzały celne, spalone | **Nie** — brak potwierdzonej historii wymaganej do budowy modelu | Nie dopasowywać kursów do fikcyjnych prognoz | Widoczne jako zablokowane C |

## Połączenie z istniejącymi harmonogramami
- \`github-models-v2-daily-audit.yml\`: dodany **nieblokujący** etap SHADOW po obliczeniu istniejącego A/B/C. Dodane pliki PDF/JSON i manifest do aktualnego artefaktu.
- Ten sam workflow archiwizuje \`shadow/DATE/RUN_ID.json\` **tylko gdy został rzeczywiście wyliczony**; nienaruszalny zestaw \`frozen/queues/markets\` pozostaje bez zmian.
- Po wynikach \`shadow_audit.py\` bada zamrożone wyniki; błędy SHADOW są oddzielone od rozliczania A/B/C.
- \`oddspapi-daily.yml\`: po standardowym pobraniu cen z Superbet generuje z tych samych zapisanych danych **oddzielny** raport SHADOW/BTTS. Błąd SHADOW nie zatrzymuje głównego raportu kursów.
- Oznaczenia prezentacyjne **A = dokładny kurs**, **B = model bez kursu**, **C = brak zweryfikowanych danych** NIE zastępują wariantów modeli A/B/C w głównym raporcie.

## Walidacja i warunki awansu
- [x] Napisane testy bezpieczeństwa SHADOW i uruchomione osobne GitHub Actions (PASS 2026-11-20): https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44702582786
- [ ] Zatwierdzić PR nowego kodu do \`codex/multimodel-v2\` i PR wdrożeniowego do \`main\`.
- [ ] Potwierdzić nowy rzeczywisty 7-dniowy workflow, liczbę prognoz BTTS/handicap, siedem otwieralnych PDF, zamrożony plik SHADOW i nowy raport SHADOW-Superbet.
- [ ] Po rozliczeniu minimum 100 **niezależnych** meczów przejrzeć skuteczność i kalibrację przed propozycją zmiany produkcyjnych wag.
- [ ] Rozszerzyć handikapy o zgodne z regulaminem Superbet ceny po sprawdzeniu konwencji. Nie wciskać handicapów do katalogu PLAY przed dowodem.
- [ ] Dopiero po niezależnym potwierdzeniu danych i wyników dopisać generatory strzałów, strzałów celnych oraz spalonych.

**Nie twierdzimy, że prognozy SHADOW są już skalibrowane ani że nowe źródło udostępnia kurs dla każdej kategorii. Nie zwiększono budżetu.**
