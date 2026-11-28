# Forecast/audit separation — design only

Current ABC workflow publishes early forecast artifact, archives immutable forecasts, then runs historical ABC/SHADOW audit and uploads complete artifact. OddsPapi workflow_run requires overall success. Panel selector requires successful ABC run and exact complete artifact, and independent OddsPapi rolling audit. Do not weaken these checks or simply accept cancelled runs.

## Migration
1. Extract forecast job boundary after immutable archive push. Preserve collection, cutoff, source health, optional SHADOW semantics and archive identity. Emit a forecast-only artifact with explicit schema and required files; verify exact queue and archive commit before success.
2. Separate historical audit workflow using pinned archive commit and verified results/events from the same source run; no additional provider calls. Preserve original audit cutoff semantics, archive scope, outputs and independent audit provenance.
3. Change OddsPapi trigger only after new forecast workflow is validated; retain successful main run, same Warsaw day, exact queue, six-hour freshness, future fixture and quota checks. Never enable both paid triggers simultaneously.
4. Version panel source contract: forecast artifact plus independent ABC/SHADOW audit artifact and existing odds audit. Preserve exact queue bytes, run attempt identity, audit freshness, rollback and private publication. Keep old reader until new reader passes replay.
5. Offline replay existing successful artifacts; compare forecast bytes, settlement reports and source identity; test missing archive, failed audit, stale odds, duplicate trigger, retries, midnight and optional SHADOW. No paid provider calls during tests.
6. Cutover only after tests, with rollback to original workflows and no duplicate paid cycle. Existing main workflow has push-path trigger: do not merge workflow edits casually.

No executable production changes in this design PR. Audit failure may allow forecast and odds generation but cannot bypass panel completeness gate.
