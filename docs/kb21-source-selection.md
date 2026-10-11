# KB Score 2.1 — source selection (2026-10-11)

This is an integration plan, **not** authorization to produce original KB Score predictions.

## Roles and priorities

1. **API-Football (existing paid subscription)**: candidate fixtures, past results and goals. It is the primary feed only, not independent corroboration.
2. **football-data.org v4 (new credential needed)**: independent schedule cross-check for covered competitions. Free tier covers 12 competitions and is rate limited to 10 requests/minute. Never assume team IDs from API-Football equal football-data.org IDs: maintain explicit verified team mappings (competition, season, names, IDs) and require a unique home/away/date match. Schedule information can be delayed on free tier. This is **independent**, not automatically an *official league* confirmation.
3. **Understat (optional, subject to terms/access review)**: historical actual xG/xGA for the Big Five only (England, Spain, Germany, Italy, France). There is no official public API. Use only permissible imports and preserve original source attribution; never substitute goals scored for xG.
4. **ELO**: prefer a locally computed, versioned ELO from already licensed historical finished matches, with documented initialization, home advantage, K factor, promotion handling and chronological backtest. This is a NEW diagnostic input pending KB Score methodology approval, not automatically the original structural score. ClubElo CSV access is reported restricted as of September 2026, so do not rely on it.

## Coverage boundaries

- Portugal, Netherlands, Belgium, Turkey, Poland, national teams and UEFA competitions: do not claim Understat xG coverage. Keep xG null until a permitted provider supplies it.
- football-data.org free tier does not cover all leagues of the existing API-Football whitelist (notably Poland). Missing coverage must be shown, not inferred.
- Independent schedule comparison does not replace an official competition calendar; retain separate official and independent flags.
- Do not transfer provider-specific team IDs without a verified mapping.
- No new API credentials committed to GitHub. Store credentials only in GitHub Actions secrets.
- Do not populate original KB21 component scores or P(model) from proxy data. No PLAY/LEARN/CONTROL, register writes or N changes until the original methodology's requirements are satisfied.

## Implementation sequence

1. Create a football-data.org account and set GitHub Actions secret `FOOTBALL_DATA_ORG_KEY` (requires user's action).
2. Add a separate football-data.org v4 adapter, with a rate limit, error handling, deterministic snapshot and explicit team ID mapping.
3. Feed verified independent comparison evidence into the existing `kb21_independent_calendar.py` comparison layer, without automatic PLAY or official verification.
4. Add a permitted xG import for Big Five with pre-match cutoff and missing-data flags.
5. Backtest any self-computed ELO independently before considering model integration.

Sources:
- https://www.football-data.org/pricing
- https://www.football-data.org/coverage
- https://www.football-data.org/documentation/api
- https://understat.com/
