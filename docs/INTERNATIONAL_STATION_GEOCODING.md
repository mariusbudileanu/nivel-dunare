# International station coordinates

Contract `1.3-beta` maps all 101 international station streams at 93 physical locations.

| Coordinate method | Streams | Meaning |
|---|---:|---|
| `official_station_coordinate` | 50 | Exact institutional/RIS/PEGELONLINE coordinate. |
| `manually_verified_station_coordinate` | 15 | Exact coordinate verified by the project owner; not labelled institutional. |
| `geocoded_locality` | 36 | Approximate inhabited-locality centre. |
| `unresolved` | 0 | No accepted coordinate. |

Priority is official, manually verified exact, accepted locality, unresolved. Official coordinates are never overwritten by geocoding. The 75-row geocoding registry remains immutable audit history; 36 rows are active after higher-priority replacements.

Kachlet retains original EPSG:25832 coordinates and a pyproj 3.7.2 transformation to WGS84. HR and BG coordinates come from the normalized RIS registry. Exact manual coordinates cover SK 1, HU 2 and RS 12. Approximate rows cover SK 12, HU 23 and RS 1.

Public fields are `latitude`, `longitude`, `coordinate_method`, `coordinate_source`, `coordinate_provider`, `coordinate_confidence`, `coordinate_review_status`, `is_exact_station_location`, `coordinate_verified_at`, and `coordinate_notes`. Approximate positions are never used for distance, station ordering or river-kilometre inference.

The portal distinguishes official circles, manually verified double outlines and approximate diamonds. Shared physical/co-located stations use one aggregate marker without random offsets. Approximate data are attributed as `© OpenStreetMap contributors, ODbL` in the portal and documentation.

Validate with:

```text
python -m scripts.geocode_international_stations --validate-only
python -m scripts.validate_international_public_data
```
