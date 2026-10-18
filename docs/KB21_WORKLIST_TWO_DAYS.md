# KB Score 2.1 — codzienna pełna kolejka analityczna (API-Football)

## Co jest nowego

Workflow `KB21 SINGLE SOURCE API-Football today+tomorrow` generuje
`KB21_ANALYST_WORKLIST_YYYY-MM-DD.json` i `.md` dla **wszystkich**
przyszłych kandydatów NS znajdujących się w zakresie KB21 i w poprawnie
pobranym kalendarzu API-Football z danego dnia. Są dwa dni Europe/Warsaw:
**dziś i jutro**. Nie dodaje meczów z innych terminarzy.

Do tej pory szczegółowy raport `KB21_FORM_` obejmował najwyżej 5 spotkań
na dzień (od 18.10.2026 rozszerzony do maksymalnie 30 spotkań dziennie,
przy limicie 80 zapytań o historię drużyn na dwie daty i rezerwie
25 zapytań dziennych według nagłówków dostawcy), bo każde potrzebuje osobnych zapytań o rzeczywiste wcześniejsze
wyniki obu drużyn. Ten limit **nie jest** limitem kolejki meczów. Jeśli kończy się budżet
API, niewykonane odczyty są jawnie oznaczane jako brak historii,
a nie jako brak wcześniejszych spotkań.
Pełna lista w `WORKLIST` jest niezależna od liczby danych o formie.

## Dane i granice

- `KB21_ANALYST_WORKLIST_YYYY-MM-DD.md` — zwięzły wykaz z godziną
  w Polsce, meczem, ligą, informacją o faktycznej historii goli i stanem.
- `KB21_ANALYST_WORKLIST_YYYY-MM-DD.json` — wszystkie te mecze wraz
  z pustym formularzem oceny analitycznej kompatybilnym z
  `tools/kb21_analyst_assessment.py`, identyfikatorem API, startem
  w UTC, znacznikiem czasu źródła i dołączoną historią goli **wyłącznie
  dla faktycznie wzbogaconych kandydatów**.
- `KB21_ANALYST_WORKLIST_MANIFEST.json` — liczniki i zasady bezpieczeństwa.

Wszystkie `str / qual / match / p_model / freeze_at / market` formularza
pozostają `null` lub puste. Nic nie jest rekonstruowane, prognozowane
ani pośrednio „zatwierdzane” z Poissona. Nie są dopisywane wyniki do
głównego rejestru, historii N ani statystyk DEV. Nie pobiera się kursów
bukmacherskich.

Jeżeli mecz rozpoczął się, zanim powstała kolejka, otrzymuje
`KICKOFF_PASSED_NO_LATE_FREEZE`. Takie spotkanie nie może być
oceniane jako świeży, przedmeczowy freeze. Pozostałe rekordy mają
`AWAITING_HUMAN_PREMARKET_ASSESSMENT`; to oznacza brak oceny,
**nie** zgodę na PLAY.

## Co nadal jest potrzebne do oryginalnego KB Score

1. Uczciwie udokumentowane przedmeczowe dowody dla STR/35, QUAL/35 i
   MATCH/30 (np. siła, styl, forma, dom/wyjazd, absencje). Sama średnia
   rzeczywistych goli z historii nie jest xG ani kompletną oceną.
2. Niezależna, uzasadniona ocena `P(model)` **przed sprawdzeniem kursu**.
   Historyczny matematyczny sposób jej wyprowadzania NIE został odzyskany.
3. Rzeczywiście wykonany, oznaczony czasem freeze, a po nim kurs
   z identyfikatorem zdarzenia/rynku, kontrola jakości danych,
   lineup risk, Market Signal i osobna decyzja analityczna.
4. Prospektywna weryfikacja nowej procedury bez dopisywania wyników do
   starego historycznego N ani udawania identyczności modelu.

## Bezpieczeństwo i testy

Moduł `tools/kb21_single_source_worklist.py` wymaga dokładnie dwóch
poprawnych dni API-Football, zgodnych identyfikatorów, godzin i nazw
zespołów między źródłem a historią. Odrzuca obce mecze, duplikaty,
podmienione wyniki analityczne, kursy czy sztucznie wypełniony P(model).

Uruchomienie: `python -m unittest tests.test_kb21_single_source_worklist -v`.
Pliki trafiają do dotychczasowego artefaktu `kb21-api-football-two-days`
w tej samej akcji GitHub, bez dodatkowego API i bez zmian w workflow API
Market / PitchAPI.

**Stan: RESEARCH / REVIEW REQUIRED / NO PLAY.**
