# OddsPapi — first real-account acceptance and coverage audit (2026-11-15)

Target: research PR #59 to `codex/multimodel-v2`. Key stored only in GitHub Actions secret `ODDSPAPI_API_KEY`. No credentials stored in Git.

## Runs
- [One-shot live authentication + catalog + one odds snapshot](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43765387559), second attempt: **success**. First attempt was not authorized because repository secret was not available.
- [Three-match all-market live probe](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43766198080): **success**.
- [Offline module regression](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/43764467392): **success**.

## Verified account / scope
- Account authentication works; monthly request limit 250. At the beginning of the second probe the usage count was 3; second probe was budgeted at at most 5 more billable calls and ran successfully.
- Soccer permitted. The subscribed bookmakers catalog includes `superbet.pl`, `efortuna.pl`, `bet365` and `pinnacle`; live coverage is fixture-specific and varies.
- Global market catalogue returned 70,742 definitions; soccer catalogue 1,122 definitions.
- 1,018 soccer fixtures with some odds were found in the next seven days. **This does not imply all 1,122 markets are offered for each fixture.**
- The first general-purpose sample returned 388 active odds selections from 29 bookmakers across 6 market IDs.

## Targeted live samples
Three matches and actual bookmaker selections from `/v4/odds`, not historical simulation:

| Fixture | Kickoff UTC | Selections | Market IDs | Books | O/U FT goals selections | O/U FT corners selections | O/U FT bookings selections |
|---|---|---:|---:|---:|---:|---:|---:|
| Albacete Balompie - RC Celta Fortuna (LaLiga 2) | 2026-11-16 19:30 | 89,571 | 541 | 252 | 3,686 | 1,906 | 454 |
| SV Darmstadt 98 - 1. FC Heidenheim (2. Bundesliga) | 2026-11-20 17:30 | 54,730 | 344 | 253 | 3,125 | 928 | 0 |
| EA Guingamp - Rodez Aveyron Football (Ligue 2) | 2026-11-20 19:00 | 44,117 | 317 | 234 | 2,697 | 701 | 0 |

Counts refer to distinct active outcome/line/bookmaker selections, not matches.

Albacete - Celta Fortuna also contained 760 player-fouls Over/Under quotes in `Over Under Player Fouls Committed (incl. overtime)`. **No total team-vs-team match fouls Over/Under offer was verified in these three fixtures**: player fouls != total match fouls. The market catalogue's foul-related entries alone do not prove that exact-market line +19.5 is offered.

`superbet.pl` had live cards, corners, shots, and goals-related markets in the Albacete sample; `efortuna.pl` also had active selections. Do not infer that a given market is available at each Polish bookmaker for all leagues or matches.

## Instrumentation caveat
The category-name counter in `oddspapi_coverage_probe.py` is an *overlapping keyword diagnostic*, not a mutually-exclusive or normalized market classifier. For example, `Over Under Full Time` may match within `Corners - Over Under Full Time` and `Bookings - Over Under Full Time`. The exact-market figures in the table above are extracted from **exact reported market names**, not the overlapping category totals. This needs a deterministic and mutually exclusive mapping before any PDF/model use.

## Decision and actions
1. **Authentication: PASS.** Key is working inside Actions.
2. **Read-only provider ingestion: PASS (research).** Real provider responses parsed and clean pre-kickoff snapshots obtained.
3. **All-market coverage: PARTIAL.** Broad coverage is proven, but markets and exact line settlement vary by fixture/bookmaker.
4. **PitchAPI fixture mapping: OPEN.** Never join via names alone without verified competition, kickoff and team identifiers. No live forecast enrichment until this check passes.
5. **Match-total fouls Over 19.5: NOT CONFIRMED.** Player foul markets are supported in samples but cannot stand in for total foul lines.
6. **Production: BLOCKED.** New isolated code still in draft PR #59. No changes to production scores, daily PDFs or scheduled analyses.

### Cost-aware deployment plan (proposal, NOT active)
- Monthly limit 250 requests; 10 reserve. One catalog request on refresh, one fixtures request/day, up to five or six carefully prioritized full-market fixture snapshots/day (one call captures many books and lines), with a daily/monthly stop guard and cache.
- Use free historical endpoint for independent pre-kickoff odds and calibration work, provided exact event mapping and account rules permit.
- Score all *supported* exact markets, but do not pretend every quoted prop is predictable. Separate the original frozen model forecast from market implied probability, no-vig median, market disagreements and verified price >=1.20.
- Add per-source provenance, time and missingness to PDF. Measure future calibration before adjusting weights.
