# International Danube beta publication report

## Scope and evidence

This beta publication is an explicit promotion step after the international adapters:

```text
validated candidate data -> source publication policy -> international public files -> frontend
```

It does not alter the AFDJ collection, Hetzner schedule, Romanian canonical history, AIS service or the manual-only AFDJ workflow.

PR #1 (`feature/international-danube-sources`) was revalidated with 78 tests, the repository validator and the station-audit builder, then merged as `5df2b72264a1a7cf7eac3b26a7d41b8f78aa18e3`.

The manual `Test international Danube sources` workflow was executed after that merge:

| Mode | Run ID | Result | Artifact retained locally |
|---|---:|---|---|
| fixtures / all | `30929839808` | success | `_diagnostics/international/github-fixtures-30929839808/` |
| live / all | `30929930388` | success | `_diagnostics/international/github-live-30929930388/` |

The live aggregate contained no failed source job, but adapter success is not treated as equivalent to complete publication status.

## Live evidence and publication policy

| Country | Audited stations | Live observations | Public status | Public handling |
|---|---:|---:|---|---|
| DE | 18 | 25 | complete | observations published; 17 official coordinate pairs mapped |
| AT | 9 | 9 | partial | observations and 238 forecasts published as a test-source beta; 9 official coordinate pairs mapped |
| SK | 13 | 25 | partial | 24 usable observations plus forecasts remain usable; one suspect temperature is retained but excluded from `latest` |
| HU | 25 | 57 | complete for observations | date-only observations preserved without an invented time/timezone |
| HR | 3 | 30 historical | stale / suspended | values retained as stale history, excluded from current values and statistics |
| BG | 20 | 46 | partial | current validated observations published; 30 raw candidate forecasts are not promoted |
| RS | 13 audited | 0 | suspended | audit metadata only; no request, no TLS bypass, no observations or forecasts |

The live SHMU capture contained a suspect Iža water temperature of 45.3 °C. The validated earlier capture containing the authentic 46.2 °C Iža value is also retained in `quality_issues.json` with its original observation, source hash and capture time. Neither suspect value is eligible for `latest` temperature. Valid Slovak water levels and forecasts are unaffected.

## Public contract

Contract version `1.1-beta` is declared in `status.json`. The following files are byte-identical under both `data/public/international/` and `public/data/international/`:

- `stations.json`
- `observations.json`
- `latest.json`
- `forecasts.json`
- `sources.json`
- `status.json`
- `stations.geojson`
- `unmapped_stations.json`
- `quality_issues.json`

The promoted live dataset contains:

| Measure | Count |
|---|---:|
| audited stations | 101 |
| exact official station coordinates | 26 |
| accepted approximate locality positions | 67 |
| total international GeoJSON points | 93 |
| stations listed without accepted coordinates | 8 |
| stations with a current valid value | 83 |
| published observations, including labelled stale/suspect evidence | 192 |
| current usable observations | 161 |
| stale observations excluded from current values | 30 |
| provisional observations | 24 |
| latest valid parameter records | 161 |
| published forecasts | 434 |
| current suspect observations | 1 |
| quality issues | 25 |
| complete / partial / suspended sources | 2 / 3 / 2 |

Every published observation retains station/source identifiers, source URL, source-file SHA-256, capture time, observation time as supplied, quality and source status. Sensitive DoRIS query parameters are removed. GeoJSON contains only DE and AT official high-confidence coordinates.

## Frontend and languages

The existing Romanian AFDJ GeoJSON is loaded unchanged and combined in memory with 93 international GeoJSON features: 26 exact official station coordinates and 67 accepted locality-level positions. Eight review-required stations remain in a separate list. Filters cover country, source, status, station type and coordinate type. Official circles and approximate diamonds are distinguished by shape and text; approximate popups carry an explicit RO/EN precision warning. Same-locality overlaps use a shared aggregate popup with individual station buttons. Full method, provenance and limitations are documented in `INTERNATIONAL_STATION_GEOCODING.md`.

The translation mechanism is centralized in `public/assets/js/i18n.js`. It provides matching Romanian and English catalogues, defaults to Romanian, applies URL language before `localStorage`, updates `<html lang>`, preserves the choice, formats with `ro-RO` or `en-GB`, and notifies map, cards, tables, charts, dialogs and filters after a language change. The compact keyboard-accessible EN/RO button is next to Info.

## Validation

The full repository suite currently contains **107 passing tests**. Automated checks cover the builder round trip, mirrored files, source policy, AFDJ/international isolation, suspect/stale/suspended handling, BG forecast exclusion, RS audit-only handling, coordinate partition, references, duplicates, provenance, secret scanning, translation-key parity, language priority/persistence, accessible language control, dynamic translated components, international resource loading and responsive CSS.

The repository smoke test serves the site locally and fetches the existing AFDJ resources, representative Romanian station history, all nine international files and both `?lang=ro` and `?lang=en` entry URLs. A pre-merge local-browser audit verified the branch frontend without GitHub Pages: 110 rendered marker icons representing 23 AFDJ and 93 international stations (six same-locality aggregate markers), 8 list-only stations, fully loaded basemap tiles covering the map, absolute Leaflet pane/tile positioning, country/source/status/type/coordinate filters, the structured Iža warning, an Austrian popup with 119 forecasts and complete provenance times, an already-open popup translated RO→EN, URL priority, language persistence by navigation, and visible keyboard focus. The static mobile contract and responsive breakpoint are tested; final public/mobile deployment evidence remains intentionally deferred until an explicit merge/deploy authorization.
