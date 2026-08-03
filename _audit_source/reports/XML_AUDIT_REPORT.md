# Audit tehnic și semantic — XML AFDJ Cotele Dunării

## Rezumat executiv

Auditul a analizat răspunsul XML brut descărcat la `2026-08-03T13:10:37.995804+00:00`. Documentul este well-formed, are rădăcina `response` și conține **23** noduri-stație identificate dinamic ca `item` la calea logică `/response/item`.

Sursa este **suficient de stabilă pentru automatizare, cu validările recomandate mai jos**. Au rezultat **0** probleme de validare conform definiției explicite din raportul JSON; separatorii, semnele și unitățile valide sunt tratate ca formate observate, nu automat ca erori.

## Răspuns HTTP XML

| Proprietate | Valoare |
| --- | --- |
| URL cerut | https://afdj.ro/ro/tabel_cotele_dunarii/xml |
| URL final | https://afdj.ro/ro/tabel_cotele_dunarii/xml |
| Status | 200 OK |
| Content-Type | text/xml; charset=UTF-8 |
| Content-Length antet | — |
| Dimensiune efectivă | 62541 bytes |
| Encoding HTTP | UTF-8 |
| Encoding declarație XML | — |
| SHA-256 | 9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c |
| Descărcare UTC | 2026-08-03T13:10:37.995804+00:00 |
| Descărcare Europe/Bucharest | 2026-08-03T16:10:37.995804+03:00 |
| Încercări | 1 |

## Structura XML reală

- Declarație XML: `<?xml version="1.0"?>`
- Encoding efectiv declarat: `UTF-8`
- Element-rădăcină: `response`
- Namespace-uri: `[]`
- Nod-stație: `item`
- Cale logică: `/response/item`
- Număr stații: **23**

### Ierarhia primelor niveluri

