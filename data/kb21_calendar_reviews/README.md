# KB Score 2.1 — podpisane terminarze (tylko Calendar Gate)

Ten katalog jest opcjonalnym wejściem **rzeczywiście sprawdzonych** pełnych
kalendarzy organizatorów, a nie miejscem na kopie ESPN czy automatyczne
wypełnienie dat bez dowodów.

## Jak działa walidacja

1. Wykonaj bieżący workflow `.github/workflows/kb21-legacy-recovery.yml`.
   Z artefaktu pobierz `reports/kb21_legacy/official-inventory-research-draft.json`
   (jeśli dla dat dostępne są materiały) lub
   `official-inventory-template.json`.
2. Sprawdź osobno wszystkie 14 kategorii rozgrywek każdego dnia
   w oficjalnych kalendarzach organizatorów. Potwierdź także dni bez gier,
   przełożone/zaległe mecze, sezon, godziny i niezależne ESPN.
3. Wpisz do każdego rekordu `captured_at` ze strefą czasową, `reviewer`,
   `full_day_checked: true`, pełny wykaz `fixtures` i
   `confirmed_zero_matches` (true tylko przy **rzeczywistym**
   potwierdzeniu braku meczów).
4. W `daily_approvals` wpisz osobny podpis przed rozpoczęciem pierwszego
   wydarzenia danego dnia, np.:

   ```json
   "daily_approvals": {
     "2026-10-18": {
       "reviewer": "niezależny analityk",
       "approved_at": "2026-10-18T10:00:00+02:00",
       "attests_independent_official_review": true
     }
   }
   ```

   To jest przykład formatu, **nie faktyczne zatwierdzenie**. Nie wolno
   podpisywać wstecz. Pole `approval` może obsługiwać starszy jednorazowy
   podpis całego zakresu, ale zalecane są podpisy `daily_approvals`.
5. Jeśli oficjalna godzina różni się od ESPN, wpisz odrębną
   `time_discrepancies` z `fixture_id`, `third_source_fixture_id`,
   `reason` (co najmniej 15 znaków) oraz `reviewer`. Walidator weryfikuje
   te pola z zapisanym **przed meczem** snapshotem API-Football. Same
   automatyczne `suggested_time_discrepancies` z raportu nie są decyzją.
6. Zapisz sprawdzoną inwentaryzację jako:
   `data/kb21_calendar_reviews/YYYY-MM-DD_to_YYYY-MM-DD.json`,
   dokładnie dla trzech dni pokazywanych w raporcie i uruchom workflow ponownie.
   Przykład: `2026-10-17_to_2026-10-19.json`.

Workflow wyłącznie **czyta** plik z repozytorium. Dla każdej daty osobno
wypisuje `PASS_MANUAL` lub `BLOCKED`, zaś brak pliku oznacza bezpieczny
stan `BLOCKED`.

### Ograniczenia

- Zapisane pole `reviewer` to atestacja osoby kontrolującej, nie
  kryptograficzne uwierzytelnienie zawartości strony WWW.
- Nie wpisuj zatwierdzenia, jeżeli weryfikujesz terminarz dopiero po
  rozpoczęciu pierwszego wydarzenia tego dnia.
- Dokument z 17–19 października ma **materiały badawcze, bez podpisu**,
  nie nadaje się do automatycznego zastąpienia tymi danymi nowych dat.
- `PASS_MANUAL` dotyczy wyłącznie Calendar Gate: brak zgody na PLAY bez
  pozostałych warstw KB Score 2.1 i oryginalnego pre-price P(model).
- Stare N w Google Sheet pozostaje nietknięte.
