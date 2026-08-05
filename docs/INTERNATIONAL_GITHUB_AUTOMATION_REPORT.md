# International GitHub automation

Status: implementation branch `feature/international-github-automation`.

## Scope and isolation

The international updater is independent from AFDJ, AIS and the Hetzner services. It reads and writes only the international public contract and its versioned operational state. It does not change `scripts/run_hetzner_update.sh`, Romanian canonical data, the AFDJ workflows, frontend behavior or the Pages deployment definition.

The orchestration entry point is:

```text
python -m scripts.update_international_data --source <selector> --mode <fixtures|live> --action <dry-run|publish>
```

Every selected adapter is executed separately. Its payloads are archived with metadata and SHA-256, then parsed and validated. A rejected capture cannot replace that source's committed last-known-good data, while accepted captures from other sources remain publishable. Empty station results, access errors, unexpected critical issues and unexpected adapter states fail closed for that source only.

## Source policy

| source | automation | publication policy |
|---|---|---|
| DE / PEGELONLINE | scheduled | validated observations; Austrian republications remain excluded |
| AT / DoRIS | manual | partial; public test key warning; `DORIS_PARTNER_KEY` supported when configured |
| SK / SHMÚ | scheduled | partial; suspect temperatures retained as quality evidence and excluded from current values |
| HU / Hydroinfo | scheduled | complete; source date retained without inventing an hour or time zone |
| HR | scheduled | stale history retained; each run checks automatically for recovery |
| BG / APPD | scheduled | observations only; public forecasts always empty; institutional IDs remain `null` |
| RS | disabled | inventory only; no request is made after the demonstrated TLS validation failure |

The daily schedule is `37 1 * * *`, or 01:37 UTC. GitHub Actions schedules are UTC and may start later than the nominal minute. AT and RS are excluded from the scheduled selector. AT can be selected manually; RS selection records the disabled diagnostic without opening a network client.

## Last-known-good state

`data/reference/international_source_operations.json` stores one record per source with:

- `last_attempt_at` and `last_attempt_status`;
- `last_success_at`, `last_success_capture_at`, `last_capture_at` and `last_success_commit`;
- structured and text error fields;
- `consecutive_failures`;
- `published_snapshot_date` and `next_expected_update`.

The public `sources.json` contract is version `1.2-beta` and exposes independent `source_status`, `automation_status`, `freshness_status` and `validation_status` dimensions, plus the operational timestamps and bilingual validation messages. No generic source `status` field is emitted.

On failure, the previous station/observation/forecast set and successful capture metadata are preserved. Only attempt/error fields and the consecutive-failure count change. HR may legitimately retain stale history as its last-known-good snapshot. A valid recent HR capture changes freshness to `current` and source status to `complete` automatically.

## Artifacts and publication

Raw responses, archive manifests, SHA-256 values, candidates, issues, per-source reports and `update-summary.json` belong to the Actions artifact, not Git. Retention is 30 days. Cookies, tokens, HTTP caches and complete artifact directories must not be staged.

A publish run follows this order:

1. execute all selected sources independently;
2. merge accepted candidates with committed last-known-good records;
3. build both international public mirrors;
4. validate the contract, references, JSON/GeoJSON and geocoding;
5. run the repository test suite and smoke checks;
6. stage only `data/public/international`, `public/data/international` and `data/reference/international_source_operations.json`;
7. create no commit when that whitelist has no change;
8. fetch and rebase on the latest `origin/main`, without force, with at most one controlled retry;
9. push only after all checks pass;
10. dispatch `deploy-pages.yml` only after a successful new commit and push.

This explicit Pages dispatch is required because a push made with `GITHUB_TOKEN` is not assumed to trigger a second workflow. No personal token is required or persisted.

## Manual commands

Fixture validation of all adapters, without publication:

```text
python -m scripts.update_international_data --source all --mode fixtures --action dry-run --output-dir _diagnostics/international/fixtures
```

Live dry-run of all sources:

```text
python -m scripts.update_international_data --source all --mode live --action dry-run --output-dir _diagnostics/international/live-dry-run
```

Manual Austria publication after reviewing the capture:

```text
python -m scripts.update_international_data --source at --mode live --action publish --output-dir _diagnostics/international/live-at
```

When a permanent DoRIS partner key is available, configure the Actions secret `DORIS_PARTNER_KEY`. Do not print it, persist it in URLs or place it in artifacts. Adding AT to `SCHEDULED_SOURCES` and the workflow's scheduled source list is the only policy activation step, after a reviewed live run confirms the permanent contract.

## Disable and rollback

To stop scheduled international collection quickly, disable the `Update international Danube data` workflow in GitHub Actions. A code change that removes only the `schedule` event is the versioned alternative; manual diagnostics remain available. Do not disable AFDJ or Hetzner.

Rollback the product data by reverting only the automatic international data commit. The next workflow run starts from the restored public snapshot and operation state. Never reset `main`, force-push, delete AFDJ commits or restore Romanian paths as part of this rollback.
