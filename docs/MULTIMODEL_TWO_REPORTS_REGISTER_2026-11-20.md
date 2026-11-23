# Rejestr zmian — MultiModel V2: dwa raporty końcowe

Data: **2026-11-20** (Europe/Warsaw). Zakres: `karolbarankiewicz1984-ui/kb-score-model`. Dotyczy wyłącznie sposobu publikacji informacji, **nie zmienia** modeli produkcyjnych, A/B/C, SHADOW ani danych wejściowych.

## Decyzja użytkownika

Codziennie prezentujemy tylko **dwa czytelne pliki PDF**:
1. `MULTIMODEL_YYYY-MM-DD.pdf` — wszystkie prognozy A/B/C i SHADOW z jednego, zamrożonego źródła: najlepiej oceniane pozycje (maksymalnie trzy na mecz w skrócie), dalej wszystkie mecze uporządkowane chronologicznie z rynkami (bramki, rożne, faule, kartki, 1X2, BTTS, handicapy), prawdopodobieństwami i **wyłącznie zweryfikowanymi kursami Superbet >=1.20**.
2. `MULTIMODEL_AUDYT_YYYY-MM-DD.pdf` — jeden dokument z historycznym audytem A/B/C, statusem rzeczywiście rozliczonych prognoz SHADOW i audytem prospektywnych ofert Superbet.

Materiały techniczne (oddzielne 7 PDF A/B/C, SHADOW, analizy Superbet, wszystkie JSON, metadane i archiwa) pozostają **niezmienione** w dotychczasowych artefaktach GitHub; użytkownik ma wybierać `multimodel-final-two-pdfs`. Nie kasujemy historycznych danych.

## Kod i wdrożenie

- `github_models/unified_output.py`: generator dwóch raportów; format Unicode DejaVu Sans, rozdzielenie wyników historycznych od prognoz testowych; deduplikacja identycznych wariantów A/B/C; grupowanie rynków pod meczem.
- `.github/workflows/multimodel-two-pdfs.yml`: osobny automatyczny workflow, uruchamiany po udanym OddsPapi, a także ręcznie / po zmianie wdrożeniowej. Pobiera istniejące archiwa GitHub, paruje **identyczne zamrożone `pitch_queue.json`** i archiwum A/B/C, odczytuje bez dodatkowych wywołań żadnego bukmachera, tworzy dokładnie dwa PDF-y. W razie niezgodności źródeł zamyka proces z błędem, nie skleja różnych meczów.
- Kursy są tylko historycznymi migawkami; zawsze pokazujemy brak kursu zamiast wartości zmyślonej. Nie podmieniamy fauli zawodnika na faule meczu, ani `bookings` na żółte kartki.
- Oddzielnie oznaczamy warianty modeli A/B/C i niekalibrowane prognozy SHADOW.
- **Nie ma obowiązkowej oceny 67/100**. Jest to skala punktowa, której nie wolno utożsamiać z prawdopodobieństwem 67%. Dotychczasowe progi prawdopodobieństwa wariantów A/B/C zostają niezmienione.
- Weryfikowany kurs: minimum 1.20. Rezerwa OddsPapi pozostaje 50 wywołań miesięcznie, limit operacyjny 200/250; nowy workflow zużywa **0 dodatkowych wywołań OddsPapi**.

## Weryfikacja pierwszego pakietu — 20.11.2026

Na zapisanych archiwach wykonano test lokalny składający jeden PDF z rynkami per mecz oraz jeden PDF audytu:
- Dzienny raport: 65 spotkań, 98 unikalnych pozycji A/B/C, 144 pozycje SHADOW, 17 pozycji z dopasowaną ceną Superbet; 10 poprawnych stron A4.
- Raport audytu: 27 historycznych archiwów A/B/C, pierwszy audyt SHADOW bez uprzednich archiwów, audyt Superbet z 0 niezależnie rozliczonymi jeszcze spotkaniami; 1 poprawna strona A4.
- W obu PDF sprawdzono podpis PDF i możliwość otwarcia. Żadnego wskaźnika nie wyliczono retrospektywnie z przyszłych notowań.
- Na wyraźne życzenie użytkownika dwa pierwsze PDF przesłano **jednorazowo** z podłączonego konta Gmail na ten sam własny adres e-mail. Nie ustanowiono harmonogramu dalszej wysyłki e-mail.

## Kryteria akceptacji operacyjnej

