# International source operations

## Safe local checks

Fixture-only integration check (never publishes):

```text
python -m scripts.ingest_danube_sources --source all --fixture-root tests/fixtures/international --output-dir _diagnostics/international/fixtures --archive-root _diagnostics/international/fixtures/raw-archive
python -m scripts.update_international_data --source all --mode fixtures --action dry-run --output-dir _diagnostics/international/update-fixtures
```

A named live dry-run uses normal HTTP/TLS validation and stores raw bytes plus metadata under `_diagnostics`:

```text
python -m scripts.update_international_data --source scheduled --mode live --action dry-run --output-dir _diagnostics/international/live-dry-run
python -m scripts.update_international_data --source at --mode live --action dry-run --output-dir _diagnostics/international/live-at
python -m scripts.update_international_data --source bg --stream manual --mode live --action dry-run --output-dir _diagnostics/international/live-bg-manual
python -m scripts.update_international_data --source bg --stream automatic --mode live --action dry-run --output-dir _diagnostics/international/live-bg-automatic
```

RS selection never opens a client while disabled. Do not use HTTP, `verify=False`, `curl -k`, proxies or certificate exceptions.

## Public build and validation

The builder requires a named candidate folder, matching raw archive metadata, the 101-row audit and reviewed coordinate registries. It emits `stations.json`, `streams.json`, `observations.json`, `latest.json`, `forecasts.json`, `sources.json`, `status.json`, `stations.geojson`, `unmapped_stations.json`, and `quality_issues.json`, mirrored byte-for-byte.

```text
python -m scripts.build_international_station_audit
python -m scripts.build_international_public_data --candidate-root <candidate> --archive-root <archive> --operations-state data/reference/international_source_operations.json
python -m scripts.validate_international_public_data
python -m scripts.validate_repository
```

The audit must contain 101 rows: 88 active candidates and 13 suspended RS rows. All 101 have coordinates (50 official, 15 manually verified exact, 36 approximate).

## Schedules

- General: DE, SK, HU, HR at `37 1 * * *`.
- AT: manual dispatch only.
- BG: dedicated local gates at 09:15 manual and 21:15 automatic (`15 6`, `15 7`, `15 18`, `15 19` UTC trigger pairs).
- RS: no schedule while standard TLS validation fails.

## Last-known-good and retention

Failures are isolated per source and per BG stream. A failed or empty candidate cannot overwrite station, coordinate, history or last-known-good data. Deduplication includes station/stream/parameter/source date plus daypart/window; timestamped feeds use source observation datetime. Raw gzip and metadata are retained in workflow artifacts; public history is bounded by the updater policy and reviewed before extension.

## DoRIS key

Store a permanent key only as the GitHub secret or external environment variable `DORIS_PARTNER_KEY`. Never log, persist in a URL, fixture or artifact, or hardcode it. After provisioning: run AT live dry-run, scan artifacts for the key, validate the preview, then update automation policy in a separately reviewed change.

## Disable, rollback and recovery

To disable one stream, change only its source/stream selector to disabled, retain its last-known-good files and expose the error/timestamps in `sources.json`. Do not delete shared station or coordinate records.

To roll back a bad international publication, restore the last validated international public/reference commit only; do not revert AFDJ, AIS or Hetzner files. Re-run both validators and Pages. To recover a stale source, accept a new capture only after its source date passes the adapter freshness policy; the dynamic stale message then clears automatically.

RS may be reactivated only after both official hostnames are tested with standard TLS, redirect/security behavior is recorded, a low-volume live dry-run parses daily/NRT/forecast pages, all validators pass, and the dedicated schedule is explicitly enabled. Fixtures alone do not satisfy this gate.