| Cale logică | Adâncime | Apariții |
| --- | --- | --- |
| /response | 0 | 1 |
| /response/item | 1 | 23 |
| /response/item/body | 2 | 23 |
| /response/item/changed | 2 | 23 |
| /response/item/content_translation_outdated | 2 | 23 |
| /response/item/content_translation_source | 2 | 23 |
| /response/item/created | 2 | 23 |
| /response/item/default_langcode | 2 | 23 |
| /response/item/display_page_title | 2 | 23 |
| /response/item/feeds_item | 2 | 23 |
| /response/item/field_cota | 2 | 23 |
| /response/item/field_data_actualizare_prognoze | 2 | 23 |
| /response/item/field_field_data_actualiz_cote | 2 | 23 |
| /response/item/field_geolocation_demo_single | 2 | 23 |
| /response/item/field_km | 2 | 23 |
| /response/item/field_localitate_grafic | 2 | 23 |
| /response/item/field_localitatea | 2 | 23 |
| /response/item/field_temperatura_masurata | 2 | 23 |
| /response/item/field_tendinta_120h | 2 | 23 |
| /response/item/field_tendinta_24h | 2 | 23 |
| /response/item/field_tendinta_48h | 2 | 23 |
| /response/item/field_tendinta_72h | 2 | 23 |
| /response/item/field_tendinta_96h | 2 | 23 |
| /response/item/field_variatia | 2 | 23 |
| /response/item/langcode | 2 | 23 |
| /response/item/nid | 2 | 23 |
| /response/item/path | 2 | 23 |
| /response/item/promote | 2 | 23 |
| /response/item/revision_timestamp | 2 | 23 |
| /response/item/revision_translation_affected | 2 | 23 |
| /response/item/revision_uid | 2 | 23 |
| /response/item/status | 2 | 23 |
| /response/item/sticky | 2 | 23 |
| /response/item/title | 2 | 23 |
| /response/item/type | 2 | 23 |
| /response/item/uid | 2 | 23 |
| /response/item/uuid | 2 | 23 |
| /response/item/vid | 2 | 23 |
| /response/item/changed/format | 3 | 23 |
| /response/item/changed/value | 3 | 23 |
| /response/item/content_translation_outdated/value | 3 | 23 |
| /response/item/content_translation_source/value | 3 | 23 |
| /response/item/created/format | 3 | 23 |
| /response/item/created/value | 3 | 23 |
| /response/item/default_langcode/value | 3 | 23 |
| /response/item/display_page_title/value | 3 | 23 |
| /response/item/feeds_item/guid | 3 | 23 |
| /response/item/feeds_item/hash | 3 | 23 |
| /response/item/feeds_item/imported | 3 | 23 |
| /response/item/feeds_item/target_id | 3 | 23 |
| /response/item/feeds_item/target_type | 3 | 23 |
| /response/item/feeds_item/target_uuid | 3 | 23 |
| /response/item/feeds_item/url | 3 | 23 |
| /response/item/field_cota/value | 3 | 23 |
| /response/item/field_data_actualizare_prognoze/value | 3 | 23 |
| /response/item/field_field_data_actualiz_cote/value | 3 | 23 |
| /response/item/field_geolocation_demo_single/data | 3 | 23 |
| /response/item/field_geolocation_demo_single/lat | 3 | 23 |
| /response/item/field_geolocation_demo_single/lng | 3 | 23 |
| /response/item/field_geolocation_demo_single/value | 3 | 23 |
| /response/item/field_km/value | 3 | 23 |
| /response/item/field_localitatea/value | 3 | 23 |
| /response/item/field_temperatura_masurata/value | 3 | 23 |
| /response/item/field_tendinta_120h/value | 3 | 23 |
| /response/item/field_tendinta_24h/value | 3 | 23 |
| /response/item/field_tendinta_48h/value | 3 | 23 |
| /response/item/field_tendinta_72h/value | 3 | 23 |
| /response/item/field_tendinta_96h/value | 3 | 23 |
| /response/item/field_variatia/value | 3 | 23 |
| /response/item/langcode/value | 3 | 23 |
| /response/item/nid/value | 3 | 23 |
| /response/item/path/alias | 3 | 23 |
| /response/item/path/langcode | 3 | 23 |
| /response/item/path/pid | 3 | 23 |
| /response/item/promote/value | 3 | 23 |
| /response/item/revision_timestamp/format | 3 | 23 |
| /response/item/revision_timestamp/value | 3 | 23 |
| /response/item/revision_translation_affected/value | 3 | 23 |
| /response/item/revision_uid/target_id | 3 | 23 |
| /response/item/revision_uid/target_type | 3 | 23 |
| /response/item/revision_uid/target_uuid | 3 | 23 |
| /response/item/revision_uid/url | 3 | 23 |
| /response/item/status/value | 3 | 23 |
| /response/item/sticky/value | 3 | 23 |
| /response/item/title/value | 3 | 23 |
| /response/item/type/target_id | 3 | 23 |
| /response/item/type/target_type | 3 | 23 |
| /response/item/type/target_uuid | 3 | 23 |
| /response/item/uid/target_id | 3 | 23 |
| /response/item/uid/target_type | 3 | 23 |
| /response/item/uid/target_uuid | 3 | 23 |
| /response/item/uid/url | 3 | 23 |
| /response/item/uuid/value | 3 | 23 |
| /response/item/vid/value | 3 | 23 |

### Toate tagurile identificate

