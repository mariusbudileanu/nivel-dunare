# Operațiuni

## Actualizare locală completă

```powershell
python -m scripts.ingest_afdj
python -m scripts.calculate_forecast_scores
python -m scripts.build_public_data
python -m scripts.validate_repository
python -m unittest discover -s tests -v
python -m scripts.smoke_test_site
```

## Server local

```powershell
python -m scripts.serve_local --port 8000
```

Deschide `http://127.0.0.1:8000/`. Nu deschide direct `index.html`, deoarece modulele JavaScript și fetch-ul datelor necesită HTTP.

## GitHub Actions

În fila Actions, rulează manual **Actualizare date AFDJ** prin `workflow_dispatch`. Programul implicit este 04:17 și 07:23 UTC; poate fi schimbat în `.github/workflows/update-data.yml`. Întârzierea față de publicarea oficială este posibilă.

## Interpretarea logurilor

`data/canonical/ingestion_runs.csv` înregistrează fiecare încercare: hashuri, URL final, coduri HTTP, număr de stații, rezultat HTML, zero-uri ambigue, mismatchuri și mesaj. `status=failed` înseamnă că arhiva brută a fost păstrată, dar tabelele publice nu au fost actualizate.

## Refacerea datelor publice

```powershell
python -m scripts.calculate_forecast_scores
python -m scripts.build_public_data
python -m scripts.validate_repository
```

Aceste comenzi nu descarcă sursa și pot reconstrui `data/public` și `public/data` din canonice.

## Modificare de schemă

1. verifică `data/schema/schema_changes.csv`;
2. inspectează `current_schema.json` și flat raw;
3. un tag nou necritic este deja păstrat și nu blochează;
4. un câmp critic lipsă blochează canonicele;
5. actualizează parserul și testele înainte de reluarea publicării.

## Depanare

- HTTP/Content-Type: verifică sursa și `ingestion_runs.csv`;
- HTML neparseabil sau mismatch: inspectează `data/archive/diagnostics`;
- stații cu coordonate invalide: corectează numai parserul, nu datele brute;
- 404 în site: rulează `build_public_data` și `smoke_test_site`;
- Pages: verifică permisiunile `pages: write` și `id-token: write` și setarea Pages pe GitHub Actions.

