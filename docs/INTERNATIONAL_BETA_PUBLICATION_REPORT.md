# International beta publication snapshot

Contract `1.3-beta` keeps 101 international station records at 93 physical locations. All are mapped: 50 official exact, 15 manually verified exact and 36 approximate locality. With the unchanged 23 AFDJ locations, the portal exposes 124 station records and 116 physical map markers.

Serbia activation preserves those physical counts. The validated RHMZ model adds 12 NRT stream identities to the existing 101 station records, so an active RS publication contains 113 stream rows, 13 RS physical locations, 12 RS NRT streams and 13 RS daily streams. Slankamen has no invented NRT stream. Observation and forecast totals are live outputs and must be read from `status.json`, not copied into UI constants.

The pre-merge branch retains the previous RS last-known-good. The dedicated post-merge workflow collects on `windows-latest` with standard Schannel validation, hands immutable raw payloads to Linux, validates the complete contract and only then commits the active RS data. The frontend switches from the legacy suspended warning to the provisional RHMZ presentation only when validated RS observations are present.

Values are reproduced from official sources without application plausibility thresholds. Approximate coordinates remain attributed to `© OpenStreetMap contributors, ODbL`. Transport diagnostics and operational limits are in `RHMZ_SERBIA_LIVE_INTEGRATION.md`.
