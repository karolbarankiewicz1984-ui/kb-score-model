# KB Score 2.1 — analyst-led daily report template (legacy recovery)

Status: REVIEW / MANUAL. This is a reporting template, NOT a replacement deterministic model. It requires verified pre-match evidence and analyst judgement. No API or xG subscription is mandatory.

## 0. Run metadata
- Date/time of pre-match freeze (Europe/Warsaw):
- Analyst:
- Official fixture calendar source (URL, retrieval time):
- Independent calendar cross-check (URL, retrieval time):
- Included competitions / excluded competitions and reason:
- Calendar Gate: PASS / BLOCKED. If blocked: no PLAY, no register writes.

## 1. Broad match scan
For each verified fixture record: competition, kickoff (Europe/Warsaw), home, away, official source, independent source, candidate markets, evidence completeness. Do not silently omit relevant leagues.

## 2. Sport assessment — BEFORE seeing prices
For each candidate:
- Match / market / freeze time:
- Structural strength STR: __ /35. Evidence: team power, squad strength, longer-term level, quality of opposition; URLs + dates.
- Current quality QUAL: __ /35. Evidence: form adjusted for opponents, shots/chances, defensive/offensive performance, home/away. Genuine xG if available: value + provider + date. If not: 'xG unavailable'; use other credible evidence, do not substitute goals and label them xG.
- Matchup/context MATCH: __ /30. Evidence: styles, home advantage, rest, travel, key confirmed absences, rotation/lineup uncertainty, motivation only when supported.
- SPORT SCORE = STR + QUAL + MATCH: __ /100.
- Pre-price P(model) for specified market: __%. Justification and probability-estimation method; uncertainty interval. If not defensible, mark 'UNDETERMINED' and do not classify PLAY.
- Scoreline projection (if defensible): __; projected goals / xG only if supported and clearly labeled as estimates.
- Confidence: __/10, reflecting evidence quality and model stability; never mechanically added to Sport Score.
- Evidence gaps and potential counterarguments:

## 3. Independent checks
- Consensus: SUPPORT / NEUTRAL / CONTRA; independent source URLs and capture time. Do not copy consensus into P(model).
- Lineup / data quality: verified, uncertain, or missing. Any post-freeze changes require a new timestamped assessment.

## 4. Market assessment — AFTER P(model) freeze
- Bookmaker / market / price / timestamp:
- Implied probability = 1/odds:
- No-vig benchmark: list ALL mutually exclusive outcomes and prices; otherwise mark unavailable (do not fabricate).
- Fair odds = 1/P(model):
- Edge (probability points) = P(model) - no-vig benchmark (if available):
- EV = P(model) * decimal odds - 1:
- Correlation with other selections:
- Decision: PLAY / LEARN / CONTROL / NO BET; written reasoning. No hard Sport Score cutoff.
- Typical minimum EV guidelines from LIVE parameters: Confidence 8–10 => 2%; 6–7 => 3.5%; 5 => 5%; below 5 => no PLAY. These are guidance, not sufficient conditions for PLAY.

## 5. Publication and audit
- Publish dated PDF only after Calendar Gate passes, evidence and pre-match freeze are archived, and conclusions are checked. Otherwise issue clearly marked DIAGNOSTIC / NO PLAY, never an ordinary LIVE report.
- Keep original Google Sheet read-only during recovery. Do not backfill missing historical observations or N. Do not count candidate reports as new N.
- KB Score 2.1 remains independent from API Market Scan and provisional Poisson experiments.

## 6. Validation milestone
Compare at least 10 new, timestamped analyst-led assessments against the original archived rubric for internal consistency, and check event identities against official schedules before restoring LIVE publication and registry writes. This is process validation, not a promise of predictive accuracy.
