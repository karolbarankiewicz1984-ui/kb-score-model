# MultiModel PWA — MM-03
React + TypeScript + Vite. Code only, no private data, server token or API keys. Local ZIP import from MM-02, Polish mobile interface, fixture filters/details, research candidate views, audit and calibration counters, IndexedDB transactional snapshot, versioned offline shell. No calls to sports providers or GitHub from the app.

## Development
Node 22, `npm install`, `npm test`, `npm run build`, `npm run preview`. Direct dependencies pinned; lockfile not yet committed. Use only trusted local ZIP from MM-02. Preview on localhost; production Android installation requires a trusted HTTPS origin and a successful first online load. Merely unzipping or opening index.html as a local file does not install a PWA. Do not publish private data or embed them in dist. No hosted deployment is configured yet.

## Safety and scope
- ZIP preflight (fixed names, duplicate/path/size checks, standard ZIP only), CRC, SHA-256, strict JSON, semantic validation of fixture/candidate identities, chronology, probability ranges and readiness flag; retain old snapshot if import fails. No source authentication via hashes alone. Import only the package you obtained through a trusted channel. IndexedDB is not app-encrypted; local device security matters. Browser storage can be evicted.
- Only historical snapshots; no current bookmaker quote or guaranteed payouts. No TOP until validated quality score. No math changes. Research view uses existing A/B/C thresholds and SHADOW separate label. Individual ABC settlements unavailable. All candidate rows retained; raw market rows and base forecasts preserved in bundle, full presentation and deeper filters in MM-04.
- MM-05 handles authenticated sync and private delivery; MM-06/07 detailed audit/calibration; MM-10 Android device and installation tests. CI contains synthetic tests and builds code only, not user data. Do not install or publish PWA on an untrusted origin.
