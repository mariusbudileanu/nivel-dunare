# International consolidation v2 — pre-merge audit

- Contract: `1.3-beta`.
- Stable registry: 101 international station records at 93 physical locations; all are mapped. Together with 23 AFDJ locations the portal has 124 station records and 116 physical markers.
- Coordinate classes remain unchanged: 50 official exact, 15 manually verified exact and 36 approximate locality.
- RS integration adds twelve NRT source streams without adding physical locations. After the first validated RS publication, `streams.json` contains 113 streams while `stations.json` remains at 101 records and the map remains at 93 international physical markers.
- RS: 13 official Danube gauges, 12 manually verified exact coordinates and one accepted approximate locality coordinate; 12 NRT streams plus 13 daily streams, with Slankamen daily-only.
- The branch deliberately retains the previous committed RS last-known-good until the post-merge Windows/Schannel collection and Linux validation publish validated live data.
- BG remains 8 manual + 12 automatic streams at 13 physical markers, with no public forecast.
- SK remains 13/13 mapped and partial; Medveďov remains outside the contract pending audit.
- Approximate coordinates retain the attribution `© OpenStreetMap contributors, ODbL`.

All counts are builder outputs. Serbia transport evidence and activation rules are documented in `RHMZ_SERBIA_LIVE_INTEGRATION.md`.
