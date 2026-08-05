# International GitHub automation — open issues

## External and source limitations

- DoRIS still uses a public test key. AT remains manual and `partial` until a permanent `DORIS_PARTNER_KEY` is supplied and reviewed. The key must not appear in repository files, logs, persistent URLs or artifacts.
- SHMÚ can publish structurally valid levels and forecasts while individual temperatures are suspect. These observations remain in `quality_issues.json` and the observation archive but are excluded from current values and statistics.
- Hydroinfo supplies an official observation date but no demonstrated observation time or time zone. The automation deliberately leaves datetime fields empty.
- The Croatian feed is currently stale. Its 30 historical observations remain available as history and excluded from `latest.json`; scheduled checks are intended to detect recovery.
- APPD does not demonstrate stable institutional station IDs or a validated forecast contract. IDs remain `null`, and downloaded forecast material remains diagnostic-only.
- The Serbian endpoint failed TLS certificate-chain validation in the audited environment. RS is disabled, inventory-only and performs no request. Certificate verification must not be weakened.

## Operational verification still required

- The workflow must be merged before GitHub can register and dispatch it from the default branch.
- After merge, run fixtures/all, live/all dry-run, scheduled-source live publish, manual AT live publish and RS no-request verification. Record every run ID and download each artifact; an HTTP 200 alone is not proof of a usable source.
- Confirm the automatic data commit rebases cleanly beside a concurrent Hetzner AFDJ commit. The workflow must stop on a real conflict and must never force-push.
- Confirm that explicit Pages dispatch occurs only after an actual successful data commit, then verify the deployed `status.json` and a representative station for every published source with a cache-busting query.
- GitHub-hosted source access can differ from local access. A source-specific failure should update its diagnostic state while leaving that source's last-known-good product records and all successful peer-source updates intact.

## Not part of this stage

- No semantic frontend, map panel, filter, card or legend reorganization.
- No AFDJ, AIS, Hetzner service/timer, Romanian canonical-data or public AFDJ contract change.
- No migration of international automation to Hetzner until GitHub runner behavior is measured and documented.