| Tag calificat | Nume local | Apariții |
| --- | --- | --- |
| alias | alias | 23 |
| body | body | 23 |
| changed | changed | 23 |
| content_translation_outdated | content_translation_outdated | 23 |
| content_translation_source | content_translation_source | 23 |
| created | created | 23 |
| data | data | 23 |
| default_langcode | default_langcode | 23 |
| display_page_title | display_page_title | 23 |
| feeds_item | feeds_item | 23 |
| field_cota | field_cota | 23 |
| field_data_actualizare_prognoze | field_data_actualizare_prognoze | 23 |
| field_field_data_actualiz_cote | field_field_data_actualiz_cote | 23 |
| field_geolocation_demo_single | field_geolocation_demo_single | 23 |
| field_km | field_km | 23 |
| field_localitate_grafic | field_localitate_grafic | 23 |
| field_localitatea | field_localitatea | 23 |
| field_temperatura_masurata | field_temperatura_masurata | 23 |
| field_tendinta_120h | field_tendinta_120h | 23 |
| field_tendinta_24h | field_tendinta_24h | 23 |
| field_tendinta_48h | field_tendinta_48h | 23 |
| field_tendinta_72h | field_tendinta_72h | 23 |
| field_tendinta_96h | field_tendinta_96h | 23 |
| field_variatia | field_variatia | 23 |
| format | format | 69 |
| guid | guid | 23 |
| hash | hash | 23 |
| imported | imported | 23 |
| item | item | 23 |
| langcode | langcode | 46 |
| lat | lat | 23 |
| lng | lng | 23 |
| nid | nid | 23 |
| path | path | 23 |
| pid | pid | 23 |
| promote | promote | 23 |
| response | response | 1 |
| revision_timestamp | revision_timestamp | 23 |
| revision_translation_affected | revision_translation_affected | 23 |
| revision_uid | revision_uid | 23 |
| status | status | 23 |
| sticky | sticky | 23 |
| target_id | target_id | 92 |
| target_type | target_type | 92 |
| target_uuid | target_uuid | 92 |
| title | title | 23 |
| type | type | 23 |
| uid | uid | 23 |
| url | url | 69 |
| uuid | uuid | 23 |
| value | value | 667 |
| vid | vid | 23 |

### Atribute XML

| Element | Atribut | Apariții | Exemple |
| --- | --- | --- | --- |
| item | key | 23 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |

## Structura nodului-stație

Câmpuri copil observate, în ordinea primei apariții: `nid, uuid, vid, langcode, type, revision_timestamp, revision_uid, status, uid, title, created, changed, promote, sticky, default_langcode, revision_translation_affected, path, content_translation_source, content_translation_outdated, display_page_title, body, feeds_item, field_cota, field_data_actualizare_prognoze, field_field_data_actualiz_cote, field_geolocation_demo_single, field_km, field_localitatea, field_localitate_grafic, field_temperatura_masurata, field_tendinta_120h, field_tendinta_24h, field_tendinta_48h, field_tendinta_72h, field_tendinta_96h, field_variatia`.

| Tag | Rol asociat | Apariții | Lipsește din stații |
| --- | --- | --- | --- |
| nid | — | 23 | 0 |
| uuid | — | 23 | 0 |
| vid | — | 23 | 0 |
| langcode | — | 23 | 0 |
| type | — | 23 | 0 |
| revision_timestamp | — | 23 | 0 |
| revision_uid | — | 23 | 0 |
| status | — | 23 | 0 |
| uid | — | 23 | 0 |
| title | — | 23 | 0 |
| created | — | 23 | 0 |
| changed | — | 23 | 0 |
| promote | — | 23 | 0 |
| sticky | — | 23 | 0 |
| default_langcode | — | 23 | 0 |
| revision_translation_affected | — | 23 | 0 |
| path | — | 23 | 0 |
| content_translation_source | — | 23 | 0 |
| content_translation_outdated | — | 23 | 0 |
| display_page_title | — | 23 | 0 |
| body | — | 23 | 0 |
| feeds_item | — | 23 | 0 |
| field_cota | cota | 23 | 0 |
| field_data_actualizare_prognoze | forecast_updated | 23 | 0 |
| field_field_data_actualiz_cote | data_masuratoare | 23 | 0 |
| field_geolocation_demo_single | coordinates | 23 | 0 |
| field_km | km | 23 | 0 |
| field_localitatea | localitate | 23 | 0 |
| field_localitate_grafic | localitate | 23 | 0 |
| field_temperatura_masurata | temperatura | 23 | 0 |
| field_tendinta_120h | forecast_120h | 23 | 0 |
| field_tendinta_24h | forecast_24h | 23 | 0 |
| field_tendinta_48h | forecast_48h | 23 | 0 |
| field_tendinta_72h | forecast_72h | 23 | 0 |
| field_tendinta_96h | forecast_96h | 23 | 0 |
| field_variatia | variatie | 23 | 0 |

