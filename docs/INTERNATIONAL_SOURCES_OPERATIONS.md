# Running the international source adapters

The adapters are isolated candidate-data collectors. They do not update `public/`, canonical files or AFDJ data.

## Local contract test

From the repository root:

```powershell
python -m scripts.ingest_danube_sources `
  --source all `
  --fixture-root tests/fixtures/international `
  --output-dir _diagnostics/international/local-fixtures `
  --archive-root _diagnostics/international/local-fixtures/raw-archive
```

On Linux/macOS:

```bash
python -m scripts.ingest_danube_sources \
  --source all \
  --fixture-root tests/fixtures/international \
  --output-dir _diagnostics/international/local-fixtures \
  --archive-root _diagnostics/international/local-fixtures/raw-archive
```

Run one low-volume live source by replacing `de` with `at`, `sk`, `hu`, `hr`, `bg` or `rs`:

```bash
python -m scripts.ingest_danube_sources \
  --source de \
  --output-dir _diagnostics/international/live-de \
  --archive-root data/archive
```

`--source all` performs one request per JSON page, two requests for the two-page sources, and one request per SHMÚ station after discovery. There are no retries. Do not run it repeatedly or on a short loop.

For Austria, provide a permanent key only through the environment:

```bash
export DORIS_PARTNER_KEY='value-provided-by-viadonau'
python -m scripts.ingest_danube_sources --source at --output-dir _diagnostics/international/live-at
```

Without it, the public test key is used transparently and the result remains `partial`/non-publishable.

## Outputs

- Raw response: `data/archive/<source>/<YYYY>/<MM>/<timestamp>-<label>.raw.gz`
- Raw metadata: adjacent `.metadata.json`
- Candidate records: `<output>/<selector>/stations.json`, `observations.json`, `forecasts.json`
- Validation: `<output>/<selector>/issues.json` and `summary.json`
- Aggregate status: `<output>/summary.json`

Exit code `2` means a source could not be safely fetched or parsed. Exit code `3` is returned only when `--require-publishable` is supplied and at least one source is partial/suspended. HTTP or schema failures are never converted into empty successful datasets.

## Hetzner preparation — no production activation

The same commands work on the current Hetzner checkout with Python 3.11+ and no third-party packages. Before any future integration:

1. create a separate unprivileged working directory and archive retention policy;
2. provide `DORIS_PARTNER_KEY` through a root-readable environment file, never Git;
3. run each source independently and inspect `publishable` plus critical issues;
4. keep output outside the AFDJ canonical/public data path;
5. add locking, notification and a conservative schedule only after source-owner review;
6. never alter the existing AFDJ service or timer as part of this collector.

This change intentionally creates no cron entry, systemd service or timer.

## GitHub manual run

Actions → **Test international Danube sources** → **Run workflow**. Select a source and `fixtures` or `live`. The workflow has `contents: read`, uses no secret in fixture mode, performs no commit, and uploads a 14-day artifact containing raw, normalized and validation files.

## Rebuilding the station audit

```bash
python -m scripts.build_international_station_audit
```

The builder fails unless the reviewed selection still contains exactly 88 primary station records, which makes accidental disappearance or scope drift visible.
