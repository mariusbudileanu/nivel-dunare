# International beta pre-merge audit

Audit date: 2026-08-05
Branch: `feature/international-map-beta`
Pull request: `#2`
Public contract: `1.1-beta`

This audit covers the beta-publication branch before merge. It does not claim a GitHub Pages deployment. AFDJ collection, the Hetzner configuration, AIS, production schedules and Romanian canonical data are outside the change set.

## Requirement matrix

| # | Requirement | Result and evidence |
|---:|---|---|
| 1 | Beta publication and complete public contract | Complete. Nine documented JSON/GeoJSON files are mirrored byte-for-byte under `data/public/international/` and `public/data/international/`. |
| 2 | Public builder and validator | Complete. Dedicated deterministic builder and fail-closed validator cover counts, mirrors, references, policy, provenance and quality evidence. |
| 3 | International map integration | Complete in branch. Existing 23 AFDJ stations are combined in memory with 93 international points (26 exact official + 67 approximate), for 116 mapped station records; no Romanian station is duplicated. Six same-locality Bulgarian automatic/manual pairs use aggregate markers, so the 116 records render as 110 marker icons. |
| 4 | Coordinate provenance | Complete. 26 exact official coordinates and 67 accepted approximate locality positions are mapped; 8 review-required stations remain in `unmapped_stations.json`. |
| 5 | Country/source/status/type filters | Complete. Browser checks covered DE, SK, AT-source, suspect and manual-station filters. |
| 6 | Popups, cards, legend and statistics | Complete. Optional fields are omitted when absent; values, types, forecast availability, source/local/UTC/capture times, quality, status and official links are displayed where available. |
| 7 | Complete/partial/provisional/suspect/stale/suspended/unavailable | Complete. Source status and observation quality remain separate; all seven states have labels, symbols and distinct styles. |
| 8 | DE/AT/SK/HU/HR/BG/RS policy | Complete according to the documented beta policy. AT is explicitly test-source/partial; SK quality is observation-local; HR is stale/suspended; BG forecasts are excluded; RS is registry-only and makes no request. |
| 9 | Exclude suspect/stale from current statistics | Complete. The contract records 161 current-usable, 30 stale, 24 provisional and one current suspect observation. `latest.json` contains only usable current values. |
| 10 | Provenance and original times | Complete. Observations and forecasts retain source URL/provider, source hash, capture time, original supplied time, normalized date/time when demonstrated, timezone metadata and quality/status. |
| 11 | Complete RO/EN interface | Complete for versioned static and dynamic UI text. Literal translation calls and HTML translation attributes are automatically audited. |
| 12 | EN/RO beside Info | Complete. It is the immediately adjacent compact button. |
| 13 | Translate static and dynamic text | Complete for controls, filters, statistics, cards, warnings, chart labels/exports, table, downloads, dialogs and map popup content. Proper station/authority names and units are preserved. |
| 14 | Language persistence | Complete. Browser navigation without a language parameter retained the chosen English interface. |
| 15 | `?lang=ro` / `?lang=en` | Complete. Browser checks confirmed URL language priority. |
| 16 | `<html lang>` | Complete and checked in both languages. |
| 17 | Rerender open/dynamic components | Complete. Filters/cards/table/downloads/charts/station selector and open map popup rerender; the popup action is rebound after replacement. |
| 18 | `ro-RO` / `en-GB` formatting | Complete. Browser evidence includes `1.895` and `04.08.2026` in RO versus `1,895` and `04/08/2026` in EN. Original data is unchanged. |
| 19 | Mobile and keyboard accessibility | Responsive breakpoint, compact header behavior, focus-visible styling, semantic buttons, translated ARIA labels and keyboard focus are covered. Final device-level public verification remains a post-deploy check. |
| 20 | Future Hetzner migration | Complete as documentation only. It covers isolated commands, credentials, locking, limits, retention, logs, fail-closed operation and disabled sources. No Hetzner configuration was changed. |
| 21 | Final reports and remaining issues | Complete in this report, `INTERNATIONAL_BETA_PUBLICATION_REPORT.md` and `INTERNATIONAL_BETA_OPEN_ISSUES.md`. |

## Browser evidence before merge

The branch was served locally and exercised in the in-app browser. This was not a Pages deployment.

- application startup: operational (`Date actualizate`);
- mapped station records: 116 = 23 AFDJ + 93 international;
- rendered marker icons: 110, because six same-locality Bulgarian automatic/manual pairs are represented by aggregate markers;
- list-only international stations: 8;
- Leaflet `.leaflet-pane` and `.leaflet-tile`: computed `position: absolute`;
- basemap: nine complete tiles covered the map viewport;
- country DE: 17 markers and one list card;
- country SK: 12 accepted approximate locality markers and one unresolved list-only card; the source remains `partial`;
- suspect filter: one Iža card with the localized implausible-temperature warning;
- viadonau source: nine markers;
- manual type: seven accepted approximate BG markers and one unresolved list-only card; no coordinate is invented;
- Austrian popup: official source, partial status, station type, river, level, variation, 119 available forecasts, source local time, timezone, UTC, capture time, observation quality and test-source warning;
- open Austrian popup: translated from RO to EN without closing; its `Open analysis` action remained functional;
- no rendered `null` or `undefined` text;
- language persistence and URL priority: verified through navigation;
- keyboard focus: language button received a visible outline.

## Contract totals

| Measure | Count |
|---|---:|
| audited international stations | 101 |
| mapped international stations | 93 |
| exact official coordinates | 26 |
| accepted approximate positions | 67 |
| list-only international stations | 8 |
| existing AFDJ stations | 23 |
| total mapped station records | 116 |
| rendered marker icons after six aggregations | 110 |
| stations with a usable current value | 83 |
| published observations | 192 |
| current-usable observations / latest records | 161 / 161 |
| stale observations | 30 |
| provisional observations | 24 |
| current suspect observations | 1 |
| published forecasts | 434 |
| quality issues | 25 |
| complete / partial / suspended sources | 2 / 3 / 2 |

## Remaining limitations

- Only DE and AT have verified official coordinates suitable for the international map.
- AT requires a permanent `DORIS_PARTNER_KEY` before production scheduling.
- SK remains partial. Twelve stations are mapped with accepted approximate locality markers and only `sk-5128` remains list-only; suspect temperatures remain quality evidence, while valid levels and forecasts stay usable.
- HU has date-only observations and no normalized numeric forecast.
- HR remains stale/suspended and excluded from current metrics.
- BG institutional IDs and forecast semantics remain unproven; forecasts are not publicly normalized.
- RS remains suspended after TLS-chain validation failure; no request or TLS bypass is performed.
- International refresh is manual; no production timer or service is added.
- Public GitHub Pages behavior, cache state and device-level mobile layout cannot be certified until merge and an explicitly authorized deployment.

## Protected scope

The branch diff must not include the AFDJ workflow, Hetzner runner/service/timer, AIS, Romanian canonical data, Pages deployment workflow or `artifacts/`. Secret scans must find no persisted DoRIS key and no `viadonau_partner_key=` value.