Toate căile indexate până la fiecare stație sunt păstrate în `xml_structure.json`, cheia `station.indexed_paths`.

### Exemplu XML real pentru o stație

```xml
<item key="0">
  <nid>
    <value>82</value>
  </nid>
  <uuid>
    <value>657e4b68-9e17-4102-a240-b2cf2f34ba27</value>
  </uuid>
  <vid>
    <value>105</value>
  </vid>
  <langcode>
    <value>ro</value>
  </langcode>
  <type>
    <target_id>cote</target_id>
    <target_type>node_type</target_type>
    <target_uuid>d5b549ce-2740-49f7-8f34-d399df21fbb6</target_uuid>
  </type>
  <revision_timestamp>
    <value>2023-07-26T12:41:06+00:00</value>
    <format>Y-m-d\TH:i:sP</format>
  </revision_timestamp>
  <revision_uid>
    <target_id>0</target_id>
    <target_type>user</target_type>
    <target_uuid>1faab451-89c1-41f5-bb1a-e9270859731c</target_uuid>
    <url>/ro/user/0</url>
  </revision_uid>
  <status>
    <value>1</value>
  </status>
  <uid>
    <target_id>1</target_id>
    <target_type>user</target_type>
    <target_uuid>3ed76c64-399c-4099-a53e-4456eb2fdb78</target_uuid>
    <url>/ro/users/admin</url>
  </uid>
  <title>
    <value>Sulina</value>
  </title>
  <created>
    <value>2014-07-22T12:09:46+00:00</value>
    <format>Y-m-d\TH:i:sP</format>
  </created>
  <changed>
    <value>2026-08-03T05:57:28+00:00</value>
    <format>Y-m-d\TH:i:sP</format>
  </changed>
  <promote>
    <value>0</value>
  </promote>
  <sticky>
    <value>0</value>
  </sticky>
  <default_langcode>
    <value>1</value>
  </default_langcode>
  <revision_translation_affected>
    <value>1</value>
  </revision_translation_affected>
  <path>
    <alias>/content/sulina</alias>
    <pid>53</pid>
    <langcode>ro</langcode>
  </path>
  <content_translation_source>
    <value>und</value>
  </content_translation_source>
  <content_translation_outdated>
    <value>0</value>
  </content_translation_outdated>
  <display_page_title>
    <value>1</value>
  </display_page_title>
  <body />
  <feeds_item>
    <target_id>7</target_id>
    <imported>2026-08-03T05:57:28+00:00</imported>
    <url>/ro/feed/7</url>
    <guid />
    <hash>f5f18f92c380155802467c0218a371d8</hash>
    <target_type>feeds_feed</target_type>
    <target_uuid>cfcb2ba1-82f0-4490-985d-eaa03abb5b7d</target_uuid>
  </feeds_item>
  <field_cota>
    <value>62</value>
  </field_cota>
  <field_data_actualizare_prognoze>
    <value>2026-08-02T03:00:00+03:00</value>
  </field_data_actualizare_prognoze>
  <field_field_data_actualiz_cote>
    <value>2026-08-03T03:00:00+03:00</value>
  </field_field_data_actualiz_cote>
  <field_geolocation_demo_single>
    <lat>45.15541425</lat>
    <lng>29.652728883222</lng>
    <data />
    <value>45.15541425, 29.652728883222</value>
  </field_geolocation_demo_single>
  <field_km>
    <value>0</value>
  </field_km>
  <field_localitatea>
    <value>Sulina</value>
  </field_localitatea>
  <field_localitate_grafic />
  <field_temperatura_masurata>
    <value>27.5</value>
  </field_temperatura_masurata>
  <field_tendinta_120h>
    <value>0</value>
  </field_tendinta_120h>
  <field_tendinta_24h>
    <value>0</value>
  </field_tendinta_24h>
  <field_tendinta_48h>
    <value>0</value>
  </field_tendinta_48h>
  <field_tendinta_72h>
    <value>0</value>
  </field_tendinta_72h>
  <field_tendinta_96h>
    <value>0</value>
  </field_tendinta_96h>
  <field_variatia>
    <value>3</value>
  </field_variatia>
</item>
```

