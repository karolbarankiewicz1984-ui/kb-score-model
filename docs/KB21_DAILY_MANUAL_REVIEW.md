# KB Score 2.1 — podpisy dzienne, bez ponownego zatwierdzania po przesunięciu okna

## Dlaczego to jest potrzebne

Wcześniejsze podpisy obejmowały nazwę zakresu, np. 2026-10-17_to_2026-10-19.json.
Po przesunięciu raportu na 18–20 października kod nie odnajdywał już
oddzielnego podpisu dla 18 i 19 października.

Od teraz zatwierdzony dzień jest przechowywany osobno:
data/kb21_calendar_reviews/YYYY-MM-DD.json

Zmiana listy meczów, błędne źródło ESPN lub spóźniony podpis oznaczają
odrzucenie dotychczasowej decyzji, nie automatyczne dalsze zatwierdzenie.

## Co powinien zrobić rzeczywisty niezależny analityk

1. W najnowszym przebiegu GitHub Actions: KB21 recovery (official fixture diagnostics)
   pobierz artefakt kb21-legacy-api-free-diagnostic.
2. W katalogu human-review-forms znajdziesz trzy osobne formularze JSON,
   z datą w nazwie. Są NIEPODPISANE, choć część meczów już wypełnia automat.
3. Dla wybranego dnia osobiście sprawdź WSZYSTKIE 14 terminarzy organizatorów.
   Uzupełnij każdą pozycję competitions:
   - fixtures: faktycznie potwierdzona lista spotkań i godziny ze strefą;
   - captured_at: rzeczywisty czas kontroli ISO 8601 ze strefą;
   - reviewer: tożsamość osoby wykonującej kontrolę;
   - full_day_checked: true dopiero gdy cały terminarz dnia jest sprawdzony;
   - confirmed_zero_matches: true WYŁĄCZNIE dla niezależnie zweryfikowanego
     dnia bez meczu w danej lidze; false gdy mecz istnieje.
4. Po pełnym sprawdzeniu, przed pierwszym meczem całego dnia (spośród 14 lig),
   uzupełnij approval rzeczywistym reviewer, approved_at oraz
   attests_independent_official_review: true.
5. Zapisz w commit/PR pod dokładną nazwą:
   data/kb21_calendar_reviews/YYYY-MM-DD.json
6. CI zweryfikuje daną datę względem AKTUALNYCH meczów ESPN. Tylko wtedy
   poprzedni podpis będzie odnajdywany po przesunięciu trzydniowego okna.

Jeśli nie ma żadnego kandydata na mecz w całym dniu, brak meczów wymaga
kontroli i podpisu PRZED początkiem doby w Warszawie. Po terminie nie
wolno podpisywać pustego dnia wstecz. W pozostałych przypadkach podpis musi
wyprzedzać pierwszy kickoff całego dnia.

## Co może zrobić automat

- Przygotowuje trzy niepodpisane formularze i wskazuje deadline.
- Ponownie wykorzystuje rzeczywiście zapisane podpisy per data.
- Sprawdza pełne 14 kart, zdrowie źródła, zgodność par i godzin,
  rzeczywisty czas i wymagane pola; każda sprzeczność zatrzymuje import.
- Wynik zapisuje w human-review-persistent-status.json oraz
  human-review-inventory-combined.json.
- Nigdy nie dopisuje nazwiska recenzenta, daty zatwierdzenia,
  potwierdzenia dnia bez meczów ani PLAY.

Stary format podpisów zakresowych jest nadal obsługiwany. Gdy stare
zakresowe i nowe dzienne podpisy kolidują, automat przerywa pracę.
W przypadku częściowo zatwierdzonych trzech dni Calendar Gate nadal
jest BLOCKED globalnie, ale prawidłowa kontrola jednego dnia jest
zachowana bez potrzeby jej ponownego sporządzania.

UWAGA: zawartość ręcznie wypełnionego JSON nie jest podpisem kryptograficznym.
Kod sprawdza spójność i terminy, a nie dowodzi, że analityk faktycznie
odwiedził stronę organizatora. Potrzebna jest rzeczywista weryfikacja.
