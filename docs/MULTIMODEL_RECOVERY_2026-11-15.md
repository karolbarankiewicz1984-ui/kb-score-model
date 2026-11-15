# MULTIMODEL GitHub V2 — recovery log — 2026-11-15

Scope: independent `codex/multimodel-v2` research workflows in the `kb-score-model` repository. Production betting models and their thresholds/weights are unchanged.

## Confirmed actions
1. Re-ran previously failed `PitchAPI prematch xG context - API and KB21 companion`, run [43711303145](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43711303145), attempt 2. **Succeeded** on 2026-11-15 at 13:31 UTC. Commit `58f0099594fd1f779f0493709fe62a868a3a5448` published dated snapshots for 2026-11-16 through 2026-11-18.
2. Re-ran previously failed `GitHub Models V2 — A/B/C | daily forecast and audit`, run [43603122881](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43603122881), attempt 2. Forecast, JSON, PDF, artifact publication and immutable research snapshot archiving **succeeded**. Forecast artifact ID: `14163359664`. Historical A/B/C audit still in progress when this record was written.
3. Found that isolated end-to-end smoke run [43605193312](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43605193312) reached PDF creation but its archival step was canceled at the 25-minute job timeout. Historical settlement itself consumed approximately 20 minutes (22 archive files, 12 event-market archive files).
4. Raised the timeout in `.github/workflows/github-models-smoke.yml` from 25 to 45 minutes, in commit `32995452178c47c6a052d184278a23c035287e43`, without changing prediction logic. The automatically triggered verification run is [43719709783](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43719709783), still in progress at record creation.

## Research forecast availability
A fresh immutable forecast was archived at `research/github-models-frozen:frozen/2026-11-15/43603122881.json` with 8 raw 1X2 model records from Elo and Dixon-Coles for 4 fixtures, including Albacete–Celta Fortuna on Nov 16. The corresponding event-market archive contains 96 probability entries. All probabilities are explicitly `uncalibrated_research`; no claim is made about real-world predictive accuracy.

## Remaining blockers — do not silently claim fixed
- `xgboost: model_not_trained_or_adapter_not_ready`: not operational; do not manufacture model forecasts.
- Several unsupported/unmatched team identities outside the verified source mapping remain excluded (fail closed).
- Bookmaker odds and availability have **not** been captured or verified; do not apply the >=1.20 odds filter to imaginary prices and do not label unverified research candidates as playable bets.
- Full historical A/B/C audit and new smoke run must end successfully before declaring all scheduled paths restored.
- Optimize repeated historical settlement and consider a separate fast smoke path if 45-minute verification remains too slow; retain strict pre-match cutoff, unaltered scores, exact outcome matching and immutable forecasts.

## Evidence
- Data refresh: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43711303145
- Daily V2 forecast: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43603122881
- Forecast artifact: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43603122881/artifacts/14163359664
- Smoke fix: https://github.com/karolbarankiewicz1984-ui/kb-score-model/commit/32995452178c47c6a052d184278a23c035287e43
- New smoke: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43719709783