## Formatele reale ale câmpurilor

| Rol | Prezente | Lipsă | Exemple brute | Distribuție |
| --- | --- | --- | --- | --- |
| coordinates | 23 | 0 | '45.15541425, 29.652728883222', '45.2721887, 28.4571456', '45.4338215, 28.0549395', '45.2716092, 27.9742932' | text/data |
| cota | 23 | 0 | '62', '25', '26', '4' | neg=13, zero=0, poz=10 |
| data_masuratoare | 23 | 0 | '2026-08-03T03:00:00+03:00' | text/data |
| forecast_120h | 23 | 0 | '0', '16', '-9', '-118' | neg=12, zero=8, poz=3 |
| forecast_24h | 23 | 0 | '0', '22', '23', '-115' | neg=11, zero=9, poz=3 |
| forecast_48h | 23 | 0 | '0', '21', '-2', '-115' | neg=12, zero=8, poz=3 |
| forecast_72h | 23 | 0 | '0', '20', '-4', '-116' | neg=12, zero=8, poz=3 |
| forecast_96h | 23 | 0 | '0', '18', '-6', '-117' | neg=12, zero=8, poz=3 |
| forecast_updated | 23 | 0 | '2026-08-02T03:00:00+03:00' | text/data |
| km | 23 | 0 | '0', '103', '150', '170' | neg=0, zero=1, poz=22 |
| latitude | 23 | 0 | '45.15541425', '45.2721887', '45.4338215', '45.2716092' | neg=0, zero=0, poz=23 |
| localitate | 23 | 0 | 'Sulina', 'Isaccea', 'Galati', 'Braila' | text/data |
| longitude | 23 | 0 | '29.652728883222', '28.4571456', '28.0549395', '27.9742932' | neg=0, zero=0, poz=23 |
| temperatura | 23 | 0 | '27.5', '28' | neg=0, zero=0, poz=23 |
| variatie | 23 | 0 | '3', '1', '0', '-1' | neg=15, zero=5, poz=3 |

### Verificări explicite de format în XML

| Rol | Plus explicit | Virgulă zecimală | Punct | Punct de mii | Spații margini | Unități | Lipsă | Nenumerice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coordinates | 0 | 0 | 23 | 0 | 0 | 0 | 0 | 0 |
| cota | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| data_masuratoare | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_120h | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_24h | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_48h | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_72h | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_96h | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forecast_updated | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| km | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| latitude | 0 | 0 | 23 | 0 | 0 | 0 | 0 | 0 |
| localitate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| longitude | 0 | 0 | 23 | 0 | 0 | 0 | 0 | 0 |
| temperatura | 0 | 0 | 17 | 0 | 0 | 0 | 0 | 0 |
| variatie | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Normalizarea numerică din preview acceptă semn explicit, virgulă zecimală și punct zecimal; pentru `km`, `cota`, `variatie` și prognoze, grupurile de exact trei cifre după punct sunt interpretate ca separatori de mii (de exemplu `1.072` → `1072`). Valorile originale rămân intacte.

## Diferențe față de documentația locală

