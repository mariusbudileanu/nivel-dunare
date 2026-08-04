# International Danube sources — implementation report

Date: 2026-08-04
Scope: independent candidate-data adapters only. This work does not modify AFDJ, canonical/public data, the frontend, GitHub Pages, production cron or the Hetzner service.

## Outcome

Six source adapters and one explicit suspended source state are implemented behind a common fail-closed contract. Raw responses are saved byte-for-byte in gzip archives with URL, capture time, HTTP status, content type, byte count, SHA-256 and adapter version. Normalized results are written only to a caller-selected review directory; no adapter publishes to `public/` or canonical datasets.

| Country | Administration | Format | Found | Danube primary | With coordinates | Without coordinates | Observations available | Local test | GitHub Actions | Final status | Blocker | Hetzner recommendation |
|---|---|---|---:|---:|---:|---:|---|---|---|---|---|---|
| DE | WSV PEGELONLINE | JSON | 27 | 18 | 17 | 1 | level, discharge, temperature where series exist | parsed/normalized/validated: complete | pending manual run | complete | one metadata coordinate gap | ready for later independent probe |
| AT | viadonau DoRIS | JSON | 10 | 9 | 9 | 0 | level, variation, 240 forecast points in live sample | parsed/normalized/validated: partial | pending manual run | partial | public test key | provision permanent key before activation |
| SK | SHMÚ | HTML + JavaScript | 13 | 13 | 0 | 13 | level, optional temperature, 196 forecast points in live sample | parsed/normalized; validation partial | pending manual run | partial | Iža reported implausible 46.2 °C | probe independently; alert on critical quality issue |
| HU | OVF Hydroinfo | HTML | 93 | 25 | 0 | 25 | level, variation, discharge, temperature; narrative forecast only | parsed/normalized/validated: complete | pending manual run | complete | official coordinates unavailable | ready for later independent probe |
| HR | Croatian waterways/DHMZ | JSON | 3 | 3 | 0 | 3 | dated level history | parsed/normalized; validation suspended | pending manual run | suspended | newest record was 2026-03-12 | probe for restoration, never publish as current while stale |
| BG | APPD | HTML | 26 | 20 current | 0 | 20 | level, some discharge, temperature, categorical trend, 30 forecasts | parsed/normalized; validation partial | pending manual run | partial | no stable institutional IDs; forecast contract incomplete | metadata/operator review before any activation |
| RS | RHMZ/Hidmet | HTML | 13 audited | 13 audited, 0 activated | 0 | 13 | not collected by implementation | deliberately no request | pending manual run | suspended | TLS certificate chain validation | do not deploy until normal TLS validation succeeds |

The committed audit contains 88 primary station rows and 26 verified coordinate pairs. No coordinates were inferred from names, river kilometres, third-party maps or cross-border matches. The source row `KACHLET WEHR UP` has no official coordinate pair in the audited PEGELONLINE payload and remains blank.

## Adapter behavior

### Germany — PEGELONLINE

The adapter calls the official REST endpoint with `waters=DONAU`, timeseries and current measurements. It requires `water.shortname=DONAU`, excludes nine rows whose `agency=VIA DONAU`, uses station UUID as the source identity, and accepts only demonstrated `W`, `Q` and `WT` series. ISO-8601 source offsets are retained and UTC is calculated from that explicit offset. Coordinates are used only when present in the official JSON.

Official API documentation: <https://www.pegelonline.wsv.de/webservice/dokuRestapi>

### Austria — viadonau DoRIS

The list and status endpoints are joined on `objectID`. `Schwedenbrücke` is explicitly excluded because it is on Donaukanal. Current level, difference and `[target, central, minimum, maximum]` forecast arrays are retained. Millisecond timestamps are UTC and are also represented in `Europe/Vienna` for local display. The documented public `opendata` test key makes a run non-publishable; set `DORIS_PARTNER_KEY` to a permanent project key before production use.

