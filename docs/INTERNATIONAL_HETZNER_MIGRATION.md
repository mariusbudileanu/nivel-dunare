# International sources: Hetzner migration preparation

This is a future migration runbook, not an activation. Do not create a timer or service from these examples until source-owner review is complete. Do not modify `scripts/run_hetzner_update.sh`, `nivel-dunare-afdj.service`, `nivel-dunare-afdj.timer` or the AIS service.

## Isolated directories and account

Use a separate unprivileged account and paths that are not used by AFDJ or AIS. Example names below are illustrative and must be reviewed on the server:

```bash
sudo install -d -o nivel-dunare-intl -g nivel-dunare-intl -m 0750 \
  /var/lib/nivel-dunare-international/{candidate,archive,public,locks} \
  /var/log/nivel-dunare-international
```

Keep the repository checkout read-only to the collector except during a separately controlled deployment step. Candidate and archive paths must never overlap `data/canonical`, the AFDJ archive/history, or AIS storage.

## Exact collection commands

From the repository root, run one source with the same contract used by GitHub diagnostics:

```bash
python -m scripts.ingest_danube_sources \
  --source de \
  --output-dir /var/lib/nivel-dunare-international/candidate/run-$(date -u +%Y%m%dT%H%M%SZ) \
  --archive-root /var/lib/nivel-dunare-international/archive
```

Replace `de` with `at`, `sk`, `hu` or `bg` only after that source is approved. `hr` must remain suspended while the feed is stale. `rs` must remain suspended while normal TLS certificate-chain validation fails; never use `verify=False` or `curl -k`.

Run all currently implemented adapters for a controlled diagnostic capture:

```bash
python -m scripts.ingest_danube_sources \
  --source all \
  --output-dir /var/lib/nivel-dunare-international/candidate/run-$(date -u +%Y%m%dT%H%M%SZ) \
  --archive-root /var/lib/nivel-dunare-international/archive
```

This does not make HR or RS publishable and does not promote candidate files.

For Austria, place the permanent key in a root-readable environment file outside Git:

```bash
sudo install -o root -g nivel-dunare-intl -m 0640 /dev/null /etc/nivel-dunare-international.env
sudoedit /etc/nivel-dunare-international.env
set -a
. /etc/nivel-dunare-international.env
set +a
python -m scripts.ingest_danube_sources --source at \
  --output-dir /var/lib/nivel-dunare-international/candidate/at-review \
  --archive-root /var/lib/nivel-dunare-international/archive
```

The environment file contains `DORIS_PARTNER_KEY=...`. Never print it, pass it on a command line, copy it into artifacts or persist the request query URL.

## Validation and promotion

Fail closed: stop before promotion when collection, parsing, schema validation, reference validation or repository validation fails.

```bash
python -m scripts.validate_repository
python -m scripts.validate_international_public_data \
  --root /var/lib/nivel-dunare-international/public \
  --mirror /var/lib/nivel-dunare-international/public-mirror
```

The public builder is run only against a named, reviewed candidate capture and its matching raw archive metadata:

```bash
python -m scripts.build_international_public_data \
  --candidate-root /var/lib/nivel-dunare-international/candidate/APPROVED_RUN/results \
  --archive-root /var/lib/nivel-dunare-international/candidate/APPROVED_RUN/raw-archive \
  --historical-quality-root /var/lib/nivel-dunare-international/quality-evidence/sk-20260804T145920Z \
  --historical-archive-root /var/lib/nivel-dunare-international/quality-evidence/raw-archive \
  --geocoding-registry /opt/nivel-dunare/data/reference/international_station_geocoding.csv \
  --output-root /var/lib/nivel-dunare-international/public \
  --mirror-root /var/lib/nivel-dunare-international/public-mirror \
  --live-run-id HETZNER-APPROVED_RUN
```

The `quality-evidence` paths above refer to the reviewed SHMU candidate capture and matching raw metadata that preserve the authentic Iža 46.2 °C observation. Restore them from the validated diagnostic artifact by SHA-256; do not synthesize the observation or its capture time.

The reviewed geocoding registry is a static build input. Do not invoke live geocoding from the Hetzner collector or public builder; locality coordinates change only through a separately reviewed registry update. Full policy is in `INTERNATIONAL_STATION_GEOCODING.md`.

Review `summary.json`, `issues.json`, source counts and SHA-256 metadata before any Git commit. Promotion must use a staging directory followed by an atomic rename only after validation; never replace a valid public dataset with an empty/partial failed run.

## Locking and resource controls

Use a dedicated lock and conservative resource limits, separate from AFDJ and AIS:

```bash
flock -n /var/lib/nivel-dunare-international/locks/collector.lock \
  systemd-run --quiet --wait --collect --scope \
  -p CPUQuota=25% -p MemoryMax=512M -p TasksMax=64 -p Nice=10 \
  python -m scripts.ingest_danube_sources \
  --source all \
  --output-dir /var/lib/nivel-dunare-international/candidate/manual-review \
  --archive-root /var/lib/nivel-dunare-international/archive
```

Do not reuse the AFDJ lock, service unit, timer, working directory, log or deployment script. Schedule collectors outside AIS and AFDJ peak windows only after measuring resource use.

## Retention, logs and alerts

- Retain raw gzip responses plus metadata/SHA-256 for at least 90 days; retain the most recent validated candidate and the dataset currently published indefinitely or according to the approved backup policy.
- Delete only paths resolved beneath `/var/lib/nivel-dunare-international/archive`; review a dry-run listing before retention cleanup.
- Send stdout/stderr to a dedicated journal identifier or `/var/log/nivel-dunare-international/`, with logrotate and no environment dump.
- Alert on non-zero exit, schema drift, missing stations, unexpected count changes, missing capture hashes, stale source age and failed promotion.
- A failed source never becomes an empty success and never overwrites the last validated public output.
- Monitor AIS and AFDJ service health independently before and after any future trial.
