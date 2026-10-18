# KB21 — prospektywny audyt testowych prognoz 1/X/2 i over 2,5

## Dlaczego

Dotychczasowe `KB21_SHADOW_YYYY-MM-DD.json` były wyłącznie zamrożonymi,
pomocniczymi prognozami z rzeczywistych wcześniejszych goli (nie xG).
Bez rozliczenia po meczu nie można zmierzyć ich skuteczności, kalibracji
ani porównać z historycznym, osobnym KB Score 2.1.

**To NIE jest przywrócenie oryginalnego KB21 P(model), typy bukmacherskie
ani rozliczanie głównego N.** Nazwa shadow oznacza niezależną hipotezę
statystyczną z niedoskonałym zbiorem danych.

## Działanie

Codziennie o 07:00 UTC, dla **wczoraj** w strefie Europe/Warsaw:
1. Dzienny GitHub Actions wybiera wyłącznie udane przebiegi głównej gałęzi
   `KB21 SINGLE SOURCE API-Football today+tomorrow` z dnia badanego
   oraz poprzedniego. Nie odtwarza prognoz na podstawie aktualnych danych.
2. Pobiera istniejące artefakty `kb21-api-football-two-days` bezpośrednio
   z GitHub Actions; odczytuje zapisany snapshot i jego oryginalne
   `SINGLE_SOURCE_MANIFEST`, `KB21_API_CALENDAR` oraz
   `KB21_FORM_MANIFEST`.
3. Sprawdza oryginalny ID meczu, drużyny, datę, godzinę, czasy pozyskania,
   brak ceny, oryginalnego P(model) i brak informacji o końcowym wyniku.
   Tylko prognoza zapisana **PRZED startem** jest dopuszczalna.
4. Dla meczu powtarzającego się w kilku przebiegach wybiera pierwszą
   kwalifikującą się prognozę z rzeczywiście obliczonymi procentami.
5. Po zakończeniu dnia pobiera wyniki z API-Football dla oryginalnej
   daty. Rozlicza wyłącznie status `FT` i spójny wynik pełnego czasu
   w `goals` oraz `score.fulltime`. Start przesunięty o więcej niż
   pięć minut, dogrywka, brak wyników, niezgodność źródła lub inne
   statusy oznaczają brak rozliczenia — NIE przegraną ani wygraną.
6. Raportuje trafność maksymalnego z 1/X/2, wieloklasowy Brier 1/X/2
   oraz binarny Brier over 2,5. Każdy mecz liczy się tylko raz.
   Nie sumujemy 1/X/2 i over 2,5 jako niezależnych wydarzeń.

## Wyniki i granice

GitHub workflow: `KB21 shadow prospective outcome audit`
Artefakt: `kb21-shadow-outcome-audit` (30 dni)

- `KB21_SHADOW_AUDIT_YYYY-MM-DD.md` — czytelne rozliczenie.
- `KB21_SHADOW_AUDIT_YYYY-MM-DD.json` — każdy źródłowy snapshot, hash
  SHA256 pliku, ID, czas zamrożenia, prognoza oraz wynik i status.

Ten automat wykonuje `GET` na cudzych prognozach/rezultatach
i **nie zapisuje** nic do repozytoryjnej historii modelu, Google Sheets,
N200, DEV, API Market, PitchAPI ani oryginalnego P(model).
Nie dopisuje „zerowych” albo wymyślonych typów, gdy w archiwum
nie ma żadnej prawdziwej prognozy.

Brak niezależnego porównania do innego dostawcy wyników i mała próba
oznaczają, że początkowe oceny są tylko diagnostyczne.
Wiarygodną skuteczność oceniamy po większej liczbie **różnych,
rozstrzygniętych spotkań**, z rozdzieleniem lig i rynków.

Uruchomienie testów: `python -m unittest tests.test_kb21_shadow_audit -v`.
