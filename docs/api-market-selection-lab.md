# API Market selection lab — shadow experiment (2026-10-15)

This package is an **independent, read-only historical audit**, not a replacement
for KB Score 2.1, API Market's core calculations or the live multi-day scan.

## What it compares

- Published, settled pre-match positions (published=true, hit 0/1), deduplicated
  by observation_id. Failed settlements with missing match statistics are excluded
  from win/loss denominators and counted as source errors.
- Existing selection: final score >= 67 and best recorded pre-match bookmaker
  odd >= 1.20 (all quoted bookies).
- The same positions excluding corners.
- Max three positions per fixture by score, with/without a distinct-market rule.
- Strictly verified STS/Superbet quotes vs. available Betano quotes.
- Accuracy and hypothetical flat-unit-stake profit by day, market and score band.
  Unique fixture counts are displayed to flag correlation.

**Important:** model score /100 is not automatically a calibrated probability,
and we must not infer positive expected value solely by comparing it to 1/odds.
The best price from all bookmakers is optimistic: it might not have been available
in Poland. Profit ignores taxes, limits and void-specific rules.
Same-match positions are correlated.

## Run locally (no API key)

From repository root:

    python -m unittest discover -s tests -p 'test_api_market_selection_lab.py' -v
    python tools/api_market_selection_lab.py \
      data/api_football/calibration/2026-10-12.json \
      data/api_football/calibration/2026-10-13.json \
      data/api_football/calibration/2026-10-14.json

Read reports/api_market_scan/selection_lab/SELECTION_AUDIT.md and the corresponding JSON.

## GitHub Actions

The workflow .github/workflows/api-market-selection-lab.yml uses read-only
repository permissions and artifacts only. Once merged into default branch,
it can run daily at 08:00 UTC after existing settlement, or manually using
3/7/14/30 latest dated settlement files.

**Until merged, it is not enabled on main.** No existing production code or
workflows are modified by this experiment branch.

## Initial diagnostic — 12–14 October 2026

94 published settled positions with quoted odds >= 1.20:
- 66 wins, 70.21% accuracy, -9.00% hypothetical best-price ROI.
- Without corners: 76 positions, 58 wins, -0.54% ROI.
- Max three highest-score positions per fixture: 58 positions, -19.14% ROI.
- Max three distinct markets per fixture: 54 positions, -12.85% ROI.
- Strict STS/Superbet subset: 0 verified quotes in these snapshots.
- Settlement files recorded 22 missing-stat errors on 14 October.

Retrospective comparisons of this small and correlated sample are
**not** proof of future performance. Validate on subsequent frozen data before
changing live filters.

## Follow-up: fixture-equal diagnostics and market mix

The v2 report retains the earlier position-weighted hit rate and ROI, and
adds **fixture-equal hit rate and ROI**, giving each match one vote (its
average over the selected positions). This prevents a match with 15 related
corners lines dominating a match with a single suggested position. These
figures are *descriptive only*: they do not make fixture outcomes
statistically independent and cannot prove future profitability.

New audit splits include competition, market/direction, market scope,
odds ranges (1.20-1.39, 1.40-1.59, 1.60-1.99, 2.00+), and model version
counts. Diagnostic flags call out missing settlement statistics, no
confirmed STS/Superbet quotes, mixed model versions and fewer than 30
unique matches. Any sub-group with fewer than 10 matches is explicitly
labeled very-small-sample; 10-29 is labeled preliminary; 30+ still
requires prospective validation.

October 12, 2026 contained domestic-league matches while October 13
and 14 were dominated by UEFA Champions League matches; comparing days
without considering competition is potentially misleading.

Retain identical production parameters (score >= 67, odds >= 1.20,
unchanged market selection), and use new fields to **diagnose**, not to
automatically retrain or change any market threshold.
