# KB21 — aktualna siła ligowa i poziom ostatnich rywali

## Dlaczego nie ClubElo

W 2026 r. dawny publiczny endpoint CSV ClubElo jest niedostępny lub
przeszedł za uwierzytelnienie. Nie używamy niedziałającego wejścia,
nie przypisujemy „Elo” do statystyki goli ani aktualnej pozycji.

**To świadomie oddzielne źródło DANYCH O SILE W SEZONIE, NIE ELO.**
Wykorzystujemy znane, dokumentowane
`API-Football /standings?league=ID&season=YEAR`.

## Co zbieramy

- Dokładnie jeden odczyt `standings` na unikatowy identyfikator ligi
  i sezonu na DWIE daty terminarza. Maksimum 16, rezerwa 25 wywołań
  z dziennego limitu. Nie pobieramy innych terminarzy.
- Tylko ligi krajowe z istniejącej listy `DOMESTIC`.
  Puchary i reprezentacje nie dostają sztucznej „tabeli”.
- Punkty, miejsce, mecze rozegrane, bilans bramkowy, punkty/mecz,
  wyniki u siebie/na wyjeździe. Różnica miejsc lub punktów/mecz
  jest tylko obserwacją między dwiema DRUŻYNAMI W TEJ SAMEJ TABELI,
  nie szacowaną przewagą ELO.
- Identyfikacja wyłącznie przez numer zespołu API, ten sam numer
  ligi i sezonu oraz jedną grupę tabeli. Błędy API, brak drużyny,
  różne grupy lub zbyt mała liczba spotkań nie dają porównania.
- Dla maksymalnie pięciu ostatnich FT zawodów każdej drużyny
  można dołączyć **obecne** punkty/mecz dawnych przeciwników,
  ale TYLKO gdy zachowała się tożsamość rywala, identyfikator
  ligi i sezon, a rywal jest widoczny w tej samej tabeli.

## Ograniczenie metodologiczne

To nie są odtworzone oceny rywali z chwili ich dawnych meczów.
Dzisiejszy ranking uwzględnia rezultaty osiągnięte w międzyczasie,
dlatego służy jako aktualny opis siły, a nie punktowy
historyczny sygnał obliczeniowy. Nigdy nie tworzymy z tych danych
ani `STR/35`, `QUAL/35`, `MATCH/30`, `P(model)`, EV ani PLAY.

Mecz rozpoczęty przed pobraniem tabeli nie otrzymuje nowego
kontekstu przedmeczowego. Prognozy cienia z poprzednich dni
nie są przeliczane, stary KB N, API Market i PitchAPI bez zmian.

Jeśli optional endpoint zawiedzie, zapisujemy uczciwy brak tabeli
i nie zatrzymujemy głównego terminarza oraz historii goli.
Nie podajemy zera zamiast pustego punktu.

## Pliki i działanie

Codzienny `KB21 SINGLE SOURCE API-Football today+tomorrow` dodaje do
już istniejącego artefaktu:

- `KB21_STANDINGS_CONTEXT_YYYY-MM-DD.md` — kompaktowe zestawienie;
- `KB21_STANDINGS_CONTEXT_YYYY-MM-DD.json` — dane i ID;
- `KB21_STANDINGS_CONTEXT_MANIFEST.json` — liczba udanych powiązań,
  wywołania, statusy źródeł i kontrole izolacji.

Testy: `python -m unittest tests.test_kb21_standings_context -v`.
