# PitchAPI — izolowane archiwum danych historycznych xG

## Stan i przeznaczenie

PitchAPI jest osobnym źródłem danych o **zakończonych** meczach.
Moduł `tools/pitchapi_xg_lab.py` nie importuje ani nie wywołuje silnika KB Score 2.1,
API Market ani modułów kalibracji. **Żadne wyniki xG nie są obecnie dopisywane do oceny typów.**

**Historyczne xG nie jest predykcją przedmeczowego xG**. Jeżeli powstanie
później osobny moduł modelowania, każda cecha historyczna musi pochodzić
wyłącznie z meczów rozegranych przed ocenianym spotkaniem. Bez przecieku danych.

## Źródła i bezpieczeństwo

- Klucz PitchAPI: GitHub Actions Secret `PITCHAPI_API_KEY`.
- Oficjalne SDK `pitchapi==0.1.6`; komunikacja tylko HTTPS.
- Repozytorium: `data/api_football/daily/YYYY-MM-DD.json` — oryginalne pliki API-Football pozostają bez zmian.
- Wyniki PitchAPI: `data/pitchapi/daily/YYYY-MM-DD.json`.
- Porównanie: `reports/pitchapi/YYYY-MM-DD.json` i czytelne `reports/pitchapi/YYYY-MM-DD.md`.
- Workflow `.github/workflows/pitchapi-xg-lab.yml`: ręcznie albo codziennie o 04:57 UTC
  (po API-Football daily collector z godz. 04:17 UTC), zbiera poprzedni dzień według czasu w Warszawie.
- Limit pobierania: maksymalnie 75 spotkań na dzień; na zatłoczone dni
  priorytet mają europejskie puchary i duże ligi. W pliku pozostaje liczba
  wszystkich meczów dostępnych tego dnia, aby było widać uciętą część.
- Brak zmian w licznikach N, parametrach modelu, rankingu, typach czy PDF.

## Reguły jakości

1. Sumujemy *pobrane ze strzałów* xG osobno dla gospodarzy i gości po stabilnym ID drużyny PitchAPI.
2. Niepełna lista xG oznacza `xg: null`, nie wartość `0`.
3. Odrzucamy niejednoznaczne połączenia, niewłaściwe rozgrywki oraz zbyt duże różnice godzin.
4. Gdy wynik meczu jest różny między dostawcami, nie przekazujemy wartości xG do
   zbioru potencjalnie użytecznego w **historycznej** kalibracji.
5. Wartości xG różnych dostawców **nie są równoważne i nie mogą być sumowane** w jeden wskaźnik.
6. Liczba strzałów może różnić się definicją między dostawcami; obie wartości
   są przechowywane osobno jako materiał audytowy.
7. Obsługiwane aliasy nazw klubów są jawne; unikalność meczu i zgodność rozgrywek
   oraz wyniku nadal są wymagane.

## Wynik pilota

Dla 2026-10-14 zweryfikowano:

- 37 meczów PitchAPI, kompletne dwustronne xG w 30.
- 9 meczów w odpowiednim archiwum API-Football, 9/9 sparowanych po poprawce
  na różnice nazw LASK/Lask Linz i AEK Athens/AEK Athens FC.
- 9 par o zgodnych wynikach i kompletnym xG.
- 0 zmian w KB N, DEV N i wynikach typów.

To nie jest jeszcze walidacja poprawności prognoz modelu ani jego wzrostu skuteczności.

## Kolejne kroki (wymagają osobnego zatwierdzenia)

- Zebrać co najmniej kilka tygodni historycznych meczów z kompletnego, stałego zakresu.
- Zmierzyć kompletność dla Ligi Europy, Ligi Konferencji i lig głównych.
- Niezależnie skalibrować kroczące historyczne xG z prawidłowym odcięciem czasu.
- Dopiero po backteście porównać model wzbogacony o xG z dotychczasowym,
  bez zastępowania żadnej starej metodologii w locie.