- [x] Workflow na `main` kończy się `success` i publikuje artefakt `multimodel-final-two-pdfs` z dokładnie dwoma PDF.
- [x] Oba PDF-y otwierają się, mają poprawne polskie znaki i czytelne tabele; sprawdzono również renderowanie stron.
- [x] Workflow jest niezależny od A/B/C i OddsPapi, nie generuje prognoz ani nie modyfikuje wag.
- [ ] Sprawdzić kolejne cykle `workflow_run` po pełnym A/B/C i Superbet, w szczególności zgodność identyfikatorów i dat po północy.

## Plan dalszych kroków (kolejność)

1. **Stabilność raportów:** kontrola pierwszego biegu na `main`, spójności zamrożonych danych, błędów GitHub Actions, jakości PDF i dostępności tylko dwóch wynikowych dokumentów.
2. **Odbiór przez użytkownika:** ewentualne uproszczenie sekcji najsilniejszych wskazań, wyróżnienie kursów, kompletności linii, godzin i czytelnego statusu SHADOW bez zmieniania obliczeń.
3. **Rozliczanie wyników:** po zakończeniu spotkań z zapisanymi kursami weryfikować rzeczywiste wyniki i dostępność statystyk; nierozliczone pozycje muszą mieć jednoznaczne przyczyny.
4. **Audyt próbek:** po co najmniej 100 różnych rozliczonych spotkaniach analizować na identycznej próbie hit rate, Brier/log loss, kalibrację, wpływ zgodności Superbet, oraz ROI wyłącznie z realnych historycznych kursów.
5. **Faule i kartki:** poszukać dokładnych rynków Superbet w już pobranych ofertach; ustalić zasady punktacji `bookings` i karty żółte, nigdy nie zastępować rynków niezgodnych.
6. **Handicapy SHADOW:** przed etykietą z kursem i rekomendacją udokumentować znaki handicapów i zasady rozliczenia w OddsPapi/Superbet.
7. **Nowe rynki:** dopiero po niezależnej historii wyników dołożyć strzały, celne strzały, spalone i ewentualnie inne kategorie do oddzielnego, rozliczanego SHADOW.
8. **Weryfikacja porównań:** sprawdzić czy podział według rynku, ligi i przedziału P daje rzeczywistą poprawę; nie dostosowywać wag tylko na podstawie surowego P modelu.
9. **Automatyczna wysyłka e-mail (opcjonalna):** osobna decyzja użytkownika. Jednorazowa wysyłka z Gmail nie upoważnia do włączenia codziennych e-maili.
10. **Długoterminowa retencja:** kontrolować 30/90-dniowe terminy wygaśnięcia artefaktów i zasady archiwizacji, by audyt prospektywny miał komplet danych.

### Zakres zablokowany do dalszej walidacji

- STS nadal niedostępny w obecnej subskrypcji OddsPapi — nie oznaczać STS jako obecne.
- Brak wycenionych dokładnie fauli/kartki — nie generować fikcyjnych kursów.
- SHADOW to niekalibrowana analiza; brak dowodu dodatniego EV.
- Anulowany pomocniczy smoke z 19.11, częściowy terminarz 25–26.11 oraz status 0 rozliczonych nowych próbek pozostają osobnymi pozycjami monitoringu, nie przesłaniają generowania użytkowych raportów.

## Aktualizacja 20.11.2026 — etapy I/II: faule, kartki, handicapy

Pełny **10-krokowy rejestr dalszych działań**, aktualne dowody z archiwum OddsPapi, kryteria weryfikacji rynku, historia zmian i warunki kalibracji:

**[MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md](MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md)**

Dodano rozdzielanie jednostek *bookings* od żółtych kartek, fauli gracza od fauli meczu oraz handicapów azjatyckich od europejskich; wynik semantyczny zostanie dodany do istniejącego PDF audytu. Modele A/B/C i SHADOW pozostają bez zmian, zero nowych wywołań OddsPapi. Integracja rzeczywistych reguł rozliczeń i dalsza kalibracja są oddzielnymi krokami zależnymi od weryfikacji danych.

## Kontrola końcowa 20.11.2026 — po rozbudowie zasad rynków

