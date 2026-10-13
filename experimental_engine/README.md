# Independent API Statistical Engine — isolated experiment

This branch is for a NEW model, not KB Score 2.1 and not API Market.

## Isolation contract
- Never modify KB Score 2.1 methodology, Google Sheet register, N150/N200 checkpoints, historical N, PLAY/LEARN/CONTROL records, or historical freeze.
- Never write to existing `data/api_football/kb21_inputs`, `reports/kb21_*`, or `model/` paths.
- Use distinct `data/experimental_engine/`, `reports/experimental_engine/` and `tools/experimental_engine_*.py` paths.
- Predictions must be dated before kickoff; no retroactive predictions.
- Treat goal-based proxies as proxies, NOT measured xG.
- Do not claim backtest accuracy until real frozen out-of-sample predictions are settled.
- This branch is not deployed or scheduled by default.

## Recovery of legacy KB Score
The historical KB Score source of truth is the Google Sheet "KB Score – Rejestr i Backtest" plus the documented snapshots in AKTUALNY_MODEL.md, HISTORIA_ZMIAN.md, CHECKPOINTY.md and model/.
GitHub contains a methodology snapshot, not proof of an executable original scoring engine. Restore only from verified historical formulas and register parameters; never substitute the provisional Poisson engine for original P(model).

## Next implementation
Implement independently tested source adapters, immutable prematch snapshots, explicit missing-data checks, model versioning, and a separately named experimental PDF. Keep this branch isolated until separately approved.
