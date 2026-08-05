# International consolidation v2 — pre-merge audit

- Contract: `1.3-beta`.
- International station streams: 101; physical locations: 93; mapped streams: 101; list-only: 0; combined portal map icons: 116 (23 AFDJ + 93 international physical locations).
- Coordinate classes: 50 official exact; 15 manually verified exact; 36 approximate locality.
- Current committed snapshot: 310 observations, 164 latest rows, 868 forecasts, 25 quality issues (23 active technical/source issues; 2 inactive legacy application-rule findings).
- Source dimensions: 2 complete, 4 partial, 1 suspended; automation 5 scheduled, 1 manual, 1 disabled; freshness 5 current, 1 stale, 1 unavailable.
- BG: 8 manual + 12 automatic streams, 13 physical markers, zero public forecasts.
- RS: 13 mapped inventory stations, 12 exact manually verified + 1 approximate, no public observations/forecasts while TLS is failed.
- SK: 13/13 mapped, 1 manual exact + 12 approximate; source-provisional values are not locally reclassified.
- HU: 25/25 mapped; fixture parser covers previous morning/evening and current morning without invented hours.
- HR: available/scheduled/stale/partial, with dynamic last-observation date.

All figures are builder outputs, not UI constants. See `INTERNATIONAL_CONSOLIDATION_V2_REPORT.md` for source detail and commands.
