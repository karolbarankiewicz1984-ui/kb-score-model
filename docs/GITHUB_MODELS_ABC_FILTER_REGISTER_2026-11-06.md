# MULTIMODEL V2 — filtry A/B/C, 2026-11-06

Zakres: wyłącznie gałąź `codex/multimodel-v2`. MULTIMODEL i KB Score 3.0 bez zmian.

## Zmiany
- `github_models/abc_filter_policy.json`: eksperymentalne progi A 70%, B 75%, C 80%, zgodność Elo/Dixon-Coles maks. 10 p.p.
- `github_models/abc_filter.py`: równoległe filtrowanie 1X2 i par over/under z kontrolą matematyki. Nie przypisuje fikcyjnego V2 Score.
- `tests/test_github_models_abc_filter.py`: testy progów, błędnych sum i par rynków.
- `github_models/abc_report.py`: czytelny raport PDF i pełny JSON kandydatów.
- `.github/workflows/github-models-independent.yml`: osobny krok generowania A/B/C na zamrożonych danych z bieżącego przebiegu; JSON i PDF w artefakcie.

## Ograniczenia i bramki
- A/B/C to klasyfikacja badawcza, nie dowód kalibracji ani wartości zakładu.
- Brak kompletnych i zweryfikowanych składowych V2 Score: nie liczyć arbitralnych 0–100.
- Przed uznaniem za zamknięte: wymagane CI SUCCESS dla commitu zawierającego workflow, rzeczywiste liczniki kandydatów i sprawdzony PDF z tego samego artefaktu.
- Stare 1226/1226 testów dotyczą wcześniejszego przebiegu.
- Nie scalać do main ani nie dotykać innych modeli.

## 2026-11-07 — naprawa opóźnionych rozliczeń
**Diagnoza z rzeczywistego przebiegu 42355073948:** 0 rozliczonych A/B/C przy 5 archiwach. Baza wyników bramkowych miała najnowszy `match_date` 2026-11-05, baza dodatkowych statystyk 2026-11-04. Importer CSV celowo dopuszcza tylko wyniki po dacie meczu + 2 dni. Nie wynika z tego, że typy przegrały.

**Nowe rozwiązanie (badawcze):**
- `github_models/fast_final_parser.py`: ścisłe parsowanie wyników `FT` i statystyk API-Football. Bez potwierdzonego kraju, ligi, jednoznacznej nazwy drużyn i rzeczywistego statusu FT — nie rozliczać.
- `github_models/fast_final_collect.py`: maks. 2 dni historii; do 24 zapytań o statystyki na przebieg. Dwa ostatnie dni dotyczą wyłącznie ROZLICZANIA, nie treningu ani rewizji prognoz. Timestamp to rzeczywisty moment obserwacji zakończonego wyniku, a nie wymyślony czas gwizdka.
- Bezpieczna agregacja: identycznych wyników dostawców nie dublować; sprzeczne zachować do oznaczenia jako niejednoznaczne. Nie imputować brakujących kartek, fauli i rożnych.
- `tests/test_github_models_fast_results.py`: testy statusów, zgodności wyników, drużyn, braku klucza i duplikatów.
- `github_models/abc_settlement.py`: zachowuje dokładną linię rynku i przyczynę nierozliczenia.
- `github_models/abc_audit_runner.py`: deduplikacja tej samej prognozy meczu/rynku/strony/linii we wszystkich migawkach. Wcześniejsze 749/475/247 były liczebnościami ze zduplikowanych archiwów, a nie unikalną próbą do oceny trafialności.
- `github_models/abc_audit_pdf.py`: raportuje deduplikację i przyczyny odmowy rozliczenia.
- Główny harmonogram: `.github/workflows/github-models-v2-daily-audit.yml` na `main`, uruchamiany codziennie i przy zmianie workflow. Nowy etap pozyskiwania API-Football ma dostęp wyłącznie do danych końcowych, a w fazie forecast korzysta się nadal z poprzedniej bazy.

**Ograniczenia i bramki:**
- API-Football może nie pokrywać wszystkich lig oraz statystyk; brak wyniku jest `unresolved`, nigdy porażką.
- Potwierdzenie działania: testy PASS, cały przebieg SUCCESS, dodatnia liczba rzeczywiście zweryfikowanych wyników 2026-11-06 i niezależna kontrola liczb Brier/log loss. Brak sukcesu na którejkolwiek bramce pozostaje otwartą usterką.
- Progi A/B/C i model produkcyjny bez zmian. Nie podnosić oceny skuteczności bez nowej próby.
