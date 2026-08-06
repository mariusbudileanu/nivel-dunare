# International consolidation v2 — open issues

Date: 2026-08-06

## Active operational limitations

- **Austria:** automation remains manual pending a permanent institutional `DORIS_PARTNER_KEY`.
- **Slovakia:** Medveďov (`sk-5145`) remains outside the reviewed 13-station contract until identifiers, coordinates and Danube association are audited. The existing 13-station last-known-good remains fail-soft.
- **Croatia:** the accessible source remains stale; no numeric forecast is published.
- **Bulgaria:** forecast candidates remain outside the public contract until their semantics are demonstrated.
- **Serbia transport:** Ubuntu/OpenSSL cannot build the RHMZ chain with its standard trust bundle (`unable to get local issuer certificate`). Windows GitHub Actions `curl.exe`/Schannel validates both official hostnames and receives HTTP 200. Production collection therefore runs in a separate read-only Windows job and hands immutable payloads to Linux validation. No HTTP downgrade, custom CA, `verify=False`, `curl -k`, proxy or hostname-verification exception is used.
- **Serbia data:** observations are source-provisional and unvalidated. A failed NRT, daily or forecast component preserves its own last-known-good. Range pages are evidence, not point forecasts.
- **Locality coordinates:** 36 locations are approximate OpenStreetMap/Nominatim locality centres and retain `© OpenStreetMap contributors, ODbL` attribution.
- **Kachlet:** the legacy and current source objects remain separate streams at one physical location.

## Not active issues

- Serbia is no longer intentionally disabled: workflow run `31083512217` demonstrated standard HTTPS success on `windows-latest`, and the live candidate contained 13 stations, 2,348 observations and 36 point forecasts.
- The former numeric-temperature plausibility rule remains inactive legacy evidence.
- There are no unmapped international station records.

Exact current publication counts and source state must be read from the generated public contract. See `RHMZ_SERBIA_LIVE_INTEGRATION.md` for the evidence and repeat commands.
