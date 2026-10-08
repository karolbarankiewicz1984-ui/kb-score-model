# API Market Scan — eksperyment grywalnych kursów

Stan: projekt do wdrożenia i testów, **nieaktywny** w codziennym workflow.

Repozytorium używa już v3.2; nie zastępujemy istniejącego modelu starszym v2. Nazwa 2.0 dotyczy nowego trybu publikacji, nie cofnięcia silnika.

## Warunki publikacji

- Dokładnie ten sam mecz, rynek, strona i linia w danych historycznych oraz notowaniu.
- Przedmeczowy, aktualny kurs >= 1.20 u co najmniej jednego dostawcy danych.
- Dowolny bukmacher z API może potwierdzić kurs; STS i Superbet są wyróżniane osobno, lecz ich brak w źródle oznacza „niepotwierdzone”.
- Ocena końcowa >= 67/100 (próg tymczasowy); nie traktować oceny jako skalibrowanego prawdopodobieństwa.
- Brak limitu pozycji. Kolejność: obecna ocena końcowa, bez sztucznego premiowania wysokiego kursu.
- Przy wielu liniach tego samego rynku pokazuj wszystkie spełniające warunki, grupowane według meczu. Nie traktuj ich jako niezależnych zdarzeń.
- Rozróżniaj żółte kartki od punktów kartkowych i kartek czerwonych.

## Audyt

Zapisuj liczby: kandydatów, bez kursu, poniżej 1.20, niezgodnych linii, poniżej progu oceny, zakwalifikowanych. Zachowaj pełną listę kandydatów i odrzuceń do rozliczenia, bez nadpisywania API PURE.

## Warunki aktywacji

1. Zweryfikować rzeczywisty schemat rekordów kursowych i kandydatów.
2. Dodać niezależny generator shadow report i testy (kurs 1.19/1.20, brak STS, błędna linia, brak notowania, duplikaty).
3. Porównać z raportem produkcyjnym na identycznych danych i sprawdzić rozliczenie po meczach.
4. Dopiero po akceptacji przełączyć harmonogram publikacji.

**Nienaruszalne:** KB Score CORE, KB N, DEV N, istniejący harmonogram i produkcyjny PDF.
