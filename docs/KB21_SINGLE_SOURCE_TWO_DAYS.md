# KB Score 2.1 — nowy terminarz: jedno API, dwa dni

## Zasada

Jedynym źródłem terminarza dla nowego trybu KB Score jest **API-Football**.
Każdy przebieg pobiera dwie daty w strefie Europe/Warsaw: **dzisiaj i jutro**.
Trzeciego dnia nie pobiera. Jeżeli mecz nie jest widoczny w poprawnej odpowiedzi
API-Football, nie jest kandydatem do badania. Nie dodajemy go z ESPN, KNVB,
UEFA ani football-data.org.

- Zapisujemy wszystkie zwrócone przez dostawcę wydarzenia z obu dni z ID,
  godzinami, rozgrywkami i rzeczywistymi statusami.
- Do dalszej analizy KB21 trafiają tylko przyszłe mecze NS (not started)
  w zakresie rozgrywek określonym przez istniejący filtr KB21.
- Przełożone, odwołane, rozpoczęte i zakończone mecze pozostają w wykazie
  dostawcy, ale nie trafiają do kandydatów przedmeczowych.
- Poprawna pusta odpowiedź to zero kandydatów W TYM API, nie dowód o świecie.
- Awaria, brak klucza, zła data, powtórzone identyfikatory, błędne godziny
  lub niespójne dane kończą się błędem, a nie potwierdzeniem pustego dnia.
- Endpoint API-Football fixtures według daty odrzuca parametr page.
  Odczyt jest pojedynczą odpowiedzią z kontrolą metadanych paging.

## Gdzie szukać

GitHub Actions: KB21 SINGLE SOURCE API-Football today+tomorrow.

Artefakt: kb21-api-football-two-days (retencja 30 dni).

- KB21_API_CALENDAR_YYYY-MM-DD.md — czytelny terminarz dla danej daty.
- KB21_API_CALENDAR_YYYY-MM-DD.json — pełny zestaw wydarzeń i kandydatów.
- KB21_INPUT_YYYY-MM-DD.json — faktyczny wkład terminarzowy do KB21,
  bez wymyślonych statystyk lub ocen.
- KB21_RESEARCH_YYYY-MM-DD.json — istniejąca jawnie eksploracyjna
  diagnostyka, nigdy oryginalny P(model).
- SINGLE_SOURCE_MANIFEST.json — źródło, daty, stan i liczniki.

Harmonogram: raz dziennie o 08:00 UTC, czyli 10:00 czasu polskiego latem,
09:00 zimą; GitHub może opóźnić wykonanie. Każdy raport ma faktyczną
datę i godzinę pobrania.

## Co ze 149 brakami i 42 podpisami?

Pozostają prawdziwe w ARCHIWALNYM Calendar Gate obejmującym
14 rozgrywek na 3 daty. Nie zostały naprawione ani sfałszowane.

W nowym trybie zamiast historycznych 42 kontroli uruchamia się
techniczny SINGLE_SOURCE_GATE=PASS_SOURCE, który sprawdza poprawność
obu dni z jednego API. To zmiana polityki zakresu, nie retroaktywne
zatwierdzenie dawnej procedury.

Stare automatyczne harmonogramy KB21 dla ESPN/organizerów i
football-data.org zostały wyłączone. Workflowy pozostają dostępne
na życzenie do analiz archiwalnych.

## Co pozostaje do odbudowy

Terminarz NIE jest prognozą. Oryginalny KB Score 2.1 nadal wymaga
niezależnych, udokumentowanych STR/35, QUAL/35, MATCH/30 oraz
osobnego P(model) wyznaczonego przed odczytem kursów. Obecny adapter
celowo zachowuje te oceny jako null. PASS_SOURCE nie upoważnia
do PLAY, nie tworzy rekomendacji i nie wpisuje nic do historii N.

API Market i PitchAPI to niezależne silniki. Również korzystają z
API-Football, ale ich wyników nie kopiujemy do oryginalnego KB21
i nie zmieniamy ich dotychczasowej metodologii.

## Dodatkowo: eksperymentalne prawdopodobieństwa z prawdziwych goli

Raporty KB21_FORM_YYYY-MM-DD.pdf zawierają teraz pomocnicze wartości
1/X/2 i over 2,5 dla maksymalnie trzydziestu meczów na dzień (od 18.10.2026; wcześniej pięciu). Oblicza je
ISTNIEJĄCY tools.kb21_api_diagnostic.diagnose; NIE są to odbudowane
historyczne P(model), Sport Score ani rekomendacje.

- Podstawa: średnie zdobytych i straconych goli z ostatnich 5–10
  zakończonych gier obu drużyn; model Poissona z tych średnich.
- Model nie ma rzeczywistych xG, ELO, korekt siły ligi, absencji i
  kalibracji empirycznej. Wyniki to hipotezy do audytu, nie value.
- Brak wystarczającej próby = INSUFFICIENT_HISTORY, brak procentów.
- Oddzielne prognozy KB21_SHADOW_YYYY-MM-DD.json zawierają ID, start
  meczu, moment uruchomienia oraz szacunki przed wynikiem. Dzięki temu
  można później uczciwie porównać predykcje z rozstrzygnięciem bez
  odtwarzania ich po poznaniu rezultatu.
- experimental_goal_model.p_model i analyst_assessment.P_model_pre_odds
  zawsze pozostają null; brak kursów, PLAY oraz zapisów do historii N.
