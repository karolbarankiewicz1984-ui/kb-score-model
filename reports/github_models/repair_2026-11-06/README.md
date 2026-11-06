# Końcowy pakiet badawczy — 2026-11-06

- `RESEARCH_REPORT.pdf`: pięciostronicowe podsumowanie, interpretacja pięciu rynków, każda liga i wybrane obserwacje.
- `FORECASTS_FULL.pdf`: pełny aneks 133 stron; te same rzeczywiste prognozy co w końcowym artefakcie.
- `coverage_comparison_final.json`: ta sama kolejka 488 spotkań i cutoff we wszystkich wariantach; 65 osobnych ID lig.
- `verification.json`, `project_ledger.json`: matematyka, testy, odrzucenia, ograniczenia i ślad zmian.
- `source_artifact_42197854709.zip`: niezmieniony oryginalny artefakt Actions; wszystkie wejścia, manifesty, migawki i prognozy. SHA256: `80c0ce7c0be80e8ebed61bd24e9c61d6473be2430e8d9c9017119bfce0eda5cc`.
- `github_actions.log`, `github_actions.json`, logi testów: dowody wykonania i wersje zależności zapisane przez runner.
- `reference_226.zip`: wcześniejsza, osobna kohorta diagnostyczna; nie łączyć jej z finałem. Hash w `reference_226.sha256`.

Kod obliczeń: `703b533ed45ae005c2a0825cd6a50de640da797c`. Kod bazowy: `f609427e07ea9e9e944a61c3063ab18a11f3b897`. Pełny run: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42197854709.

Prognozy są niekalibrowane. Cutoff `2026-11-06T09:53:42.542940+00:00` opisuje dostępność wejść, a nie publikację artefaktu. Odtworzenie raportu nie tworzy nowego forward, wartości bukmacherskiej ani wpisów N.

## Odtworzenie porównania bez nowych zapytań API

Uruchom w czystej kopii repozytorium z zależnościami `github_models/requirements.txt`. Archiwum ZIP zachowano w Git, więc odtworzenie nie zależy od 30-dniowej retencji Actions.

```bash
git worktree add /tmp/kb-before f609427e07ea9e9e944a61c3063ab18a11f3b897
unzip reports/github_models/repair_2026-11-06/source_artifact_42197854709.zip -d /tmp/kb-replay
```

Z oryginalnej macierzy wydziel dawny zakres pięciu lig, zachowując czasy obserwacji:

```python
import json
from pathlib import Path
rows = json.loads(Path('/tmp/kb-replay/data/github_models/verified_results.json').read_text())
leagues = {'Premier League', 'Bundesliga', 'Serie A', 'La Liga', 'Ligue 1'}
Path('/tmp/kb-top5.json').write_text(json.dumps(
    [row for row in rows if row['league'] in leagues], ensure_ascii=False, indent=2) + '\n')
```

```bash
python -B -m github_models.coverage_comparison \
  --queue /tmp/kb-replay/reports/github_models/queues/2026-11-06.json \
  --history /tmp/kb-replay/data/github_models/verified_results.json \
  --events /tmp/kb-replay/data/github_models/verified_events.json \
  --before-history /tmp/kb-top5.json --baseline-root /tmp/kb-before \
  --as-of 2026-11-06T09:53:42.542940+00:00 --output /tmp/kb-comparison.json
```

`verify_artifacts.py`, `build_summary_pdf.py` i `build_project_report.py` udostępniają `--help`. Weryfikacja wymaga oryginalnego ZIP, manifestu `github_actions.json`, końcowego porównania oraz logu pełnej regresji. Generatory odrzucają pomieszane kohorty, różne cutoff, hashe lub nieprawidłowe prawdopodobieństwa. Nie pobieraj ponownie dzisiejszych CSV i nie nadpisuj nimi historycznych czasów pierwszego odczytu.
