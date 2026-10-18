# KB21: prospektywny test A/B — historyczne xG kontra rzeczywiste gole

## Co jest teraz porównywane

To osobny eksperyment, **nie odzyskanie oryginalnego wzoru P(model) KB Score 2.1**.

- **Model G:** wcześniej działający `kb21-api-last10-goals-shadow-v1`,
  oparty na średniej faktycznych goli zdobytych i straconych w ostatnich meczach.
- **Model X:** `kb21-pitchapi-mean-xg-poisson-shadow-v1`,
  odrębny, jawny model: `lambda_home = (xGF_home + xGA_away)/2`
  i `lambda_away = (xGF_away + xGA_home)/2`, Poisson do 24 goli,
  1/X/2 oraz P(over 2,5).
  xGF i xGA to faktyczne **historyczne xG PitchAPI** z 3–5
  wcześniejszych spotkań, a nie przewidywane xG najbliższego meczu.
- Szacunki są nieskalibrowane: brak korekty przewagi własnego boiska,
  siły rywali, transferów, absencji, ELO lub kursów. Wersja jest jawnie
  oznaczona i ma niezmienne zasady w dniu przechwycenia.

Nie dopasowujemy parametrów do wyniku ocenianych spotkań.
Oba modele biorą udział **tylko dla tych samych meczów**, gdy istnieje
wcześniej zapisana niezależna prognoza z goli i wiarygodny snapshot
historycznych xG PitchAPI, a chwila łączenia jest wcześniejsza
od rozpoczęcia meczu.

## Zamrażanie

Dzienny `KB21 SINGLE SOURCE API-Football today+tomorrow` zapisuje:
`KB21_XG_V_GOALS_SHADOW_YYYY-MM-DD.json` i `.md`.

Każda para zawiera:

- Kanoniczne `fixture_id` API-Football, obie nazwy, start UTC.
- Oryginalną **wcześniejszą** prognozę Modelu G bez ponownych obliczeń.
- Obliczoną przed meczem prognozę Modelu X.
- Znaczniki czasu: starszą migawkę PitchAPI, freeze Modelu G i freeze
  porównania; brak pola wyniku końcowego.
- Identyfikator meczu źródłowego PitchAPI i liczności historii xG obu drużyn.
- Jawne `original_kb21_p_model: null`, `odds: null`,
  `selection: null`, `safe_to_publish_play: false`.

Jeżeli mecz już się rozpoczął, nie powstaje spóźniona prognoza Modelu X.
Brak xG powoduje brak pary — nie dopisujemy wartości zerowej.
Kanoniczny terminarz na dziś i jutro **nadal wyłącznie API-Football**.

## Niezależne rozliczenie następnego dnia

Workflow `KB21 shadow prospective outcome audit` pobiera oryginalne
artefakty GitHub Actions z wcześniejszych udanych uruchomień `main`.
Nowy skrypt `tools/kb21_xg_pair_audit.py`:

1. Weryfikuje źródła z tej samej migawki, poprawny schemat i daty freeze.
2. Odrzuca modyfikację dawnego Modelu G, niezgodność ID i próbę
   dołączenia kursu lub końcowego wyniku do prognozy.
3. Pierwszy prawidłowy wcześniejszy snapshot tego samego `fixture_id`
   liczy **raz**; nie mnoży 1X2 i over 2,5 w niezależne spotkania.
4. Korzysta z tych samych rzeczywistych rezultatów FT API-Football.
   Przełożone i nierozstrzygnięte mecze nie wchodzą do liczby sukcesów
   ani błędów.
5. Liczy Brier 1/X/2 oraz Brier over 2,5 dla **obu modeli na tej
   samej próbie**. Różnica = `Brier_X - Brier_G`: ujemna sugeruje
   poprawę, ale nie dowodzi jej na małej próbce.

Wyniki:
`KB21_XG_V_GOALS_AUDIT_YYYY-MM-DD.{json,md}`
w artefakcie `kb21-shadow-outcome-audit`.

**Początek historii eksperymentu dopiero od pierwszego rzeczywistego
przedmeczowego zamrożenia na `main`.** Nie tworzymy prognoz wstecz
dla 17 października ani wcześniejszych dni. Pierwszy wynik z małej próby
nie potwierdza stabilnej przewagi i nie uprawnia do deklarowania
trafności, value, ROI lub typów bukmacherskich.

Oryginalne STR/35, QUAL/35, MATCH/30, historyczne P(model), rejestr KB,
licznik N, API Market i PitchAPI **bez modyfikacji**.

Testy: `python -m unittest tests.test_kb21_xg_pair_shadow tests.test_kb21_xg_pair_audit -v`.


## Czytelne pliki PDF (automatycznie)

Dzienny workflow KB21 tworzy w istniejącym artefakcie
`kb21-api-football-two-days` dwa dodatkowe dokumenty:

- `KB21_XG_V_GOALS_SHADOW_YYYY-MM-DD.pdf` (dziś),
- `KB21_XG_V_GOALS_SHADOW_YYYY-MM-DD.pdf` (jutro).

Raport pokazuje dla każdego potwierdzonego przedmeczowego sparowania
oba zestawy 1 / X / 2 oraz over 2,5. Wszystkie prognozy są
eksperymentalne; żadna nie jest ofertą ani zaleceniem zakładu.
Pliki mają układ A4 poziomy, niedużą czytelną czcionkę i automatyczny
podział dłuższych zestawień na kolejne strony.

Oddzielny audyt dnia wczorajszego zapisuje PDF
`KB21_XG_V_GOALS_AUDIT_YYYY-MM-DD.pdf` obok JSON i Markdown w
artefakcie `kb21-shadow-outcome-audit`. W dokumencie znajdują się
wyłącznie zweryfikowane wyniki FT lub ich jawny brak, porównanie
błędu Brier i łączna liczba rozliczonych unikalnych spotkań.

Generator jest wyłącznie prezentacyjny: `tools/kb21_pdf_reports.py`.
Nie używa API, nie nadpisuje wcześniejszych prognoz, nie dopisuje
kursów, oryginalnego P(model), scoringu ani liczników N.
