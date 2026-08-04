# Dicționarul datelor

## `stations.csv`

| Câmp | Tip | Descriere |
|---|---|---|
| `station_id` | UUID | Cheie stabilă din `uuid/value`. |
| `station_nid` | text | ID CMS secundar din `nid/value`. |
| `source_name` | text | Numele exact din XML. |
| `display_name` | text | Nume de afișare configurabil; nu este cheie. |
| `slug` | text | Nume sigur pentru URL/fișiere. |
| `river_km` | număr | Poziția fluvială normalizată. |
| `latitude`, `longitude` | grade zecimale | Coordonate WGS84. |
| `path_alias` | text | Alias Drupal păstrat tehnic. |
| `first_seen_at`, `last_seen_at` | ISO 8601 UTC | Intervalul observării stației. |
| `active` | boolean | Prezentă în ultima captură validă. |

## `observations.csv`

Cheie: `station_id + measurement_datetime`.

Valorile `river_km_raw`, `level_raw`, `variation_raw`, `temperature_raw` și `measurement_datetime_raw` păstrează textul sursă. Perechile normalizate sunt `river_km`, `level_cm`, `variation_cm_24h`, `water_temperature_c`, `measurement_datetime` și `measurement_date`. `record_hash` este hashul conținutului semantic. `first_seen_at`/`last_seen_at` păstrează trasabilitatea, iar `quality_flag` descrie validitatea.

## `forecasts.csv`

Cheie: `station_id + forecast_issue_datetime + lead_hours`. Fiecare ediție are cinci rânduri, pentru 24/48/72/96/120 h.

| Câmp | Descriere |
|---|---|
| `forecast_issue_datetime/date` | Momentul/data ediției XML. |
| `target_datetime/date` | Data emiterii plus `lead_hours`. |
| `forecast_level_raw` | Textul XML exact. |
| `forecast_level_cm` | Valoare normalizată sau gol dacă nu este disponibilă. |
| `forecast_available` | Disponibilitate stabilită prin XML–HTML. |
| `availability_source` | Regula care a decis disponibilitatea. |
| `html_value_raw` | Valoarea tabelului oficial. |
| `xml_html_match` | `true`, `false` sau gol pentru ambiguu. |
| `forecast_run_hash` | Hash stabil al ediției per stație. |

### Quality flags prognoză

- `valid`: XML și HTML numerice, egale;
- `missing_forecast_encoded_as_zero`: XML `0`, HTML gol;
- `xml_html_availability_mismatch`: XML nonzero, HTML gol;
- `xml_html_value_mismatch`: ambele numerice, diferite;
- `html_validation_unavailable`: XML nonzero, HTML neparseabil;
- `ambiguous_xml_zero_html_unavailable`: XML zero, HTML neparseabil;
- `unparseable_forecast`: valoare neinterpretabilă.

## `forecast_scores.csv`

Grupează după `station_id + lead_hours`. Conține `n_pairs`, eroarea semnată medie, MAE, RMSE, bias, procentele în ±5/±10/±20 cm, prima/ultima dată și maturitatea statistică.

## Arhiva flat raw

Coloanele folosesc calea logică completă, de exemplu `item/type/target_uuid`, `item/path/alias`, `item/feeds_item/hash` și `item/field_cota/value`. Astfel, leaf-urile omonime nu se confundă. CSV-ul este UTF-8 și comprimat gzip.


## Contract internațional beta 1.1

`data/public/international/` și oglinda `public/data/international/` publică registrul internațional separat de AFDJ. `stations.json` conține toate cele 101 stații, iar `stations.geojson` numai coordonatele acceptate. `unmapped_stations.json` conține rezultatele nerezolvate sau care necesită review.

Câmpurile de coordonate sunt:

- `latitude`, `longitude`: EPSG:4326 sau `null`;
- `coordinate_method`: `official_station_coordinate` ori `geocoded_locality`;
- `coordinate_source`: URL-ul sursei oficiale sau al interogării geocoderului;
- `coordinate_provider`: administrația oficială ori `OpenStreetMap Nominatim`;
- `coordinate_confidence`: `high`, `medium`, `low` sau `unresolved`;
- `coordinate_review_status`: `accepted`, `required` sau `rejected`;
- `is_exact_station_location`: `true` numai pentru coordonata oficială exactă a stației.

O poziție `geocoded_locality` este centrul aproximativ al localității și nu demonstrează amplasamentul mirei/senzorului. Nu se folosește pentru distanțe, ordine, precizie spațială sau inferarea kilometrului fluvial. Metoda completă și registrul review-ului sunt descrise în `INTERNATIONAL_STATION_GEOCODING.md`.