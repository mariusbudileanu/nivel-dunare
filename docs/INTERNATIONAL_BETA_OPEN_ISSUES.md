# International Danube beta open issues

These limitations are intentional and are surfaced as source statuses rather than hidden.

## Source limitations

- **Austria / AT — partial:** the validated beta capture uses the public viadonau test source. A permanent `DORIS_PARTNER_KEY` must be supplied outside Git before production scheduling. The key must never be persisted in URLs, logs, artifacts or frontend files.
- **Slovakia / SK — partial:** stations lack verified official coordinates. Iža temperature outliers are preserved as suspect quality evidence and excluded from current values. Valid levels and forecasts remain available.
- **Hungary / HU — complete observations, no map:** the official source provides a date for the published observations. No time or timezone is inferred. No official coordinate set or normalized numeric forecast is currently promoted.
- **Croatia / HR — stale and suspended:** the available feed is stale. Historical values are labelled and excluded from current metrics, trends and alerts. The three stations have no verified coordinate set.
- **Bulgaria / BG — partial:** source station IDs are not demonstrated and remain `null`; application slugs are not represented as institutional IDs. APPD forecast semantics, parameter, unit and year are not sufficiently demonstrated, so candidate forecasts are not normalized publicly. No verified coordinate set is available.
- **Serbia / RS — suspended:** the 13 audited official IDs and local names are registry-only. Live access remains disabled after certificate-chain validation failed. The adapter makes no request and TLS validation is not bypassed.

## Operational limitations

- International collection is still manual. No international production timer or systemd service is created by this beta.
- Refresh frequencies differ by national administration. The publication status and capture time must be read per source.
- Moving collection to Hetzner requires an isolated unprivileged runtime, locking, resource controls, retention, monitoring and a permanent viadonau credential. Exact preparation commands are in `INTERNATIONAL_HETZNER_MIGRATION.md`.
- HR and RS must not be enabled in an automated live collection until their respective stale-feed and TLS-chain problems are resolved and reviewed.
- The AFDJ and AIS services must remain operationally isolated from any future international scheduler.

## Data and presentation limitations

- Only 26 of 101 international stations have official verified coordinates. The other 75 are deliberately list-only.
- Source statuses describe integration maturity; they do not override observation-level quality.
- A green adapter run does not prove that a source is complete, current or suitable for every parameter.
- The portal is informational and does not replace official notices, navigation information or authority decisions.