- [x] Nowy workflow dwudokumentowy zakończył się sukcesem na `main` i opublikował artefakt `multimodel-final-two-pdfs`, dokładnie 2 PDF.
- [x] Oba pliki przeszły kontrolę otwieralności/treści w GitHub Actions — 10 i 1 strona.
- [x] Rozbudowa nie wywołuje OddsPapi i nie zmienia wag prognoz A/B/C/SHADOW.
- [ ] Nadal kontrolować kolejne cykle oraz kompletność historycznych źródeł i rozliczeń.

Źródło: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44728416352

Reguły fauli, kartek i handicapów podlegają osobnemu testowi semantycznemu: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44728416499.

## Aktualizacja po potwierdzonych dopasowaniach handicapów i audycie historycznym (20.11.2026)

- PR #71 wprowadza dokładne dopasowanie źródłowych handicapów azjatyckich ±1,5 oraz nowe badawcze rozliczanie zapisanych cen BTTS/handicap; PR #72 poprawia label dostawcy i PR #73 dopasowanie kursów tylko do daty PDF.
- Ostateczne dwa PDF-y 20.11.2026 w GitHub Actions: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44733417657 (PASS): główny 10 stron, audyt 2 strony, cena w 29 pozycjach dziennych, bez zmiany modelu lub dodatkowych zapytań OddsPapi.
- Audyt 200 zarejestrowanych ofert badawczych BTTS/handicap ma **0 niezależnych wyników `settled`**; raport poprawnie nie podaje ROI ani nie uważa tych zakładów za rozliczone przez Superbet. Wynik: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44732878148.
- Oddzielne źródła OPTA i jednostki kartek pozostają nieweryfikowane; nie przywracać fikcyjnych ofert fauli/kartkowych w głównym PDF.
- Rozwinięty rejestr wszystkich kroków i spraw otwartych: [MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md](MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md).

## Aktualizacja 21.11.2026 — raportowanie opóźnionych wyników

- Potwierdzono, że historyczny `priced_shadow_settlement` z 21.11 01:32 UTC miał **200** wycenionych prognoz, w tym **180** przed rozpoczęciem i **20** z czterech meczów 20.11 jeszcze bez niezależnie dopuszczonego wyniku; to NIE jest automatycznie błąd mapowania.
- Importer `football-data.co.uk` stosuje datę meczu +2 dni jako zachowawczą granicę końca spotkania. Poprawka w [PR #79](https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/79) pokazuje w drugim PDF liczbę prognoz oczekujących na publikację wyniku (48 h od kickoff), ale nie zmienia wydrukowanych prognoz ani nie dodaje fikcyjnych rozliczeń.
- Nadal obowiązuje **dokładnie 2 PDF**, kursy rzeczywiste >=1,20, niezależne SHADOW i brak automatycznej kalibracji. Przyszły audyt musi potwierdzić, czy po dostępności prawdziwych wyników meczów przejście z `pending` na `settled` działa; do tej chwili skuteczność pozostaje niewyliczona.
- Testy zmiany: [21/21 PASS](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/44934084567). Więcej dowodów: [główny rejestr rozliczeń](MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md).

## Aktualizacja 23.11.2026 — pierwsze rozliczone A/B/C i SHADOW

- [Pełny audyt GitHub Actions 45137989936](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/45137989936) zakończony `success`: **30** wycenionych pozycji A/B/C i **20** wycenionych pozycji SHADOW zostało niezależnie rozliczonych z **tych samych czterech** meczów. Nie sumować liczby pozycji jako liczby niezależnych spotkań. Pozostało 643 nierozstrzygniętych A/B/C, 657 przyszłych A/B/C i 481 oczekujących SHADOW.
- Techniczny `MULTIMODEL_CALIBRATION_READINESS.json` wymusza `calibration_authorized=false`; minimum 20/100 różnych meczów nieosiągnięte. Bez zmiany wag, danych przedmeczowych, min. kursu 1,20 i zasad wydawania dwóch PDF.
- Dwa końcowe dokumenty dla użytkownika nadal obowiązują. Bieżący nocny audyt publikuje JSON i techniczny PDF w `oddspapi-rolling-audit`; włączenie zaktualizowanych liczników do kolejnego głównego `MULTIMODEL_AUDYT_YYYY-MM-DD.pdf` następuje poprzez następne udane uruchomienie generatora dwóch PDF po OddsPapi. Nie oznaczać starych raportów jako nowe.
- Pełne dane, źródła czterech wyników, problemy Bookings/OPTA i warunki kalibracji: [rejestr rynków](MULTIMODEL_MARKET_RULES_REGISTER_2026-11-20.md).
