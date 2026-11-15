# MultiModel V2 / OddsPapi — register of steps 1–8
Date: 2026-11-15. Owner-controlled scope: **Superbet.pl and STS.pl only**.
All changes are separate from KB Score 3.0, legacy API Market and the original
GitHub Models V2 forecasting probabilities.

| # | Workstream | Verified state | Evidence / next gate |
|---|---|---|---|
| 1 | Exact market taxonomy | **IMPLEMENTED, tested** | Mutually exclusive names/period/line/player. Bookings != automatically identical to yellow cards; player fouls != match-total fouls. See `oddspapi_integration.py`. |
| 2 | PitchAPI ↔ OddsPapi fixture matching | **LIVE VERIFIED** | 51 unambiguous matches among 296 PitchAPI queue fixtures and 684 Superbet-offered fixtures in a seven-day sample; country + league + home/away + kickoff + no conflicting matches. |
| 3 | Polish sportsbook coverage | **SUPERBET PASS; STS BLOCKED** | Actual `/v4/account` lists `superbet.pl`; no `sts` or `sts.pl`. No foreign or substitute bookmaker is used. |
| 4 | Quota-safe collector and archiving | **BATCH LIVE PASS; scheduled activation pending default-branch workflow deployment** | 33 matched football fixtures, 10,655 quotes with a single tournament batch; subsequent cached run cost 2 billed calls total. Up to 3 batches of three leagues in proposed daily run, 90-day immutable run artifact, hard stop at 200/250. |
| 5 | Market Intelligence | **IMPLEMENTED, tested** | Exact side/period/line join, complete same-book no-vig benchmark, model-vs-market difference flagged *uncalibrated*. No false 2+ bookmaker consensus under single Polish bookmaker scope. History and price movement measured from recorded as-of snapshots. |
| 6 | PDF with sportsbook quotes | **GENERATED AND VERIFIED** | First end-to-end PDF: 12 pages, 281 exact model/market comparisons in a 33-fixture snapshot. Price >=1.20 filter and original model probability preserved. As a separate supplement, not a replacement of original PDFs; no production PDF silently modified. |
| 7 | Historical audit / settlement | **IMPLEMENTED, waiting for completed sampled fixtures** | `oddspapi_replay_audit.py`, independent official/public result source `oddspapi_outcomes.py`, daily audit workflow and separate audit PDF. First prospective sample contains 0 settled games. All empirical metrics remain empty, not fabricated. |
| 8 | Three-model ablation study | **EXPERIMENT CODE READY; NOT ELIGIBLE FOR PRODUCTION PROMOTION** | A: original frozen model, B: market agreement filter (<=10pp), C: research-only 50/50 blend. Compare paired sample sets with Brier/log loss/hit rate and strictly timestamped odds; minimum 100 *distinct settled fixtures* as a review gate, not an automatic release decision. No model weights changed. |

## Observations from actual GitHub Actions
- Live auth: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43765387559 (second attempt).
- First three-league raw coverage: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43766198080
- Working bulk odds sampler: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43770620090
- First PDF and JSON archived as Actions artifact: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43771339800
- Research PR #59: https://github.com/karolbarankiewicz1984-ui/kb-score-model/pull/59

## Cost and guardrails
- Full free plan = 250 billable endpoint calls per calendar month. Endpoint `/account` unmetered and `/historical-odds` free but blocked if plan runs out.
- Workflow capacity: one fixtures call and up to three batch odds-by-tournaments calls/day; one soccer market catalogue call per monthly cache key. At 31 days, nominal <=125 calls, before unexpected retries/errors.
- **Hard stop**: caller checks actual account `request_count`; rejects if a request would cross 200/month, preserving at least 50. Rechecks before each bulk request.
- No spontaneous retries on 4xx/5xx; no APIs outside subscriber-authorized scope; key exists only in GitHub Actions secret.
- Quote records include source, exact line, match ID, timestamp, period, side, bookmaker, active status and archived odds. No quote timestamp at/after kickoff is eligible.
- Claims of positive expected value are forbidden until probability calibration and exact market settlement are demonstrated.
- Historical replay chooses the earliest verified price per unique fixture/line/side, not the most favourable hindsight quote.

## Remaining deployment/research gates
- Main-branch **schedules** must be deployed as isolated workflows, because `main` does not hold the full research-branch model code. Workflows must check out a tested, pinned research SHA and leave main's forecasting code untouched.
- Confirm 90-day artifact retention under the repository's actual Actions settings; if run data expires, longer-term cumulative calibration will need external persistence.
- STS.pl remains unavailable in this account, requiring data-source upgrade before its markets can be compared.
- Confirm market-specific settlement rules, especially yellow cards vs bookmaker bookings, before enabling that market's probability comparisons.
- After enough prospectively archived results, review A/B/C experiment per market and identical fixture cohort. Until then **production remains unchanged**.

## Operator-facing output
- `MULTIMODEL_V2_SUPERBET_MARKET.pdf`: top rows, chronological matched selections, P(model), exact quote, P(no-vig), market coverage, and audit availability.
- `MULTIMODEL_V2_SUPERBET_AUDIT.pdf`: retrospective metrics only when independently settled.
- `collection.json`, `fixture_links.json`, `market_overlay.json`, `pitch_queue.json`: reproducible source evidence and mapping.
