# KB Score 2.1 — confirmed original source audit (2026-10-13)

Source of truth: Google Sheet "KB Score – Rejestr i Backtest", tabs Parametry, Rejestr, Kalibracja. Read-only audit; no changes to source workbook.

## Confirmed LIVE settings
- Sport Score = structural 35 + current quality 35 + matchup/context 30.
- Price, EV, consensus, confidence, and market signal do NOT enter Sport Score.
- No hard Sport Score threshold for PLAY/LEARN/CONTROL.
- Typical minimum EV: confidence 8–10: 2%; confidence 6–7: 3.5%; confidence 5: 5%; confidence <5: no PLAY.
- Missing data: reweight within the relevant block and potentially reduce confidence, do not automatically deduct Sport Score.
- P(model) is computed before bookmaker pricing; P(HIT) is distinct.
- Snapshot LIVE KB Score 2.1 dated 2026-08-22; later checkpoints and calendar controls remain in effect.

## Important limitations
The sheet specifies component weights and decision principles but not a complete deterministic formula mapping raw statistics to every LIVE component and P(model). Historical rows include human-assessed inputs. Therefore do not present a newly coded Poisson formula as the recovered original model.
Historical CORE v1R equations in Parametry are explicitly a separate backtest, NOT the LIVE 2.1 engine.
The Google Sheet remains the source of truth for existing observations and N; do not overwrite or backfill it.

## Recovery plan
1. Keep original workbook read-only until exact original LIVE computation is independently reconstructed and validated against frozen historical rows.
2. Isolate new API model on experimental/api-statistical-engine branch with separate inputs, outputs, evaluation and N.
3. Do not route provisional API data into KB21 PLAY or modify historical N.
4. Restore legacy PDF only when its original calculation and decision checks are validated, otherwise issue a clearly labeled diagnostic.
