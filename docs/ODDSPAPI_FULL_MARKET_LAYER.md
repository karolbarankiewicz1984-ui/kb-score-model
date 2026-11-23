# OddsPapi v4: universal market layer (research, not production)
Date: 2026-11-15. Target: isolated GitHub Models V2 branch `codex/multimodel-v2`.

## Status
- Implemented a **read-only standalone adapter** at `github_models/oddspapi_market.py`.
- Captures all active bookmaker market IDs/outcome IDs, not hardcoded fouls/corners/cards.
- Retains period, handicap, player ID, bookmaker, price, timing and source IDs.
- Only computes no-vig probabilities for complete outcome sets at the same bookmaker and player/market identity; 2+ books needed for a median consensus.
- Preserves all valid prices (including <1.20 for diagnosis), but only price >=1.20 qualifies for the practical output.
- Fails closed when kickoff already occurred or the fixture status is not pre-game.
- Historical endpoint replay requires a **verified scheduled kickoff** and discards timestamps at or after kickoff. These reconstructed prices are **not** magically prospective forecasts.
- Active subscription quota read via unmetered `/v4/account`; reserve of 10 billable calls enforced.
- No core model weights, forecasts, calibration, workflow schedules, API-Football dependencies, or public reports were changed.

## Setup — never commit or paste the API key
1. In GitHub: Settings > Secrets and variables > Actions > New repository secret.
2. Name it `ODDSPAPI_API_KEY`, paste the key as the **secret value**, save.
3. This branch has no unattended GitHub Actions schedule. Do not put a key in `.env`, workflow YAML, code, issue, commit, logs, or archived JSON.
4. The adapter needs the environment variable `ODDSPAPI_API_KEY`, supplied securely by the workflow or local environment.

## Standalone commands (after installing key securely)
```bash
python -m github_models.oddspapi_market quota
python -m github_models.oddspapi_market catalog --out research_inputs/oddspapi/markets.json
python -m github_models.oddspapi_market snapshot --fixture-id VERIFIED_ODDSPAPI_FIXTURE_ID --catalog research_inputs/oddspapi/markets.json --out research_inputs/oddspapi/fixture_snapshot.json
python -m github_models.oddspapi_market history --fixture-id VERIFIED_ODDSPAPI_FIXTURE_ID --bookmakers pinnacle,bet365 --kickoff-utc 2026-11-20T19:00:00Z --out research_inputs/oddspapi/history.json
python -m unittest tests.test_github_models_oddspapi_market
```
The example `--kickoff-utc` is a placeholder, **not** a real fixture's kickoff.

## Provider facts / quota design
- `GET /v4/odds`: one fixture, all accessible bookmakers when the filter is omitted; 1 billed request.
- `GET /v4/markets`: catalog; billed, cache it. `GET /v4/account`: unmetered.
- `GET /v4/odds-by-tournaments`: one bookmaker, up to three competitions per call; billed.
- `GET /v4/historical-odds`: not counted toward quota, max three bookmakers per call, but blocked once plan allowance has been exhausted.
- Free-tier/paid-tier exact coverage is account-specific. Do not assert that a market/bookmaker is included without testing the user's subscribed account.
- Provider documentation: https://oddspapi.io/us/docs and https://oddspapi.io/us/docs/requests-and-quota

## Next implementation stages
1. With the user's secret configured, safely read `/account` (do not archive its raw response, which contains `api_key`); record only quota counts and bookmaker slugs.
2. Build verified fixture mapping to PitchAPI: supplier IDs where independently shared, else strict team+competition+kickoff matching with review of ambiguous pairs. No guessed fuzzy mapping.
3. Capture all market rows for a small verified sample and determine which exact lines are covered by the subscription, including Polish books where available.
4. Automate quota-aware collection: cached static catalogs, batched odds by tournaments for chosen books, priority per-fixture calls near kickoff, snapshot once per frozen as-of date. Set a daily/monthly cap.
5. Exact-market joins only: market, side, line, period, settlement, team/player. Do not compare totals with team totals or card points with yellow cards.
6. Present no-vig reference, best quoted odds >=1.20, source/timestamp, market dispersion, price movement, and missingness in an **independent** PDF section. Keep model probability unchanged.
7. Backtest/freeze matching: original pre-match model snapshot + contemporary price <= kickoff + actual outcome under matching settlement rules. Separate Brier/calibration/hit rate from ROI; abstain when unavailable.
8. Validate on forward data and require human review before turning any market overlay into model score changes.

## Acceptance gates
- Real OddsPapi account and actual market coverage checked.
- Normalized snapshot verified against live provider response, without leaking key.
- No false complete-book probabilities, no post-start leakage, no invented quotes.
- All existing GitHub Models V2 tests remain green.
- Research forecast output, no-vig overlay, and past-result audits are separately traceable.

**Do not mark integration production-ready until live checks and regression tests have passed.**
