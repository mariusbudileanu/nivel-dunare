# International consolidation v2 — open issues

Date: 2026-08-05

## Active operational limitations

- **Austria:** access works with the permitted public DoRIS test key, but automation remains manual and integration remains partial. A permanent institutional key must be stored only as `DORIS_PARTNER_KEY`, followed by live dry-run, validation and an explicit policy update.
- **Croatia:** the endpoint is accessible and checked daily, but its latest demonstrated observation is 2026-03-12. The last-known-good history is public as stale; no numeric forecast is published.
- **Bulgaria:** manual and automatic windows are operational observations, not an official APPD publication guarantee. APPD forecast candidates remain outside the public contract until parameter, unit, issue time and target semantics are demonstrated.
- **Serbia:** the adapter and fixtures are implemented, but production access remains disabled because standard TLS certificate-chain validation failed in the audited environment. No HTTP downgrade, `verify=False`, `curl -k`, proxy or other bypass is permitted. Reactivation requires valid TLS for an official hostname plus a successful live dry-run and validator run.
- **Locality coordinates:** 36 locations are approximate OpenStreetMap/Nominatim locality centres. They are visibly distinguished and cannot be used for distance, precision, river-kilometre inference or station ordering.
- **Kachlet:** PEGELONLINE exposes a legacy and a current source object. They are retained as two source streams at one physical location and one map marker; the migration map must be preserved.
- **Committed HU history:** the pre-merge last-known-good snapshot predates the three-daypart parser output for older rows. The fixture demonstrates 125 observations (three water-level dayparts plus current morning parameters). The post-merge live publisher must validate and publish new daypart records without rewriting older source facts.

## Not active issues

- The former numeric-temperature plausibility rule is removed. Its two historical SHMU findings are inactive audit evidence and do not classify, hide or exclude official values.
- There are no unmapped international station streams in contract `1.3-beta`.
- There are no public APPD forecast rows and no public RHMZ observation/forecast rows while RS is disabled.

## Reactivation gates

For any disabled or failed stream: capture raw response with normal security validation, pass adapter/schema/reference checks, run a dry-run against last-known-good, validate the public preview and mirrors, inspect source timestamps/units, then change only that stream's operational state. Other sources and the AFDJ pipeline must remain untouched.
