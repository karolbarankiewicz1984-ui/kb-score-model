# MultiModel panel export v1 (MM-02)
The isolated Python exporter accepts three existing local ZIPs: ABC complete, OddsPapi daily, and rolling audit. No network, secrets, provider requests, model recalculation, or upload. Run IDs are supplied by the caller and must be checked against Actions metadata at download. Example (placeholders):
```
python -m github_models.panel_export --abc abc.zip --odds odds.zip --audit audit.zip --day YYYY-MM-DD --abc-run 1 --odds-run 2 --audit-run 3 --out panel.zip
python -m unittest discover -s tests -p test_multimodel_panel_export.py
```
## Contract
ZIP has nine JSON sections and MANIFEST.json. Manifest schema multimodel-panel-v1; per-section SHA-256 and size, source archive/member hashes, source run IDs, generation, forecast cutoff, Warsaw day, and separate audit as-of. Historical snapshot only. Payloads preserve source schemas; this is a v1 transport contract, not a fully normalized per-row database.
- FIXTURES: queue; canonical fixture_id is provider-scoped PitchAPI, kickoff_utc, team and league IDs.
- FORECASTS: independent predictions, event markets, ABC candidate variants, SHADOW, status of the missing 67/100 quality score. ABC probability_min is not a calibrated probability or a quality score. TOP blocked until a verified score exists.
- ODDS: source exact comparisons and SHADOW overlay separately, gaps. Historical prices below 1.20 retained for provenance; never eligible for TOP. The panel_links section provides conservative read-only joins within the fixed source full-time match-market schemas: fixture, market, line, selection, model, source cutoff, probability tolerance 1e-5 and prematch quote timestamp not before freeze. Each ABC variant remains a separate row; repeated variants are not independent evidence. SHADOW overlay quotes retain research status and may lack source market IDs; no claim of verified official payout. Ambiguous or missing quotes remain null. The research view uses existing ABC thresholds 0.70/0.75/0.80, not a replacement quality score. Missing price remains null. Do not treat odds comparison as confirmed bookmaker settlement.
- RESULTS: independently sourced historical rows and event rows, plus exact SHADOW outcomes. Secondary source IDs are not PitchAPI IDs; no name-only automatic linking. Detailed ABC settlement crosswalk still required.
- AUDIT: ABC/SHADOW model-only and priced historical summaries kept separate. No counting correlated proposals as independent matches.
- CALIBRATION_READINESS: preserved diagnostic report, authorisation false.
- CALIBRATION_EXPERIMENTS: not available, empty.
- MODEL_VERSIONS: observed model ID/version pairs only, not a complete version history.
- SOURCE_HEALTH: source status and gaps; invalid optional API final manifest quarantined, not silently corrected.
## Import
Read only; reject unsupported schema, unknown/missing members, duplicate ZIP/JSON keys, non-finite JSON, oversize, invalid CRC, inconsistent checksums. Compare source cutoff and independent audit as-of against last accepted snapshot. Import transactionally and keep previous snapshot on error. The Python verifier checks transport integrity, not cryptographic authenticity or complete section-specific schemas; client-side IndexedDB and full semantic validation remain future work. For identical forecast and audit timestamps reject differing payload hash maps; identical payload is idempotent.
No publishing bundle or private data to the public repository. CI is isolated from provider workflows; no scheduled export or publication. Authenticated download/private storage and license checks are prerequisites for production synchronization. Do not infer full coverage, freshness, exact matches or calibration from successful transport.
