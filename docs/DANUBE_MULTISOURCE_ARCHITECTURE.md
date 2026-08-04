# Arhitectură multi-sursă propusă

Acest document descrie tranziția viitoare. Auditul nu schimbă pipeline-ul AFDJ, outputurile publice, frontendul, Pages, systemd, Hetzner sau AIS.

## Etapa A — continuitatea AFDJ existentă

Pipeline-ul AFDJ actual rămâne separat și rulează sigur pe Hetzner, fără refactorizare disruptivă. Are cinci rulări zilnice la 07:00, 10:00, 12:00, 18:00 și 21:00 `Europe/Bucharest`, produce aceleași fișiere și aceleași semantici ca acum și nu depinde de finalizarea adaptoarelor internaționale. Automatizarea operațională AFDJ are prioritate imediată.

Etapa A păstrează validarea XML–HTML, regulile pentru zero ambiguu, whitelist-ul de fișiere, publicarea atomică și izolarea față de proiectul AIS. Acest audit nu instalează și nu modifică timerul ori serviciul.

## Etapa B — introducerea graduală a adaptoarelor

Se introduce `SourceAdapter` treptat. Primul adaptor nou este PEGELONLINE DE; urmează APPD BG cu parser conservator și apoi DoRIS AT după partner key și clarificarea reutilizării. AFDJ migrează în adaptor numai după un test de paritate care demonstrează aceleași stații, valori, prognoze, fișiere și reguli de calitate. Frontendul multi-provider vine ulterior.

Structura candidată:

```text
scripts/sources/
  base.py
  pegelonline_de.py
  appd_bg.py
  viadonau_at.py
  shmu_sk.py
  hidmet_rs.py
  hydroinfo_hu.py
  vodniputovi_hr.py
  afdj_ro.py
scripts/ingest_danube_sources.py
```

`SourceAdapter` expune `discover()`, `fetch(capture_context)`, `parse(raw_artifact)`, `validate(records)`, `normalize(records)` și `health()`. Rezultatul include rolurile `operator_provider_id`, `source_provider_id`, `captured_via_provider_id`, artefacte, hashuri, observații/prognoze tipizate, avertismente, schema fingerprint și starea `success|partial|stale|blocked|failed`.

## Flux și izolare

1. Orchestratorul folosește lock per furnizor.
2. Fiecare adaptor arhivează atomic corpul raw și SHA-256 sub provider/data/run.
3. Validarea schemei precede normalizarea; schema drift blochează doar sursa afectată.
4. Normalizarea scrie în staging versionat; validarea inter-sursă nu schimbă valori primare.
5. Publicarea compune numai snapshoturi acceptate și poate păstra ultimul snapshot bun ca `stale`.
6. Fiecare rând păstrează rolurile provider, run, hash și regula de conversie; corecțiile sunt append-only.

Pentru APPD, selectorii trebuie fixați pe tabelele semantice și verificați cu fixture-uri. Sunt distincte: tabelul principal (8 stații), tabelul automat (12), prognozele (5 stații/6 zile) și arhiva PDF (6 stații istorice). Celula goală este `null`; iconurile automate devin categorii controlate fără a inventa o valoare numerică. Lipsa ID-ului instituțional, a unității de forecast și a datei ediției forecast menține adaptorul `partial`.

## Politici operaționale

- Timeouturi explicite; retry limitat numai pentru timeout/5xx tranzitorii; fără retry automat la 401/403/429.
- User-Agent transparent, rate limit per host, concurrency implicit 1.
- Idempotency prin hash corp și chei provider+record; același hash nu produce publicare nouă.
- Alerte pentru status HTTP, schema drift, zero stații, scădere abruptă, timestamp stale și regresia ediției.
- Rollback prin manifest către ultimul snapshot valid, fără rescrierea arhivei.
- Potrivirile transfrontaliere sunt candidați cu `human_review_required`; numele nu unește stații.

## Git, Hetzner și independență

Colectarea AFDJ continuă pe Hetzner; build/deploy Pages rămâne pe GitHub. O automatizare viitoare folosește cheie dedicată, `known_hosts`, `git pull --ff-only`, staging și whitelist explicit; niciodată `git add .`, force push sau reset hard. AIS folosește alt director, mediu, user/cheie și lock și rămâne neatins.