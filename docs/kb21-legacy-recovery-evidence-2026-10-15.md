# KB Score 2.1 — legacy recovery evidence (2026-10-15)

## Verified read-only from Google Sheet
Spreadsheet: KB Score – Rejestr i Backtest. Tabs: Parametry, Rejestr, Kalibracja. No cells changed.

- Parametry A4:A14: LIVE Sport Score uses structural 35, current quality 35, matchup/context 30; market/EV/consensus/confidence are separate. Missing xG alone does not force zero score: reweight available reliable evidence within the block and adjust confidence.
- Parametry rows 17–30: no hard Play score threshold, conditional EV guidelines by confidence, no hard Play count limit.
- Parametry rows 46–53: CORE v1R ELO and linear probability formulas belong to historical backtest, not LIVE 2.1. Do NOT transplant.
- Rejestr rows 151–165 (sheet row numbers): historical LIVE KB2.1 notes contain STR/QUAL/MATCH breakdown and PRED/consensus for selected fixtures, though some older observations use other field arrangements. Example sheet row 152 Portugal–Wales: STR 33/35, QUAL 31/35, MATCH 26/30, score 90, P(model) 82%; row 153 Norway–Denmark: 31/35, 29/35, 24/30, score 84, P(model) 62%. These are archived evaluations, not reproducible equations.
- Calibration snapshot contains aggregate hit-rate/Brier and probability bands; not a function mapping raw stats to P(model).

## Recovery verdict
Original LIVE KB2.1 was an evidence-led analytical workflow with human-assessed block scores, not a fully specified deterministic API program. It CAN operate without paid API or xG as mandatory fields, but requires documented evidence, consistent analyst judgment, pre-match freeze, independent calendar confirmation, and review of probabilities.

## Safeguards
- Do not require real xG for each match when other sound quality indicators exist; label xG unavailable rather than inventing it.
- Do not auto-create P(model), Sport Score, or KB PLAY from recent goals alone.
- No historical backfills or alterations to existing N; do not modify Google Sheet during recovery.
- API Market and provisional Poisson remain separate.

## Next concrete milestone
Restore an analyst-led daily worksheet/report template with mandatory source provenance, three block assessments, pre-price probability, consensus, no-vig/EV, confidence and Calendar Gate. Compare new forward assessments with archived methodology before permitting register writes.
