# Model canonic propus pentru Dunăre

Acesta este un contract viitor; modelul existent și outputurile AFDJ nu sunt modificate în această etapă. Regula de bază este păstrarea valorii, unității, referinței și provenienței sursei înaintea oricărei conversii.

## Rolurile furnizorilor

Cele trei roluri nu sunt interschimbabile:

- `operator_provider_id`: instituția sau operatorul stației fizice;
- `source_provider_id`: instituția responsabilă pentru valoarea primară;
- `captured_via_provider_id`: portalul ori agregatorul prin care valoarea a fost capturată.

Pentru o valoare AFDJ capturată direct, toate rolurile pot indica AFDJ. Pentru un rând românesc republicat de Hydroinfo, operatorul și sursa primară rămân instituția română dacă sunt demonstrate, iar `captured_via_provider_id=hydroinfo_hu`. Un agregator nu devine automat titularul valorii.

## Entități

- `providers`: instituție, clasă, termeni, contact și stare operațională.
- `stations`: identitatea furnizorului și a stației, fără deducerea identității globale din nume.
- `station_aliases`: nume istorice, alfabet original, transliterări și limbi.
- `station_metadata_versions`: versiuni temporale pentru coordonate, kilometru fluvial, gauge zero, datum și statut.
- `observations`: fapte hidrologice în formă lungă, parametrizate.
- `forecasts`: ediție, țintă/lead, parametru și interval min/central/max.
- `discharges`: numai vedere/proiecție a observațiilor cu `parameter=discharge`, nu a doua copie canonică.
- `quality_flags`, `ingestion_runs`, `source_files`, `corrections`, `cross_source_matches`.

## `stations` și versionarea metadatelor

`global_station_id`, `operator_provider_id`, `source_provider_id`, `captured_via_provider_id`, `country_code`, `source_station_id`, `source_station_uuid`, `station_name_original`, `river_name`, `source_url`, `metadata_url`.

Cheia naturală este `(source_provider_id, source_station_id/source_station_uuid)`. Dacă sursa nu publică niciun identificator, adaptorul rămâne `partial`: poate folosi doar o cheie de audit documentată, precum provider + tip + nume exact + km, dar nu inventează un ID canonic.

`station_metadata_versions` conține `global_station_id`, `valid_from`, `valid_to`, `latitude`, `longitude`, `river_km`, `gauge_zero_value`, `gauge_zero_unit`, `vertical_datum`, `station_status`, `source_file_sha256`. Orice modificare închide versiunea anterioară și adaugă una nouă. Gauge zero, datum, coordonatele, km și statutul nu sunt suprascrise în loc.

## `observations`

`global_station_id`, cele trei roluri de provider, `parameter`, `measurement_datetime_utc`, `measurement_datetime_local` sau `measurement_date`, `source_timezone`, `value`, `unit`, `reference_type`, `variation_window_hours`, `variation_value`, `water_temperature_c`, `source_quality_code`, `canonical_quality_flag`, `capture_datetime_utc`, `source_file_sha256`, `source_record_id`.

`parameter` este controlat, cel puțin `water_level`, `discharge`, `water_temperature`. Nivelul și debitul de la același moment sunt rânduri parametrizate distincte, legate de același artefact și timp. Debitul se stochează canonic o singură dată în `observations` cu `parameter=discharge`; `discharges` este numai o vedere compatibilă și nu poate fi sursă separată de adevăr.

Cheia idempotentă recomandată este `(source_provider_id, source_record_id)` sau, în lipsa ei, un hash stabil din stație, parametru, timp și câmpurile raw. Lipsa sau celula goală devine `null`, niciodată zero implicit. Valorile negative ale nivelului local rămân valide.

## `forecasts`

`global_station_id`, cele trei roluri de provider, `forecast_parameter`, `forecast_issue_datetime_utc/local` sau `forecast_issue_date`, `target_datetime_utc/local` sau `target_date`, `lead_hours`, `forecast_value`, `forecast_unit`, `forecast_min_value`, `forecast_max_value`, `reference_type`, `source_quality_code`, `canonical_quality_flag`, `capture_datetime_utc`, `source_file_sha256`.

`forecast_parameter` are valori controlate `water_level` și `discharge`. Prognoza de nivel nu se amestecă cu prognoza de debit. Dacă pagina nu etichetează parametrul ori unitatea, valorile raw pot fi auditate, dar adaptorul rămâne `partial` și nu publică o interpretare inventată. O ediție nouă nu suprascrie edițiile vechi.

## Contracte minime ale adaptoarelor

Un câmp este `required=yes` numai când sursa sau o constantă de adaptor justificată îl poate furniza. Altfel adaptorul este `partial`, iar lipsa este documentată.

| Entitate | Câmpuri minime |
|---|---|
| `stations` | `provider_id`, `source_station_id` sau `source_station_uuid`, `station_name_original`, `country_code`, `river_name` |
| `observations` | `provider_id`, identificator stație, `measurement_datetime` sau `measurement_date`, `level_value`, `level_unit`, `source_file_sha256` |
| `forecasts` | `provider_id`, identificator stație, data/ora ediției unde există, `target_datetime` sau `lead_hours`, `forecast_value`, `forecast_unit`, `source_file_sha256` |

Data ediției de prognoză poate lipsi numai cu statut `partial`; ținta sau lead-ul, valoarea, unitatea și identificatorul nu se inventează. Pentru APPD forecast, identificatorul, data ediției, parametrul explicit și unitatea nu sunt demonstrate, deci parserul candidat nu poate deveni adaptor complet.

## Referințe hidrometrice

Nivelul local este raportat la zero-ul mirei și este comparabil temporal numai cât timp versiunea gauge zero este valabilă. Nivelul absolut cere gauge zero și datum explicit. Adâncimea navigabilă nu este nivel la miră. Debitul (`m³/s`) nu se derivă din nivel fără curbă de cheie și interval de valabilitate demonstrate.

Interfața nu trebuie să compare cote locale brute între stații fără referințe omogene. Graficele multi-stație folosesc nivel absolut omogen, anomalii/variații sau un avertisment explicit.

## Potriviri transfrontaliere

`cross_source_matches` păstrează `left_station_id`, `right_station_id`, dovezile, `match_confidence`, `match_reason`, `human_review_required`, revizorul și momentul deciziei. Numele singur produce cel mult un candidat `low`, niciodată o deduplicare fizică. Coordonatele, km, identificatorul ori metadatele instituționale trebuie să susțină o decizie umană.

Rândurile AFDJ și cele românești republicate de Hydroinfo rămân identități distincte. Suprapunerea de nume este doar semnal de revizuire; lipsa coordonatelor/km în rândul Hydroinfo împiedică unirea automată.

## Calitate, proveniență și evoluție

`source_quality_code` rămâne nemodificat; `canonical_quality_flag` poate fi `observed`, `provisional`, `validated`, `forecast`, `stale`, `missing`, `suspect`, `corrected`. Fiecare fapt conduce la `source_file_sha256` și `ingestion_run_id`.

Contractul are versiune semantică, migrații forward-only, schema per versiune, fixture-uri per furnizor și verificări de compatibilitate. Schimbarea unității sau semnificației cere versiune incompatibilă; câmpurile noi sunt nullable până când contractul sursei le demonstrează.