Documentația declară: `localitate, km, cota, variatie, temperatura, data_masuratoare`.
Roluri documentate neidentificate semantic în XML: `niciunul`.
Taguri literale din documentație care nu apar ca atare: `localitate, km, cota, variatie, temperatura, data_masuratoare`.
Taguri suplimentare sau neasociate documentației: `nid, uuid, vid, langcode, type, revision_timestamp, revision_uid, status, uid, title, created, changed, promote, sticky, default_langcode, revision_translation_affected, path, content_translation_source, content_translation_outdated, display_page_title, body, feeds_item, field_data_actualizare_prognoze, field_geolocation_demo_single, field_tendinta_120h, field_tendinta_24h, field_tendinta_48h, field_tendinta_72h, field_tendinta_96h`.

Schema reală nu este lista plată sugerată de documentație: stația este un nod CMS `item`, câmpurile sunt wrapper-e `field_*`, iar valorile sunt în general în copii `value`. Sunt prezente și UUID/nid, coordonate și prognoze.

Documentația indică data `DD/MM/YYYY`, dar XML-ul auditat folosește ISO 8601 cu oră și fus (`2026-08-03T03:00:00+03:00`). În XML, temperatura folosește punct zecimal și nivelurile nu includ `cm`; pagina HTML folosește virgulă zecimală și unități afișate. Nu a fost observată valoarea textuală `Mm` în această captură.

## Coordonate și prognoze în XML

| Rol căutat | Există | Taguri asociate |
| --- | --- | --- |
| latitude | DA | lat |
| longitude | DA | lng |
| coordinates | DA | field_geolocation_demo_single |
| forecast_24h | DA | field_tendinta_24h |
| forecast_48h | DA | field_tendinta_48h |
| forecast_72h | DA | field_tendinta_72h |
| forecast_96h | DA | field_tendinta_96h |
| forecast_120h | DA | field_tendinta_120h |
| forecast_updated | DA | field_data_actualizare_prognoze |

## Calitatea datelor și cazuri-limită

- Cota minimă: `{'station_index': 6, 'raw': '-213', 'numeric': -213}`; cota maximă: `{'station_index': 19, 'raw': '2510', 'numeric': 2510}`.
- Variația minimă: `{'station_index': 19, 'raw': '-5', 'numeric': -5}`; variația maximă: `{'station_index': 1, 'raw': '3', 'numeric': 3}`.
- Date brute unice: `['2026-08-03T03:00:00+03:00']`.
- Date ISO unice: `['2026-08-03']`.
- Date invalide, indici stație: `[]`.
- Valori nenumerice: `{'km': [], 'cota': [], 'variatie': [], 'temperatura': []}`.
- Duplicate complete: `[]`.
- Duplicate după localitate + km: `[]`.
- Duplicate după localitate + dată: `[]`.
- Variante de capitalizare: `[]`.
- Localități cu caractere românești: `[]`.
- Kilometri textuali / cu unități: `[]`.

### Câmpuri lipsă pentru fiecare coloană XML

| Coloană | Valori lipsă |
| --- | --- |
| nid | 0 |
| uuid | 0 |
| vid | 0 |
| langcode | 0 |
| type | 0 |
| revision_timestamp | 0 |
| revision_uid | 0 |
| status | 0 |
| uid | 0 |
| title | 0 |
| created | 0 |
| changed | 0 |
| promote | 0 |
| sticky | 0 |
| default_langcode | 0 |
| revision_translation_affected | 0 |
| path | 0 |
| content_translation_source | 0 |
| content_translation_outdated | 0 |
| display_page_title | 0 |
| body | 23 |
| feeds_item | 0 |
| field_cota | 0 |
| field_data_actualizare_prognoze | 0 |
| field_field_data_actualiz_cote | 0 |
| field_geolocation_demo_single | 0 |
| field_km | 0 |
| field_localitatea | 0 |
| field_localitate_grafic | 23 |
| field_temperatura_masurata | 0 |
| field_tendinta_120h | 0 |
| field_tendinta_24h | 0 |
| field_tendinta_48h | 0 |
| field_tendinta_72h | 0 |
| field_tendinta_96h | 0 |
| field_variatia | 0 |

