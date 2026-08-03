# Nivelul Dunării

Aplicație web statică pentru monitorizarea zilnică a cotelor și prognozelor hidrologice ale Dunării. Datele provin din sursa publică [AFDJ](https://www.afdj.ro/ro/cotele-dunarii), sunt arhivate cu trasabilitate completă și sunt publicate ca dashboard interactiv, CSV, JSON și GeoJSON.

## Funcționalități

- hartă Leaflet cu toate stațiile și tendința zilnică;
- grafice Plotly pentru nivel, prognoză, variație și temperatură;
- explorarea edițiilor istorice de prognoză și evaluarea lor față de observații;
- comparație metodologic corectă între maximum patru stații;
- intervale 7/30/90/365 zile, tot istoricul și interval personalizat;
- export CSV al selecției și PNG high-resolution pentru fiecare grafic;
- tabel accesibil ca alternativă la hartă;
- pipeline idempotent cu XML brut `.xml.gz`, flat raw complet și catalog de schemă;
- validare semantică XML–HTML, inclusiv regula pentru zero-urile ambigue;
- două actualizări programate zilnic și deploy automat GitHub Pages.

## Arhitectură

```text
AFDJ XML + HTML
       ↓
download, hash și arhivare brută
       ↓
flatten raw + validare/catălog schemă
       ↓
stations + observations + forecasts (long)
       ↓
scoruri prognoză + JSON/CSV/GeoJSON per stație
       ↓
dashboard static GitHub Pages
```

Detalii: [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) și [FORECAST_METHODOLOGY.md](docs/FORECAST_METHODOLOGY.md).

## Rulare locală

Cerință: Python 3.12+.

```powershell
python -m scripts.ingest_afdj
python -m scripts.calculate_forecast_scores
python -m scripts.build_public_data
python -m scripts.validate_repository
python -m unittest discover -s tests -v
python -m scripts.smoke_test_site
python -m scripts.serve_local --port 8000
```

Aplicația este disponibilă apoi la `http://127.0.0.1:8000/`.

Pentru o primă rulare reproductibilă din captura auditului:

```powershell
python -m scripts.ingest_afdj --xml-file _audit_source/raw/afdj_latest_raw.xml --html-file _audit_source/raw/afdj_cotele_dunarii_page.html --source audit-import
```

## Date și descărcări

- `data/public/latest.csv` — situația curentă;
- `data/public/observations.csv` — observații istorice;
- `data/public/forecasts.csv` — prognoze în format lung;
- `data/public/stations.csv` — registrul stațiilor;
- `data/public/latest.geojson` — valori curente geospațiale;
- `data/public/station/` — fișiere lazy per stație;
- `data/archive/flat_raw/` — export tehnic zilnic cu toate leaf path-urile XML.

Datele interne Drupal sunt păstrate pentru audit, dar nu sunt încărcate în interfața principală.

## Automatizare

Workflow-ul `update-data.yml` rulează zilnic la 04:17 și 07:23 UTC. A doua fereastră este o rulare de siguranță; ingestia nu dublează observațiile sau edițiile de prognoză. Actualizarea publică poate apărea după ora publicării la sursă.

`deploy-pages.yml` publică exclusiv folderul `public`, după sincronizarea `data/public` în `public/data`.

Instrucțiuni operaționale complete: [OPERATIONS.md](docs/OPERATIONS.md).

## Testare

Suita acoperă parserul XML real, toate căile critice, normalizarea, cele cinci cazuri de disponibilitate, idempotency, evoluția schemei, scoringul și exporturile publice. Smoke testul pornește un server efemer și verifică pagina, resursele, statusul, GeoJSON și fișierele lazy pentru Baziaș, Giurgiu și Sulina.

## Limitări

- istoricul începe la prima captură reală arhivată; nu sunt inventate date anterioare;
- scorurile prognozelor apar numai după ce există observații la datele-țintă;
- valorile prognozelor pot diferi temporar între XML și tabelul HTML; ambele sunt păstrate și semnalate;
- cotele absolute au zerouri de referință locale și nu sunt comparabile direct între stații;
- aplicația depinde de disponibilitatea sursei AFDJ și a serviciilor CDN pentru Leaflet/Plotly.

## Licență și disclaimer

Codul este disponibil sub [licența MIT](LICENSE).

Datele provin din sursa publică AFDJ, iar prognozele sunt cele publicate prin sursa oficială. Aplicația este informativă și nu înlocuiește avizele oficiale, informațiile de navigație sau deciziile autorităților. Momentul afișării poate fi ulterior publicării la sursă. Harta folosește date © OpenStreetMap contributors și stilul CARTO, cu atribuirea afișată în interfață.

