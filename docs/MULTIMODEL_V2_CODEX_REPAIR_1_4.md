# MULTIMODEL v2 — Codex repair batch P1-001/003/004/005

Status: READY_FOR_CODEX; NOT IMPLEMENTED. Date: 2026-11-02. Branch: `codex/multimodel-v2`. PR #55 draft. No merge.

Read first: `docs/MULTIMODEL_V2_E2E_AUDIT_2026-11-02.md` and `docs/MULTIMODEL_V2_E2E_EVIDENCE_2026-11-02.json`. Preserve source algorithms, official TOP, thresholds, historical freeze, archives and N. Never backfill pre-match data from post-kickoff captures. No paid API calls. Work in four independent workstreams, with shared tests and a consolidated register.

## 1. Three-day coverage and deadline
Inspect actual schedule, DST guard and source code checkout (not only main workflow definition). Fix isolated v2 planner/validation to demand D,D+1,D+2; use timezone Europe/Warsaw and pre-kickoff cutoff. Add fixture tests for DST boundaries, late starts, skipped DST slots, per-date status, missing artifacts, wrong date, partial exports, 11:30 deadline. Propose minimal production workflow diff as a separate patch, do not apply to main. A successful job with skipped scan must not count as source-ready. Avoid silently switching default `days` on production.

## 2. KB Score 2.1 and Konsensus current freeze
Inspect existing Google Sheets adapter, native archives, and available publication mechanisms. Implement read-only verification of event date, fixture identity, exact market, bookmaker/quote, publication time and cutoff; differentiate historical selection rows from current formal frozen picks. If current formal picks do not exist, return `SOURCE_BLOCKED` with precise missing fields and propose a non-destructive forward-only publication schema/workflow, isolated from main. Never manufacture new picks or repurpose analysis time as kickoff/freeze.

## 3. Full API candidate pool
Inspect experimental scan pipeline and native published/filtered outputs. Add optional immutable, date-partitioned full candidate export including below-67 records and rejected reasons; preserve exact quote identity, source timestamps, fixture ID, market, scope/team, direction, line, 90-minute settlement, and native publication ID. Include digest, schema/version, source run/commit, per-date counts and proof that no fields are synthesized. Apply retention and size limits, and redact API keys. Implement only in isolated branch and test against frozen fixtures; no paid scan and no rewriting prior archives. Do not claim old 1473/999 candidate rows were recovered if only counts exist.

## 4. Native settlement linkage
Add a forward-only join on original prediction/publication ID plus fixture, exact market and pre-match quote identity. Separate TOP, API full pool and FAULE UNDER cohorts. Settlement states WIN/LOSS/VOID/UNRESOLVED; ROI/fixture-equal ROI only for complete eligible frozen cohorts, otherwise null/AUDYT NIEPEŁNY. Explicitly reject 1391 existing observations from unrelated publication ID. Unit tests for wrong ID, duplicate, partial fixtures, missing odds, void, correlated markets, post-kickoff quote and replay.

## Exit criteria
- Provide actual modified files, commits, green regression CI, test counts, before/after comparison and per-workstream status DONE/BLOCKED.
- Distinguish code-ready from real-data-ready. Full shadow PASS requires current native sources and same-fixture freeze evidence.
- Update E2E audit and register; list any action requiring user credentials, Google permissions or GitHub Actions settings.
- Never merge PR #55 or modify production models, original historical data, archive, N, source thresholds, existing TOP or paid workflows.
