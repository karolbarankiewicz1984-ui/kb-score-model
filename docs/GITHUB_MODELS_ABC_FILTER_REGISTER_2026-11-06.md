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