### Primele 5 stații

| Localitate | km | cota | variatie | temperatura | data |
| --- | --- | --- | --- | --- | --- |
| Sulina | 0 | 62 | 3 | 27.5 | 2026-08-03T03:00:00+03:00 |
| Isaccea | 103 | 25 | 1 | 27.5 | 2026-08-03T03:00:00+03:00 |
| Galati | 150 | 26 | 0 | 27.5 | 2026-08-03T03:00:00+03:00 |
| Braila | 170 | 4 | 0 | 27.5 | 2026-08-03T03:00:00+03:00 |
| Harsova | 253 | -115 | -1 | 27.5 | 2026-08-03T03:00:00+03:00 |

### Ultimele 5 stații

| Localitate | km | cota | variatie | temperatura | data |
| --- | --- | --- | --- | --- | --- |
| Orsova | 954 | 2510 | -5 | 28 | 2026-08-03T03:00:00+03:00 |
| Drencova | 1015 | 963 | -1 | 28 | 2026-08-03T03:00:00+03:00 |
| Moldova Veche | 1048 | 690 | -2 | 28 | 2026-08-03T03:00:00+03:00 |
| Bazias | 1072 | 544 | 0 | 28 | 2026-08-03T03:00:00+03:00 |
| Tulcea | 71 | 21 | 0 | 27.5 | 2026-08-03T03:00:00+03:00 |

### Lista completă a localităților XML

Sulina, Isaccea, Galati, Braila, Harsova, Cernavoda, Calarasi, Oltenita, Giurgiu, Zimnicea, Turnu Magurele, Corabia, Bechet, Rast, Calafat, Cetate, Gruia, Drobeta Turnu Severin, Orsova, Drencova, Moldova Veche, Bazias, Tulcea

## Comparație cu pagina HTML oficială

Pagina HTML a răspuns cu `200 OK`, Content-Type `text/html; charset=UTF-8` și 209077 bytes.
Extragere robustă: **reușită**; metodă: `lxml + selectarea tabelului dupa rolurile semantice ale antetelor`.
Stații XML: **23**; stații HTML: **23**; comune: **23**.
Doar în XML: `[]`. Doar în HTML: `[]`.
Nepotriviri pe stațiile comune: `{'km': 0, 'cota': 0, 'variatie': 0, 'temperatura': 0, 'data_masuratoare': 0}`.

### Verificarea localităților solicitate

| Localitate | Câmp | XML brut | HTML brut | Egal normalizat |
| --- | --- | --- | --- | --- |
| Bazias | km | 1072 | 1072 | DA |
| Bazias | cota | 544 | 544 cm | DA |
| Bazias | variatie | 0 | 0 | DA |
| Bazias | temperatura | 28 | 28,0 °C | DA |
| Bazias | data_masuratoare | 2026-08-03T03:00:00+03:00 | 03/08/2026 | DA |
| Orsova | km | 954 | 954 | DA |
| Orsova | cota | 2510 | 2510 cm | DA |
| Orsova | variatie | -5 | -5 | DA |
| Orsova | temperatura | 28 | 28,0 °C | DA |
| Orsova | data_masuratoare | 2026-08-03T03:00:00+03:00 | 03/08/2026 | DA |
| Giurgiu | km | 493 | 493 | DA |
| Giurgiu | cota | -158 | -158 cm | DA |
| Giurgiu | variatie | -1 | -1 | DA |
| Giurgiu | temperatura | 27.5 | 27,5 °C | DA |
| Giurgiu | data_masuratoare | 2026-08-03T03:00:00+03:00 | 03/08/2026 | DA |
| Galati | km | 150 | 150 | DA |
| Galati | cota | 26 | 26 cm | DA |
| Galati | variatie | 0 | 0 | DA |
| Galati | temperatura | 27.5 | 27,5 °C | DA |
| Galati | data_masuratoare | 2026-08-03T03:00:00+03:00 | 03/08/2026 | DA |
| Sulina | km | 0 | 0 | DA |
| Sulina | cota | 62 | 62 cm | DA |
| Sulina | variatie | 3 | 3 | DA |
| Sulina | temperatura | 27.5 | 27,5 °C | DA |
| Sulina | data_masuratoare | 2026-08-03T03:00:00+03:00 | 03/08/2026 | DA |

