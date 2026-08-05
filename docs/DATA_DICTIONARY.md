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


## Contract internațional beta `1.3-beta`

`data/public/international/` și oglinda byte-identică `public/data/international/` sunt separate de datele AFDJ.

- `stations.json`: 101 înregistrări de flux-stație și metadatele stației fizice/localizării;
- `streams.json`: identitatea, tipul și frecvența celor 101 fluxuri;
- `stations.geojson`: 93 features, câte unul pentru fiecare amplasament fizic cartografiat, cu fluxurile agregate în properties;
- `observations.json`: istoricul observațiilor și proveniența sursei;
- `latest.json`: ultima observație tehnic utilizabilă per flux și parametru; valorile nu sunt excluse prin praguri numerice locale;
- `forecasts.json`: numai prognoze cu parametru, unitate, valoare și țintă demonstrate;
- `sources.json`: dimensiuni operaționale separate și mesaje RO/EN;
- `quality_issues.json`: probleme active tehnice/de sursă și constatări istorice inactive;
- `unmapped_stations.json`: gol în versiunea curentă.

Identitatea separă `station_id`, `physical_station_id`, `source_station_id`, `source_stream_id`, `source_stream_type` și `is_primary_stream`. Observațiile păstrează data/ora originală, precizia, daypart/window, fusul/offsetul brut, momentul capturii, valoarea brută, unitatea, calitatea sursei și SHA-256. O dată fără oră rămâne dată; un placeholder lipsă nu devine zero.

Metodele de coordonate sunt `official_station_coordinate`, `manually_verified_station_coordinate`, `geocoded_locality` și `unresolved`. Câmpurile includ sursa/providerul, încrederea, review-ul, exactitatea, data verificării și note. Pozițiile Nominatim sunt centre aproximative de localitate și nu sunt folosite pentru distanțe, ordine sau kilometru fluvial.

`sources.json` separă `access_status`, `source_status`, `automation_status`, `freshness_status`, `validation_status` și `coordinate_status`, apoi păstrează momentele de încercare/succes/captură/observație/LKG, frecvențele, eșecurile și politica bilingvă.
