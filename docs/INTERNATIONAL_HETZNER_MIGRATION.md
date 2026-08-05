# International sources — future Hetzner migration

This is documentation only. The current AFDJ Hetzner script, service, timer and AIS configuration are unchanged.

Use a separate unprivileged account, working directory, archive, lock and logs. No path may overlap AFDJ canonical/history/public data or AIS storage. Run the same `scripts.update_international_data` dry-run and public validators used by GitHub before any promotion. Promote a named validated snapshot atomically; a failed source retains its own last-known-good data and cannot erase other streams.

Schedules must remain independent: DE/SK/HU/HR daily; AT manual until a permanent `DORIS_PARTNER_KEY`; BG at DST-safe 09:15/21:15 Europe/Sofia gates; RS disabled until standard TLS succeeds and the live parser/validator gate passes. Never use `verify=False`, `curl -k`, HTTP downgrade or an unofficial proxy.

Store `DORIS_PARTNER_KEY` in a root-readable environment file outside Git, load it without printing the environment and scan logs/artifacts before promotion. Apply CPU/memory limits and a dedicated lock. Keep raw responses and SHA-256 metadata under an approved retention policy; never delete through unresolved variables or paths outside the isolated archive.

Rollback restores only the last validated international snapshot and operations state, followed by international/repository validation and a portal smoke test. It must not revert or restart AFDJ/AIS components. Full commands, disable/recovery steps and the RS reactivation gate are in `INTERNATIONAL_SOURCES_OPERATIONS.md`.