Lista completă a localităților HTML: Sulina, Tulcea, Isaccea, Galati, Braila, Harsova, Cernavoda, Calarasi, Oltenita, Giurgiu, Zimnicea, Turnu Magurele, Corabia, Bechet, Rast, Calafat, Cetate, Gruia, Drobeta Turnu Severin, Orsova, Drencova, Moldova Veche, Bazias

## Recomandări exacte pentru parserul operațional

1. Descărcați bytes cu maximum 3 încercări, timeout și User-Agent; acceptați doar HTTP 2xx și Content-Type XML.
2. Păstrați fiecare captură brută imuabilă și calculați SHA-256 înainte de parsare.
3. Folosiți un parser XML real; nu regex pentru structură. Tratați namespace-urile după numele local, dar înregistrați URI-ul.
4. Detectați nodul-stație prin copii semantici (`localitate` + `cota`) și validați că structura dominantă rămâne aceeași.
5. Păstrați valorile brute și produceți separat valori normalizate. Nu eliminați punctul înainte de a aplica regula dependentă de câmp.
6. Pentru `km`/`cota`, interpretați punctul urmat de grupuri de 3 cifre ca separator de mii; pentru temperatură și coordonate, punctul este zecimal.
7. Acceptați `+`, `-`, virgulă/punct, spații și unități cunoscute; respingeți explicit resturile textuale necunoscute după extragere.
8. Validați datele calendaristic în formatul observat și păstrați atât textul brut, cât și ISO `YYYY-MM-DD`.
9. Eșuați controlat sau alertați la: XML invalid, zero stații, lipsa câmpurilor-cheie, scădere bruscă a numărului de stații, duplicate ori schimbare de schemă.
10. Comparați periodic un eșantion cu tabelul HTML folosind antetele semantice, nu indecși globali sau selectori CSS fragili.

## Chei și identificatori recomandați

- **Cheie unică de înregistrare:** `(station_stable_id, measurement_date_iso)`. Dacă sursa va publica mai multe măsurători în aceeași zi, extindeți cu ora reală a măsurării; ora descărcării nu trebuie folosită ca oră a măsurării.
- **Identificator stabil de stație:** folosiți UUID-ul oficial din `uuid/value`, observat în fiecare nod `item`; păstrați identificatorul CMS din câmpul nid/value doar ca reper auxiliar. Dacă aceste câmpuri dispar, reveniți controlat la un ID intern din localitatea canonică + poziția fluvială normalizată și mențineți o tabelă de aliasuri. Nu folosiți doar numele.
- Păstrați separat `locality_original`, forma canonică afișată și cheia accent-insensitive/case-insensitive folosită numai la reconciliere.

## Concluzie privind automatizarea

Captura curentă este adecvată pentru automatizare cu schema tolerantă și validările descrise. Stabilitatea în timp nu poate fi demonstrată dintr-o singură captură; recomandarea este monitorizarea hash-ului structural, a setului de taguri și a numărului de stații la fiecare rulare.

---

Artefactele machine-readable (`http_metadata.json`, `xml_structure.json`, `data_quality_summary.json`, `xml_tag_counts.csv`) sunt sursa exactă pentru detaliile exhaustive; raportul de față le sintetizează fără a modifica datele brute.
