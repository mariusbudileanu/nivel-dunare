# International Danube beta open issues

These limitations are intentional and are surfaced as source statuses rather than hidden.

## Source limitations

- **Austria / AT — partial:** the validated beta capture uses the public viadonau test source. A permanent `DORIS_PARTNER_KEY` must be supplied outside Git before production scheduling. The key must never be persisted in URLs, logs, artifacts or frontend files.
- **Slovakia / SK — partial:** no official station coordinate set was found. Twelve accepted locality positions are approximate; `sk-5128` remains unresolved. Iža temperature outliers are preserved as suspect quality evidence and excluded from current values. Valid levels and forecasts remain available.
- **Hungary / HU — complete observations:** the official source provides a date only. No time or timezone is inferred. Twenty-three accepted locality positions are approximate; Doborgaz and Kvassay zsilip remain unresolved. No official coordinate set or normalized numeric forecast is currently promoted.
- **Croatia / HR — stale and suspended:** the feed is stale. Historical values remain excluded from current metrics. Aljmaš and Vukovar use approximate locality positions; Batina remains unresolved. Geocoding does not reactivate the source.
- **Bulgaria / BG — partial:** source station IDs are not demonstrated and remain `null`. Seventeen stations use accepted approximate locality positions; Bajkal and both Novo Selo rows remain low-confidence/review-required. APPD forecasts remain unnormalized because their semantics are not demonstrated.
- **Serbia / RS — suspended:** all 13 audited IDs have accepted approximate locality positions, but remain suspended and have no observations/forecasts. Geocoding made no request to the Serbian hydrology endpoint; TLS was not bypassed.

## Operational limitations

- The GitHub automation branch schedules DE, SK, HU, HR and BG daily at 01:37 UTC. AT remains manual and RS remains disabled; no international systemd service is created.
- Refresh frequencies differ by national administration. The publication status and capture time must be read per source.
- Moving collection to Hetzner requires an isolated unprivileged runtime, locking, resource controls, retention, monitoring and a permanent viadonau credential. Exact preparation commands are in `INTERNATIONAL_HETZNER_MIGRATION.md`.
- HR and RS must not be enabled in an automated live collection until their respective stale-feed and TLS-chain problems are resolved and reviewed.
- The AFDJ and AIS services must remain operationally isolated from the international GitHub scheduler.

## Data and presentation limitations

- Of 101 international stations, 26 have exact official coordinates, 67 have accepted approximate locality positions, and 8 remain list-only. Approximate positions are not gauge/sensor locations and are excluded from spatial precision, distance, river-kilometre inference and location-based ordering.
- Source statuses describe integration maturity; they do not override observation-level quality.
- A green adapter run does not prove that a source is complete, current or suitable for every parameter.
- The portal is informational and does not replace official notices, navigation information or authority decisions.
