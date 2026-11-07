# API-Football retirement — verified impact and repair status (2026-11-07)

## Evidence
- API Market Scan failed in run 42388233957: provider returned daily request limit. API Market multi-day failed in run 42386924837 for the same reason.
- MULTIMODEL V2 workflow `.github/workflows/github-models-v2-daily-audit.yml` previously called `github_models.fast_final_collect` with `API_FOOTBALL_KEY` for post-match settlement. Its prediction collection uses PitchAPI and independent public datasets.
- KB Score 3.0 PitchAPI daily collection, M0 settlement, and M0-720 research had successful runs on 2026-11-07. Historical backfill run 42417587253 failed separately; this is not proof of API-Football dependence.
- KB Score 2.1 legacy single-source calendar uses API-Football; its former workflow was retired. The remaining calendar-health workflow still expects its retired artifact.

## Implemented in main
1. Commit 5a9a3c80f22c189e7b67a5421c12d671ebe257c8: MULTIMODEL V2 daily audit now copies independently collected verified public results/events into settlement inputs instead of calling API-Football. Manifest explicitly identifies this source and does not imply completeness of absent markets.
2. Commit eb5ed3057d1f56b291daaefc9343f8b357597296: MULTIMODEL V2 repair verification uses previous independently verified public source snapshots, not API-Football.

## Remaining limitations / decision gates
- These commits have not yet passed a fresh end-to-end Actions run. Do not label them production-verified until a run succeeds and artifact contents are inspected.
- Public event sources may lack fouls/cards/corners for some leagues. Missing statistics must remain missing; no synthetic settlement.
- API Market Scan and its multi-day experiment remain API-Football-dependent, including fixture discovery, odds and enrichment. They require a licensed equivalent source and mapping of exact markets before a safe migration. No fake provider substitution or methodology changes were made.
- MULTIMODEL archive consumes API Market multi-day artifacts and can only archive successfully generated artifacts.
- KB21 calendar-health still depends on retired KB21 single-source artifact; repair or retire after confirming downstream usage.
- KB Score 3.0 main pipeline was not changed.
