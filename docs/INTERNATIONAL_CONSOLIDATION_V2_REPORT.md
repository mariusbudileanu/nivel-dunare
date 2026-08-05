# International Danube consolidation v2

Date: 2026-08-05  
Contract: `1.3-beta`

## Result

The international contract contains 101 station streams at 93 physical locations. All 101 streams are mapped: 50 use exact official coordinates, 15 use exact manually verified coordinates, and 36 use approximate locality coordinates. `unmapped_stations.json` is empty. With the unchanged 23 AFDJ locations, the portal exposes 124 mapped station records before physical/co-location aggregation; the current GeoJSON renders 116 map icons (23 AFDJ + 93 international physical locations).

Hydrological values are reproduced as provided by official sources. Numeric plausibility thresholds do not classify or exclude values. Missing cells stay missing, negative values stay negative, source quality labels are preserved, and historical application-only findings are inactive audit evidence (`quality_origin=legacy_application_rule`, `active=false`).

## Source matrix before the final post-merge live run

| Country | Access | Automation | Update frequency | Freshness | Streams / physical | Coordinates | Published observations | Published forecasts | Integration | Limitation / next action |
|---|---|---|---|---|---:|---|---:|---:|---|---|
| DE | available | scheduled | daily 01:37 UTC | current | 18 / 17 | 18 official | 50 | 0 | complete | Kachlet's legacy and current source objects are two streams at one physical location; migration map retained. |
| AT | available | manual | workflow dispatch | current | 9 / 9 | 9 official | 18 | 476 | partial | Public DoRIS test key only; add `DORIS_PARTNER_KEY` after institutional approval. |
| SK | available | scheduled | daily 01:37 UTC | current LKG | 13 / 13 | 1 manual exact + 12 approximate | 51 | 392 | partial | Source-provided provisional status is retained; no local temperature threshold is active. Live discovery found the additional Medveďov option, which is fail-soft rejected pending inventory and coordinate review. |
| HU | available | scheduled | daily 01:37 UTC | current | 25 / 25 | 2 manual exact + 23 approximate | 115 retained live-history rows | 0 | complete | The next live publication reparses all three daypart columns; the fixture contract contains 125 rows. |
| HR | available | scheduled | daily 01:37 UTC check | stale | 3 / 3 | 3 official RIS | 30 historical | 0 | partial | Last source observation is 2026-03-12; recover automatically when a recent source date appears. |
| BG | available | scheduled by stream | 09:15 / 21:15 Europe/Sofia | current | 20 / 13 | 20 official RIS | 46 | 0 | partial | Manual and automatic streams are separate; forecast candidates remain diagnostic-only. |
| RS | TLS failed | disabled | none while disabled | unavailable | 13 / 13 | 12 manual exact + 1 approximate | 0 | 0 | suspended | Parser fixtures contain 75 observations and 32 point forecasts, but production makes no request until standard TLS validation passes. |

Counts above describe the committed last-known-good public snapshot before the final live workflow. The final report must use the post-merge artifact and public files, not infer successful live access from fixtures.

## Pre-merge GitHub validation

- fixtures all-source dry-run `31019609341`: success;
- final live all-source dry-run `31020421889`: success, public preview validated; DE 18/25/0, AT 9/9/240, HU 25/107/0, HR 3/30/0 and BG 20/46/0 public forecasts accepted; SK returned 14/27/245 but was fail-soft rejected against the reviewed 13-station inventory, and RS made no request while suspended;
- BG manual dry-run `31020513661`: success, HTTP 200/200, 20 streams, 46 observations, forecast candidates excluded from public output;
- BG automatic dry-run `31020703686`: success, HTTP 200/200, 20 streams, 46 observations, forecast candidates excluded from public output.

The artifact from each run was downloaded and its `update-summary.json`, raw archive, candidate outputs and validated public preview were inspected. GitHub's Node.js 20 deprecation warning was removed by upgrading the affected official actions to the stable Node.js 24-compatible majors available on 2026-08-05.
## RIS workbooks and provenance

The original attached workbooks were inspected across relevant sheets and verified against `data/reference/ris_station_registry.csv`:

- `hr-ris_index-v1_7.xls`: SHA-256 `3ef66a6ad4d7c35c6cab601dee93cb4bddc8f71a953b682b0f48f9117eea31f1`;
- `RIS_Index_BG_01.07.2021_v2p1.xlsx`: SHA-256 `0824b69d3bb8deb042514b4fa5e7bfb2bf5b36eebd3cf0e654ad20de4fc3c4d4`.

Each normalized RIS row records workbook, sheet, row, version/date, checksum, ISRS code, original coordinate text, CRS and provenance note. Croatia contributes 3 gauge rows. Bulgaria contributes 20 observation streams at 13 physical gauges. Nikopol deliberately reuses the single RIS object demonstrated by the workbook.

## Coordinates

Priority is official station coordinate, manually verified exact coordinate, accepted locality geocode, then unresolved. Official data are never overwritten by geocoding. Kachlet was transformed from EPSG:25832 (`E=825431.75`, `N=5389976.93`) to WGS84 using `pyproj 3.7.2`; both source and target metadata are retained. Approximate coordinates are attributed to `© OpenStreetMap contributors, ODbL` and are never used to infer river kilometre, distance or station order.

## Time, stream and forecast semantics

- HU publishes yesterday morning, yesterday evening and today morning as date + daypart. It does not invent an hour or timezone. Change within 24 hours is retained from the source.
- BG keeps manual and automatic stream IDs, source date/window and categorical trend. APPD forecast candidates have no public output.
- RS fixtures keep daily and NRT observations, raw timestamps/offsets, detected cadence, `prognoza`, `bezprognoza` and range-page distinctions. Range pages are not converted to point forecasts.
- HR date-only historical observations remain available but stale and excluded from current counts.

## Workflows and last-known-good

The general workflow schedules only DE, SK, HU and HR at `37 1 * * *`. The dedicated BG workflow uses UTC pairs `15 6`, `15 7`, `15 18`, `15 19` and a `Europe/Sofia` gate, so exactly the 09:15 manual or 21:15 automatic window runs across DST. AT is manual. RS is disabled and makes no request.

The updater isolates every source, merges history by stable stream/date/daypart keys, retains per-source last-known-good state and stages only whitelisted international public/reference paths. Collect jobs use `contents: read`; publication alone uses `contents: write` and `actions: write`. There is no force push, TLS bypass or fixture publication.

## Frontend

The portal presents Romania/AFDJ separately from the international beta. The header displays mixed update status and international run/source counts. Global and international summaries are dynamic. Trend, access, integration, automation, freshness, source-provided quality, station type, stream type and coordinate type are separate filters. The source table includes frequency and operational timestamps. Popups expose stream, source time, capture time, quality, freshness, coordinate provenance and source-specific warnings. RO/EN translation, URL language selection, localStorage persistence, keyboard navigation and responsive layouts remain active.

## Verification commands

```text
python -m unittest discover -s tests -v
python -m scripts.validate_repository
python -m scripts.validate_international_public_data
python -m scripts.geocode_international_stations --validate-only
python -m scripts.validate_ris_reference --workbook-dir <folder-with-original-workbooks>
python -m scripts.build_international_station_audit
```

JavaScript is checked with `node --check` for every module. JSON, GeoJSON, mirrors, source/station/stream/observation/forecast references, translations and secret scanning are enforced by the validators and tests.
