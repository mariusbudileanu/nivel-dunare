# International station locality geocoding

Status: controlled one-time beta run completed on 2026-08-04. This process does not alter canonical station IDs or names and is not part of the production ingestion workflow.

## Result

| Item | Count |
|---|---:|
| Stations evaluated | 75 |
| Exact official station coordinates retained | 26 |
| Accepted approximate locality positions | 67 |
| Medium-confidence results | 67 |
| Low-confidence, review-required results | 3 |
| Unresolved results | 5 |
| International points in GeoJSON | 93 |
| Stations remaining list-only | 8 |

The public Nominatim endpoint was used for a small, one-time task. The run used one machine, one thread, a descriptive User-Agent, no more than one request per 1.1 seconds, no retries, and a persistent cache. There were 75 HTTP queries in total: 69 initial queries and six locality clarifications. The current 75-station inventory has 68 unique final query strings because manual/automatic stations at the same locality share a query.

Provider: OpenStreetMap Nominatim. Coordinate method: `geocoded_locality`. Data attribution: © OpenStreetMap contributors, ODbL. These coordinates are locality centres returned by the geocoder, not gauge/sensor locations.

The code follows the [public Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/). Live access requires the explicit `--live` flag. Builds, validators and tests never call the provider.

## Files and repeatability

- Script: `scripts/geocode_international_stations.py`
- Versioned raw result cache: `data/reference/international_station_geocoding_cache-v1.json`
- Reviewed registry consumed by the public builder: `data/reference/international_station_geocoding.csv`
- Machine-readable run summary: `data/reference/international_station_geocoding_report.json`
- Offline test fixture: `tests/fixtures/international/geocoding/nominatim_results.json`

Safe offline reconstruction from the committed cache:

```text
python -m scripts.geocode_international_stations \
  --report data/reference/international_station_geocoding_report.json
```

Explicit live/resume mode (not a normal build command):

```text
python -m scripts.geocode_international_stations \
  --live \
  --throttle-seconds 1.1 \
  --report data/reference/international_station_geocoding_report.json
```

Cached query keys are never requested again. Rows already marked `accepted` or `rejected` are not replaced unless `--overwrite-reviewed` is explicitly supplied. Official station coordinates are outside the 75-row geocoding registry and the public builder refuses to overwrite them.

## Query and acceptance policy

The query uses the audited official local name, ISO 3166-1 alpha-2 country constraint and country name. A canonical Latin name is used when the local label is Cyrillic and the source already supplies the audited Latin form. Only documented technical suffixes such as upper/lower level or gauge/automatic/manual qualifiers are removed from the query; source IDs and both station names remain unchanged.

Six query-only clarifications were recorded for known locality spellings or administrative context: Kozloduy, Novo Selo (Vidin), Kachlet (Passau), Batina (Osijek-Baranja), Doborgaz (Győr-Moson-Sopron) and Radvaň nad Dunajom. They do not change public names.

A result is accepted only if it has finite EPSG:4326 coordinates, matches the constrained country, falls inside conservative country and Danube-sector validation envelopes, represents an inhabited locality, has a strong direct-name match, and has no competing inhabited-place result of comparable strength. Administrative boundaries are not preferred over an inhabited-place object. The envelopes reject clearly unrelated results; they are not Danube geometry and are never used for distance calculations.

`medium` means an accepted locality-level position. `low` and `unresolved` always require review and are excluded from GeoJSON. Exact coordinates from official station payloads remain `high` and `official_station_coordinate`.

## Review-required stations

| Station ID | Result | Reason |
|---|---|---|
| `bg-bajkal-automatic` | low | OSM label `Baikal` differs from audited `Bajkal`; not accepted without review |
| `bg-novo-selo-automatic` | low | locality match score below acceptance threshold |
| `bg-novo-selo-manual` | low | same locality candidate as the automatic station; still below threshold |
| `de-560cf185-0052-4e40-832b-7792b52dd343` | unresolved | no acceptable inhabited-locality result for Kachlet Wehr UP |
| `hr-5170` | unresolved | no acceptable Batina result in the relevant Croatian sector |
| `hu-442708` | unresolved | no acceptable inhabited-locality result for Doborgaz |
| `hu-442532` | unresolved | result describes the Kvassay lock/structure, not an accepted locality |
| `sk-5128` | unresolved | result describes a quarry/information object, not an accepted locality |

No station remains ambiguous between two accepted inhabited-place candidates after deterministic validation. The eight rows above are nevertheless review-required and stay off the map. Historical intermediate responses, including ambiguous administrative/place pairs, remain byte-for-byte in the versioned cache.

## Public and UI rules

The public station contract exposes `latitude`, `longitude`, `coordinate_method`, `coordinate_source`, `coordinate_provider`, `coordinate_confidence`, `coordinate_review_status` and `is_exact_station_location`. GeoJSON includes accepted official and approximate positions; unresolved/review-required stations remain in `unmapped_stations.json`.

Approximate positions use a diamond marker and an explicit RO/EN warning. Exact official positions use a circle. Same-coordinate manual/automatic stations share an aggregate marker whose popup lists individual station buttons; no random coordinate offset is generated. Approximate positions are excluded from distance, spatial precision, river-kilometre inference and location-based ordering.
