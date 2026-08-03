# Arhitectură

## Fluxul datelor

```text
AFDJ XML + HTML
↓
download și arhivare
↓
flatten raw + validare schemă
↓
observations + forecasts long
↓
scoring
↓
JSON/CSV/GeoJSON public
↓
GitHub Pages
```

`scripts/afdj_core.py` conține logica reutilizabilă. Scripturile CLI sunt adaptoare subțiri și pot fi lansate prin `python -m scripts.<nume>`.

## Zone de stocare

- `data/archive/raw_xml`: bytes XML originali, comprimați; capturile cu hash identic nu se dublează după o rulare reușită.
- `data/archive/flat_raw`: un rând per `item`, o coloană per leaf path complet. Atributele folosesc notația `item@key`.
- `data/archive/diagnostics`: HTML comprimat numai când parsarea sau validarea semantică ridică probleme.
- `data/canonical`: tabele istorice idempotente și corecții explicite.
- `data/schema`: schema curentă, tag counts și istoricul schimbărilor.
- `data/public`: contractul public pentru frontend și descărcări.
- `public`: aplicația statică publicată.

## Identitate și idempotency

`uuid/value` este `station_id`. Cheia observației este `station_id + measurement_datetime`; cheia prognozei este `station_id + forecast_issue_datetime + lead_hours`. O modificare ulterioară a aceleiași chei actualizează rândul și scrie diferența în `corrections.csv`.

## Frontend

Pagina inițială încarcă numai `status.json`, `latest.geojson` și `downloads.json`. Istoricul unei stații se încarcă lazy și este cache-uit în memorie. Toate căile frontend sunt relative pentru publicarea într-un subpath GitHub Pages.

Leaflet 1.9.4 și Plotly 2.35.2 sunt pin-uite. Basemapul principal este CARTO Light; la erori de tile se trece la OpenStreetMap Standard.

## Blocarea publicării datelor

Captura brută este păstrată chiar dacă validarea eșuează. Actualizarea canonică este blocată la XML invalid, root greșit, lipsa `item`, câmp critic absent/neparseabil, coordonate invalide, UUID duplicat sau scădere a stațiilor peste 20% față de ultima rulare validă. Tagurile noi necritice sunt păstrate și raportate fără blocare.

