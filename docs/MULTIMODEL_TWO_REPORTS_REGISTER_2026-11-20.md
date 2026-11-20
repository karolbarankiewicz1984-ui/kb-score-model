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

- [ ] Po scaleniu zmian automatyczne uruchomienie workflow na `main` kończy się `success` i publikuje artefakt `multimodel-final-two-pdfs` zawierający dokładnie dwa pliki PDF.
- [ ] Każdy plik otwiera się, ma prawidłową liczbę stron i polskie znaki; dostateczna czytelność tabel.
- [ ] Nowy workflow nie wstrzymuje obecnego A/B/C, Superbet ani audytu. Nigdy nie tworzy prognoz i nie modyfikuje wag.
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
