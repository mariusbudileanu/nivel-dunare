# International source implementation report

Seven adapters/source states share the canonical model for physical stations, observation streams, parameters, observations, forecasts, sources and locations. Fixture status/counts are: DE 18 stations/18 observations; AT 9/9 plus one fixture forecast; SK 13/26 plus 26 forecasts; HU 25/125; HR 3/6; BG 20/48 plus 30 diagnostic forecast candidates; RS 13/75 plus 32 demonstrated point forecasts. Fixture data are parser contracts and are never published.

The public `1.3-beta` snapshot and source policies are documented in `INTERNATIONAL_CONSOLIDATION_V2_REPORT.md`. `implementation_status`, live/operational source status and per-observation source quality are independent. Official values, including unusual or negative values, are retained; missing placeholders remain missing. A source-provided `provisional` label is preserved. Application numeric plausibility thresholds are not active.

`country_code` is ISO 3166-1 alpha-2. `station_name` is the application's deterministic ASCII international name and `station_name_local` preserves official source text. Official Latin/English text is preferred. Cyrillic fallback uses the documented project transliteration convention; it is not claimed as a formal ISO transliteration standard.
