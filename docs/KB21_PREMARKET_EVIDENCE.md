# KB21 — przedrynkowe, faktyczne dowody sportowe z 12 ostatnich spotkań

## Cel

Od 18.10.2026 rozszerzamy dotychczasowe dwudniowe `KB21_FORM_*.json/.md/.pdf`
oraz kolejkę `KB21_ANALYST_WORKLIST_*.json` o dane pozwalające analitykowi
ocenić rzeczywistą formę, zamiast widzieć tylko średnią goli z 10 meczów.
Wszystkie dane pochodzą z **TEJ SAMEJ** już pobranej odpowiedzi
`API-Football /fixtures?team=...&last=12`. Brak dodatkowych zapytań.
Terminarz nadal pochodzi wyłącznie z API-Football na dziś i jutro.

## Nowe obiektywne informacje

- 5 ostatnich **FT** (pełen czas regulaminowy): W-D-L, faktyczne gole
  zdobyte i stracone na mecz oraz punkty/mecz.
- Do 10 ostatnich **FT**: oddzielne bilanse u siebie i na wyjeździe.
  Jeśli jest mniej niż 3 mecze domowe albo wyjazdowe, raport wprost
  oznacza próbę jako za małą do użytecznego wniosku o danym boisku.
- Liczba dni od **rozpoczęcia** poprzedniego meczu, nie liczba
  rzeczywistych godzin odpoczynku; nie utożsamiamy tych miar.
- Każda rzeczywista próba ma oryginalne `fixture_id`, datę UTC,
  lokalizację gospodarze/goście, wynik FT i stan. Brak wyniku FT
  nie jest zerem ani przegraną.
- `AET/PEN` nie są automatycznie zaliczane do 90-minutowej
  historii FT. Takie spotkania są jawnie liczone jako pominięte
  w nowej części faktograficznej (dotychczasowy model testowy
  10 goli pozostaje niezmieniony).

## Bezpieczeństwo

- Każde zdarzenie pobrane przed meczem; żadna obserwacja FT
  o dacie równej lub późniejszej niż faktyczny snapshot nie jest
  dopuszczana. Duplikaty historycznych ID i godziny bez strefy
  czasu są błędem, nie fałszywym wynikiem.
- Pola `STR/35`, `QUAL/35`, `MATCH/30`,
  `original_p_model`, `analyst_assessment.P_model_pre_odds`,
  kursy i PLAY **pozostają puste**. Dane o golach nie pozwalają
  odtworzyć siły ELO, jakości rywali, prawdziwego xG, absencji,
  ustawień, ryzyka składu czy brakującej historycznej formuły.
- Raport `sport_evidence` ma `safe_to_publish_play=false`.
  Nie zmienia historycznego N, rejestru ani metody oryginalnego
  KB Score i nie integruje kursów.
- `side_note` umieszcza wyłącznie opis faktów w kompaktowym PDF;
  bez wskazywania rynku lub sztucznego confidence.

## Dlaczego to etap konieczny

Oryginalny Sport Score: 35% strukturalna siła, 35% jakość gry,
30% dopasowanie i kontekst. **Te wagi nie oznaczają**, że
obiektywną średnią bramek można po prostu przeliczyć na oceny
35/35/30. Nowy moduł buduje audytowalną bazę dowodów o
wynikach, formie i miejscu meczu, którą można potem połączyć
z niezależnymi ELO, xG, absencjami i ręcznym oszacowaniem
P(model) przed kursem.

Uruchomienie:
`python -m unittest tests.test_kb21_form_evidence -v`
i pełne `python -m unittest discover -s tests -p 'test_kb21*.py'`.
