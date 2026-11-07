# API-Football retirement — 2026-11-07

Decision: user no longer uses API-Football. Retire its dedicated GitHub Actions workflows, preserving model code and historical datasets.

Removed workflow definitions (not model code or datasets):
- api-football-backfill-5m.yml
- api-football-conference-patch-5m.yml
- api-football-daily-collector.yml
- api-football-history-lab.yml
- api-football-international-backfill-5m.yml
- api-football-odds-reference.yml
- api-football-smoke.yml
- kb21-api-prematch.yml
- kb21-shadow-audit.yml
- kb21-single-source-two-days.yml

Outstanding dependencies intentionally NOT altered to preserve other models:
- api-market-scan.yml and api-market-multiday-experiment.yml still require API_FOOTBALL_KEY; these may continue to fail. Migration or separate retirement decision required.
- kb21-calendar-health.yml depends on the retired KB21 single-source workflow; may need retirement or replacement after downstream review.
- Other KB21 historical snapshot readers may reference data/api_football paths; historical files were not deleted.

No claim is made that API-Football has been removed from all code paths. No PitchAPI, KB Score 3.0, or model data modifications were made.
