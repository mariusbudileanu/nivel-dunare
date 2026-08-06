# International source operations

## Safe local checks

Fixture-only checks never publish:

```text
python -m scripts.ingest_danube_sources --source all --fixture-root tests/fixtures/international --output-dir _diagnostics/international/fixtures --archive-root _diagnostics/international/fixtures/raw-archive
python -m scripts.update_international_data --source all --mode fixtures --action dry-run --output-dir _diagnostics/international/update-fixtures
```

Serbia live collection is intentionally GitHub-hosted on Windows because Schannel validated the official HTTPS chain while Ubuntu/OpenSSL did not. Dispatch `.github/workflows/update-serbia-data.yml` with `action=dry-run` for validation or `action=publish` for the controlled publisher. The Windows collect job has `contents: read`; only the Linux publish job has write permission. Do not use HTTP, `verify=False`, `curl -k`, `--insecure`, proxies, custom hostname rules or a bundled leaf certificate.

## Public build and validation

```text
python -m scripts.build_international_station_audit
python -m scripts.build_international_public_data --candidate-root <candidate> --archive-root <archive> --operations-state data/reference/international_source_operations.json
python -m scripts.validate_international_public_data
python -m scripts.validate_repository
```

The stable audit contains 101 active station records at 93 physical locations. All 101 have coordinates (50 official, 15 manually verified exact, 36 approximate). Active Serbia adds 12 NRT stream identities, producing 113 stream rows without changing station or marker counts.

## Schedules

- General: DE, SK, HU and HR daily at `37 1 * * *`.
- AT: manual dispatch only.
- BG: DST-safe 09:15 manual and 21:15 automatic Europe/Sofia gates.
- RS NRT: every three hours at minute 17; daily overlap reconciliation at 00:47 UTC.
- RS daily: UTC trigger pair gated to 10:20 Europe/Belgrade.
- RS forecast: UTC trigger pair gated to 12:35 Europe/Belgrade.

## Last-known-good and retention

Serbia keeps independent NRT, daily and forecast component state. A failed component preserves its previous validated records; empty candidates are rejected. Observation deduplication uses station, stream, parameter and source observation date/time. Raw Windows payloads, metadata and SHA-256 values are retained in workflow artifacts; Linux publishes only a validated whitelisted product.

## DoRIS key, rollback and migration

Store `DORIS_PARTNER_KEY` only as an external secret and never log or persist it. Rollback restores only the last validated international snapshot and operations state, then reruns both validators and the portal smoke test. It must not alter AFDJ, AIS or Hetzner components. Future Hetzner migration must preserve the same isolation, standard TLS validation, component last-known-good semantics and DST-safe schedules.