Official API: <https://opendata2.doris-info.at/swagger-ui/index.html>

### Slovakia — SHMÚ

Station discovery is semantic: only official selector options ending in `- Dunaj` are included. Each discovered station page is downloaded once, its latest `Merané hodnoty` row is parsed, and its inline `forecast_serie` is retained when present. A missing optional temperature column does not discard a valid water level. The official page presents local civil time; it is stored as `Europe/Bratislava` and converted to UTC. No coordinates are exposed in the audited pages. In the live 2026-08-04 run, Iža reported `46.2 °C`; the range validator kept all raw data but marked the result partial instead of publishing that implausible value.

Official station page: <https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id=5140>

### Hungary — OVF Hydroinfo

The adapter parses the official Danube table and includes only code-prefix `4` Hungarian primary rows. The 68 foreign rows remain excluded validation context and are never substituted for a national primary source. The audited English forecast page is narrative only; the adapter verifies the six-day marker but invents no numeric station forecast. The table exposes a date but no observation time or timezone, so neither is inferred.

Official table: <https://www.hydroinfo.hu/tables/dunhif.html>

### Croatia — Croatian waterways/DHMZ

The three official identifiers `5001`, `5170` and `5070` map to Aljmaš, Batina and Vukovar. Dates and centimetre values are preserved without inventing a time or timezone. A latest observation older than seven days suspends the adapter. At the 2026-08-04 audit, the latest returned sample was 2026-03-12, so the live source is not eligible as current data.

Official feed: <https://vodniputovi.hr/dhmz_vodostaji/getwaterstuff.php>

### Bulgaria — APPD

The adapter keeps the eight hydrometeorological rows and twelve automated rows distinct. River kilometre is metadata, not an invented source identifier. The source exposes no demonstrated stable institutional station IDs, so `source_station_id` stays blank and validation is critical. Categorical six-hour direction is retained from the image filename. Five forecast tables with six values each are parsed; raw `DD.MM` targets are preserved without inventing a year, time or timezone. Publication remains closed pending institutional identifier and forecast-semantics confirmation. Six historical document-index rows are excluded from current observations.

Official pages: <https://www.appd-bg.org/hidrology-en> and <https://www.appd-bg.org/forecasts-en>

### Serbia — suspended

The adapter intentionally performs no request. The audited official endpoint did not provide a normally verifiable TLS certificate chain. No `verify=False`, `curl -k`, alternate proxy, certificate suppression or HTTP downgrade is implemented.

## Local live verification

One sequential run with no retries produced: DE complete (18 stations, 25 observations); AT partial (9 stations, 9 observations, 240 forecast points, public test key); SK partial after reparsing archived data (13 stations, 25 observations, 196 forecast points, one implausible official temperature); HU complete after strict ISO-8859-2 decoding (25 stations, 75 observations); HR suspended (3 stations, 30 historical observations); BG partial (20 stations, 46 observations, 30 forecasts); RS suspended without a request. The first BG attempt exposed a misspelled route in code (hydrology-en); the demonstrated official route hidrology-en was corrected and verified once. No canonical or public data was written.

## Validation contract

Critical validation includes mass station disappearance, duplicate canonical IDs or slugs, absent required source IDs, incomplete/out-of-country coordinates, impossible values, future observations and inconsistent forecast bounds. Empty responses, non-200 responses, common anti-bot pages, wrong content formats and structural schema changes fail before normalization.

Fixture snapshots are synthetic parser contracts, not claimed live observations. They exercise all expected station counts and source-specific shapes without making network requests. The real station inventory and coordinate audit are in `docs/INTERNATIONAL_STATIONS_AUDIT.csv`.

## GitHub Actions

`.github/workflows/test-international-sources.yml` is manual-only (`workflow_dispatch`) and read-only (`contents: read`). It accepts a source selector and `fixtures`/`live` mode, runs validation, and uploads raw archives, normalized candidate files and summaries. It never commits or pushes data.
