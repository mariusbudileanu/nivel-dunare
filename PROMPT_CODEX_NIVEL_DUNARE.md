# PROMPT PENTRU CODEX — PROIECT „NIVELUL DUNĂRII”

Lucrează exclusiv în folderul:

`C:\Users\mariu\Date\_nivel_Dunare`

## 0. Obiectivul general

Construiește, testează, documentează și publică o aplicație web statică modernă pentru monitorizarea cotelor Dunării pe baza sursei publice AFDJ:

- XML: `https://afdj.ro/ro/tabel_cotele_dunarii/xml`
- pagina HTML oficială pentru verificare semantică: `https://www.afdj.ro/ro/cotele-dunarii`

Aplicația trebuie să:

1. colecteze automat datele cel puțin o dată pe zi;
2. arhiveze observațiile zilnice și toate edițiile prognozelor;
3. păstreze pentru audit toate tagurile și valorile brute din XML;
4. ofere o hartă interactivă modernă cu toate stațiile;
5. ofere grafice istorice și prognoze interactive pentru fiecare stație;
6. permită explorarea liberă a intervalelor temporale;
7. permită descărcarea datelor în CSV;
8. permită descărcarea fiecărui grafic individual ca PNG de rezoluție mare;
9. ruleze complet prin GitHub Actions și să fie publicată prin GitHub Pages;
10. fie robustă, documentată, responsive și accesibilă.

Nu construi un prototip minimal. Construiește un produs public complet, cu structură clară și cod mentenabil.

## 1. Reguli de lucru

- Nu modifica și nu șterge nimic din afara folderului indicat.
- Nu șterge folderul existent `_audit_source` și nici fișierele sale.
- Citește înainte de implementare toate fișierele de audit disponibile în `_audit_source`, în special:
  - `reports\XML_AUDIT_REPORT.md`
  - `reports\xml_structure.json`
  - `reports\xml_tag_counts.csv`
  - `reports\data_quality_summary.json`
  - `reports\http_metadata.json`
  - fișierele brute XML și HTML existente.
- Folosește rezultatele auditului ca sursă de adevăr pentru structura reală.
- Nu presupune că documentația simplificată descrie integral XML-ul.
- Nu introduce credențiale, parole, tokenuri sau date sensibile în cod, commituri, loguri ori documentație.
- Folosește `GITHUB_TOKEN` furnizat automat de GitHub Actions pentru commiturile automate.
- Nu cere confirmări între pași. Continuă până la implementarea completă, exceptând situațiile în care:
  - autentificarea GitHub nu este disponibilă;
  - există un conflict real de repository;
  - o operațiune externă nu poate fi executată în siguranță.
- În asemenea situații, finalizează tot ce poate fi realizat local și raportează exact blocajul.

## 2. Configurația proiectului

Folosește următoarele valori implicite:

- titlu public: `Nivelul Dunării`
- subtitlu: `Monitorizare zilnică a cotelor și prognozelor hidrologice`
- repository GitHub implicit: `nivel-dunare`
- branch implicit: `main`
- limbă interfață: română
- fus orar logic al datelor și interfeței: `Europe/Bucharest`

Dacă în folder există deja un repository Git valid, inspectează-l și continuă fără a-i distruge istoricul.

Dacă nu există repository:
1. inițializează Git;
2. creează branch-ul `main`;
3. verifică `gh auth status`;
4. creează un repository public GitHub numit `nivel-dunare`;
5. configurează remote-ul `origin`;
6. publică branch-ul `main`.

Dacă repository-ul `nivel-dunare` există deja în contul autentificat, reutilizează-l numai dacă este clar că aparține acestui proiect. Nu crea automat un nume alternativ fără să raportezi.

## 3. Constatări obligatorii din audit

Parserul trebuie construit pentru structura reală:

- root XML: `/response`
- nod-stație: `/response/item`
- număr observat la audit: 23 stații
- fără namespace
- fiecare `item` are atributul `key`
- identificatorii disponibili includ `uuid`, `nid`, `vid`
- coordonatele există în:
  - `field_geolocation_demo_single/lat`
  - `field_geolocation_demo_single/lng`
  - `field_geolocation_demo_single/value`
- observațiile există în:
  - `field_cota/value`
  - `field_variatia/value`
  - `field_temperatura_masurata/value`
  - `field_km/value`
  - `field_localitatea/value`
  - `field_field_data_actualiz_cote/value`
- data prognozei există în:
  - `field_data_actualizare_prognoze/value`
- prognozele există în:
  - `field_tendinta_24h/value`
  - `field_tendinta_48h/value`
  - `field_tendinta_72h/value`
  - `field_tendinta_96h/value`
  - `field_tendinta_120h/value`

Folosește `uuid/value` drept identificator stabil principal al stației.
Folosește `nid/value` doar ca identificator secundar/fallback.
Nu folosi indexul `item key` sau numele localității ca identificator permanent.

## 4. Cerință esențială: toate tagurile XML

Utilizatorul dorește să fie implementat și păstrat tot ceea ce apare în schema reală XML, nu doar câmpurile hidrologice.

Prin urmare:

1. La fiecare captură reușită, salvează XML-ul brut exact, fără reformatare.
2. Creează un export zilnic „flattened raw”, cu un rând per stație și câte o coloană pentru fiecare leaf path XML identificat.
3. Denumește coloanele prin calea logică completă, astfel încât tagurile omonime precum `value`, `url` sau `target_uuid` să nu se confunde.
4. Include și:
   - atributul `item@key`;
   - toate tagurile Drupal;
   - toate valorile `target_id`, `target_type`, `target_uuid`, `url`, `hash`, `imported`;
   - datele `created`, `changed`, `revision_timestamp`;
   - `path/alias`;
   - toate câmpurile hidrologice și de prognoză.
5. Menține un catalog de schemă curent și un istoric al schimbărilor de schemă.
6. Compară la fiecare rulare tagurile observate cu schema anterioară.
7. Un tag nou nu trebuie să blocheze automat procesarea; trebuie păstrat și raportat.
8. Lipsa unui câmp critic hidrologic trebuie să blocheze actualizarea tabelelor publice.
9. Câmpurile interne Drupal nu trebuie expuse inutil în interfața principală, dar trebuie păstrate în arhiva tehnică și puse la dispoziție într-un export tehnic separat.

## 5. Structura recomandată a proiectului

Creează o structură coerentă, apropiată de următorul model:

```text
_nivel_Dunare/
├── .github/
│   └── workflows/
│       ├── update-data.yml
│       └── deploy-pages.yml
├── _audit_source/
├── config/
│   ├── app_config.json
│   ├── station_display_names.json
│   └── quality_rules.json
├── data/
│   ├── archive/
│   │   ├── raw_xml/
│   │   │   └── YYYY/MM/YYYY-MM-DDTHHMMSS.xml.gz
│   │   ├── flat_raw/
│   │   │   └── YYYY/MM/YYYY-MM-DD.csv.gz
│   │   └── diagnostics/
│   ├── canonical/
│   │   ├── stations.csv
│   │   ├── observations.csv
│   │   ├── forecasts.csv
│   │   ├── forecast_scores.csv
│   │   ├── corrections.csv
│   │   └── ingestion_runs.csv
│   ├── daily/
│   │   └── YYYY-MM-DD.csv
│   ├── station_csv/
│   │   └── <station-slug>.csv
│   ├── schema/
│   │   ├── current_schema.json
│   │   ├── current_tag_counts.csv
│   │   └── schema_changes.csv
│   └── public/
│       ├── latest.csv
│       ├── observations.csv
│       ├── forecasts.csv
│       ├── stations.csv
│       ├── latest.geojson
│       ├── status.json
│       ├── station/
│       │   ├── <station-slug>-observations.json
│       │   ├── <station-slug>-forecasts.json
│       │   ├── <station-slug>-forecast-scores.json
│       │   └── <station-slug>.csv
│       └── downloads.json
├── docs/
│   ├── DATA_DICTIONARY.md
│   ├── ARCHITECTURE.md
│   ├── OPERATIONS.md
│   ├── FORECAST_METHODOLOGY.md
│   ├── USER_GUIDE.md
│   └── audit/
├── public/
│   ├── index.html
│   ├── 404.html
│   ├── assets/
│   │   ├── css/
│   │   ├── js/
│   │   ├── icons/
│   │   └── images/
│   └── data/
├── scripts/
│   ├── ingest_afdj.py
│   ├── flatten_xml.py
│   ├── parse_html_forecasts.py
│   ├── build_public_data.py
│   ├── calculate_forecast_scores.py
│   ├── validate_repository.py
│   ├── smoke_test_site.py
│   └── serve_local.py
├── tests/
│   ├── fixtures/
│   ├── test_xml_parser.py
│   ├── test_normalization.py
│   ├── test_forecast_availability.py
│   ├── test_idempotency.py
│   ├── test_schema_changes.py
│   ├── test_scoring.py
│   └── test_public_outputs.py
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

Poți ajusta structura dacă ai un motiv tehnic bun, dar păstrează separarea clară între:

- arhiva brută;
- datele canonice;
- datele publice pentru frontend;
- interfața web;
- scripturi;
- teste;
- documentație.

## 6. Colectarea datelor

Creează un colector Python robust.

### Cerințe HTTP

- HTTP GET;
- timeout explicit;
- maximum 3 încercări;
- backoff între încercări;
- User-Agent explicit;
- verificare status;
- verificare Content-Type;
- păstrarea URL-ului final;
- SHA-256 pentru fiecare răspuns;
- timestamp UTC;
- timestamp Europe/Bucharest;
- loguri clare;
- fără a salva credențiale.

Descarcă la fiecare rulare:

1. XML-ul AFDJ;
2. pagina HTML oficială AFDJ folosită pentru validarea prognozelor.

### Arhiva brută

Pentru XML:

- salvează fiecare captură nouă ca `.xml.gz`;
- păstrează bytes-ii originali;
- nu crea o captură duplicată dacă SHA-256 este identic cu ultima captură;
- înregistrează totuși rularea în `ingestion_runs.csv`.

Pentru HTML:

- nu este necesar să arhivezi toate paginile HTML zilnic dacă nu există probleme;
- păstrează hash-ul și rezultatul validării;
- arhivează HTML-ul brut comprimat în `data/archive/diagnostics/` atunci când:
  - parsarea HTML eșuează;
  - XML și HTML nu corespund;
  - apare o prognoză ambiguă;
  - numărul stațiilor diferă;
  - se schimbă structura tabelului.

## 7. Normalizarea datelor

Păstrează întotdeauna:

- valoarea brută;
- valoarea normalizată;
- starea de calitate;
- sursa deciziei.

### Observații

Schema canonică minimă pentru `observations.csv`:

```text
station_id
station_nid
source_name
display_name
river_km
latitude
longitude
measurement_datetime
measurement_date
level_cm
variation_cm_24h
water_temperature_c
capture_datetime_utc
capture_datetime_local
source_changed_datetime
record_hash
first_seen_at
last_seen_at
quality_flag
```

Cheia logică:

`station_id + measurement_datetime`

Rulările repetate nu trebuie să creeze duplicate.

Dacă aceeași cheie apare ulterior cu valori diferite:

- păstrează captura brută;
- înregistrează diferența în `corrections.csv`;
- actualizează rândul canonic la cea mai recentă versiune;
- păstrează `first_seen_at` și `last_seen_at`;
- nu ascunde corecția.

### Prognoze

Nu stoca prognozele numai în format wide.
Creează obligatoriu `forecasts.csv` în format lung:

```text
station_id
station_nid
forecast_issue_datetime
forecast_issue_date
target_datetime
target_date
lead_hours
forecast_level_raw
forecast_level_cm
forecast_available
availability_source
html_value_raw
xml_html_match
capture_datetime_utc
capture_datetime_local
forecast_run_hash
first_seen_at
last_seen_at
quality_flag
```

Pentru fiecare stație și ediție de prognoză generează câte cinci rânduri:

- 24 h
- 48 h
- 72 h
- 96 h
- 120 h

Calculează:

`target_datetime = forecast_issue_datetime + lead_hours`

Cheia logică principală:

`station_id + forecast_issue_datetime + lead_hours`

Păstrează fiecare ediție istorică de prognoză.
Nu suprascrie prognozele vechi când apare una nouă.

Dacă aceeași cheie este corectată ulterior, înregistrează modificarea în `corrections.csv`, exact ca pentru observații.

## 8. Regula critică pentru prognozele cu valoarea XML 0

Auditul a arătat că unele câmpuri de prognoză pot avea valoarea XML `0`, în timp ce în tabelul HTML oficial celula poate fi necompletată.

Nu interpreta automat orice `0` XML drept o prognoză reală de 0 cm.

Implementează următoarea logică:

### Caz 1 — XML numeric și HTML numeric, valori egale

```text
forecast_available = true
forecast_level_cm = valoarea numerică
availability_source = "xml_html_confirmed"
xml_html_match = true
quality_flag = "valid"
```

### Caz 2 — XML 0 și HTML gol

```text
forecast_available = false
forecast_level_cm = null
forecast_level_raw = "0"
availability_source = "html_blank_xml_zero"
xml_html_match = null
quality_flag = "missing_forecast_encoded_as_zero"
```

### Caz 3 — XML nonzero și HTML gol

```text
forecast_available = false
forecast_level_cm = null
forecast_level_raw = valoarea XML
availability_source = "html_blank_xml_nonzero"
xml_html_match = false
quality_flag = "xml_html_availability_mismatch"
```

Arhivează HTML-ul în diagnostics.

### Caz 4 — XML și HTML numerice, dar diferite

```text
forecast_available = true
forecast_level_cm = valoarea XML
html_value_raw = valoarea HTML
availability_source = "xml_with_html_mismatch"
xml_html_match = false
quality_flag = "xml_html_value_mismatch"
```

Afișează o avertizare discretă în interfață și arhivează HTML-ul.

### Caz 5 — parsarea HTML eșuează

- pentru valoare XML nonzero:
  - păstrează valoarea;
  - `forecast_available = true`;
  - `availability_source = "xml_only_html_unavailable"`;
  - `quality_flag = "html_validation_unavailable"`.
- pentru valoare XML zero:
  - nu presupune că este validă;
  - `forecast_available = false`;
  - `forecast_level_cm = null`;
  - `quality_flag = "ambiguous_xml_zero_html_unavailable"`.

## 9. Registrul stațiilor

Creează `stations.csv` folosind `uuid` drept `station_id`.

Câmpuri minime:

```text
station_id
station_nid
source_name
display_name
slug
river_km
latitude
longitude
path_alias
first_seen_at
last_seen_at
active
```

Păstrează numele original exact în `source_name`.

Poți utiliza un fișier separat `config/station_display_names.json` pentru afișarea cu diacritice în interfață, fără a modifica identitatea și datele brute.

Exemple de afișare posibilă:

- Baziaș
- Orșova
- Drobeta-Turnu Severin
- Turnu Măgurele
- Călărași
- Oltenița
- Hârșova
- Cernavodă
- Brăila
- Galați

Nu folosi `display_name` ca cheie.

## 10. Validarea sursei

Validează înainte de a actualiza tabelele publice:

- XML well-formed;
- root `response`;
- existența nodurilor `item`;
- existența `uuid`, localitate, km, cotă, variație, temperatură, data măsurării, coordonate;
- valori numerice parseabile;
- date ISO valide;
- latitudine și longitudine valide;
- lipsa duplicatelor de identitate;
- scădere anormală a numărului de stații;
- schimbări de schemă;
- corespondența XML–HTML pentru prognoze;
- existența celor cinci orizonturi ca taguri, chiar dacă unele valori sunt indisponibile.

Nu hardcoda „23” ca regulă absolută.
Folosește-l ca valoare de referință pentru avertizare.

De exemplu:

- dacă numărul de stații scade cu mai mult de 20% față de ultima rulare validă, blochează actualizarea canonică;
- dacă apare o stație nouă, accept-o, raporteaz-o și adaug-o registrului;
- dacă dispare temporar o singură stație, marcheaz-o ca lipsă/stale, fără a șterge istoricul.

## 11. Calculul evaluării prognozelor

Creează un proces separat care compară prognozele istorice cu observațiile realizate.

Potrivește:

`station_id + target_date`

cu:

`station_id + measurement_date`

Pentru fiecare stație și fiecare `lead_hours` calculează:

- `n_pairs`
- eroarea semnată: `forecast - observed`
- MAE
- RMSE
- bias
- procent în interval de ±5 cm
- procent în interval de ±10 cm
- procent în interval de ±20 cm
- prima și ultima dată incluse

Creează `forecast_scores.csv`.

În interfață:

- sub 10 perechi: `Date insuficiente`
- 10–29 perechi: `Rezultate preliminare`
- minimum 30 perechi: indicatori afișați normal

Precizează clar că aceste statistici sunt calculate de aplicație și nu sunt publicate de AFDJ sau INHGA.

## 12. Date publice și descărcări CSV

Generează și actualizează automat:

### Descărcări globale

- situația curentă: `latest.csv`
- toate observațiile: `observations.csv`
- toate prognozele în format lung: `forecasts.csv`
- registrul stațiilor: `stations.csv`
- valorile curente geospațiale: `latest.geojson`
- export tehnic cu toate câmpurile XML pentru fiecare captură zilnică

### Descărcări per stație

Pentru fiecare stație:

- observații istorice;
- prognoze istorice;
- un CSV combinat, documentat;
- datele exact vizibile în grafic, generate în browser la cerere.

### Descărcare exactă a selecției

Fiecare grafic trebuie să aibă:

- buton `Descarcă CSV`;
- exportul trebuie să conțină exact:
  - stația sau stațiile selectate;
  - intervalul vizibil;
  - seriile active;
  - prognoza selectată;
  - coloane explicite și unități documentate.

## 13. Frontend — principii generale

Construiește o aplicație statică fără backend.

Recomandare:

- HTML semantic;
- CSS modular;
- JavaScript modern, organizat pe module;
- Leaflet pentru hartă;
- Plotly pentru grafice;
- biblioteci externe pin-uite la versiuni stabile exacte;
- fără framework greu dacă nu este necesar;
- fără proces de build fragil;
- fără dependențe inutile.

Generează JSON-uri optimizate pentru frontend.
Nu obliga browserul să descarce întregul istoric global la deschiderea paginii.

Comportament recomandat:

- harta încarcă numai `latest.geojson`, `stations` și `status`;
- istoricul unei stații este încărcat lazy, numai la selectarea ei;
- fișierele per stație sunt cache-uite în browser;
- schimbarea stației nu reîncarcă pagina.

## 14. Design system modern

Interfața trebuie să arate ca un dashboard hidrologic public modern, nu ca o pagină tehnică sau un prototip.

Creează variabile CSS centrale și un design system coerent.

Paleta de bază recomandată:

```css
--bg-main: #F4F7FB;
--surface: #FFFFFF;
--text-primary: #183042;
--text-secondary: #647484;
--primary: #126A91;
--observation: #147DA6;
--current-point: #00A6A6;
--forecast: #7161D9;
--rising: #169B7A;
--falling: #E36B5D;
--stationary: #7B8794;
--warning: #E5A93D;
--border: #DCE5EC;
```

Poți rafina ușor nuanțele dacă păstrezi rolurile și contrastul.

Cerințe vizuale:

- fundal luminos și aerisit;
- carduri albe;
- colțuri rotunjite 14–16 px;
- umbre discrete;
- contururi fine;
- spațiere generoasă;
- tipografie modernă și foarte lizibilă;
- iconografie coerentă;
- animații scurte și discrete;
- fără degradeuri stridente;
- fără efecte decorative inutile;
- fără culori saturate care concurează cu datele.

Culorile nu trebuie să fie singurul mijloc de transmitere a sensului.
Folosește și:

- semne + / − / 0;
- linii continue și întrerupte;
- simboluri diferite;
- etichete text;
- stări focus/hover;
- ARIA labels.

Interfața trebuie să fie responsive și utilizabilă pe:

- desktop;
- laptop;
- tabletă;
- telefon.

## 15. Structura paginii

### Header

Include:

- titlul `Nivelul Dunării`;
- ultima dată oficială a observațiilor;
- data ultimei capturi;
- starea sistemului;
- buton `Info`;
- buton `Descarcă date`;
- eventual un selector compact al stației.

### Indicatori generali

Afișează:

- numărul stațiilor raportate;
- stații în creștere;
- stații în scădere;
- stații staționare;
- stații cu date lipsă sau stale.

Nu compara cotele absolute ale stațiilor ca și cum ar avea același zero de referință.
Nu afișa „cea mai mare cotă a Dunării” între stații fără avertisment metodologic.

### Layout desktop

Aproximativ:

- hartă: 40–45%;
- analiză/grafice: 55–60%.

Graficul este elementul principal și trebuie să primească suficient spațiu.

### Layout mobil

- harta apare prima;
- selectarea unei stații deschide un panou aproape full-screen;
- graficele sunt touch-friendly;
- butoanele de perioadă, fullscreen, CSV și PNG sunt ușor de apăsat.

## 16. Harta interactivă

Folosește Leaflet.

### Basemap

- folosește un basemap luminos, modern și cu saturație redusă;
- asigură atribuirea legală completă;
- centralizează URL-ul și atribuirea în config;
- oferă fallback către OpenStreetMap Standard dacă tile providerul principal nu este disponibil.

### Stații

- marker circular;
- dimensiune constantă;
- contur alb;
- umbră discretă;
- culoare după variația zilnică:
  - creștere: verde/turcoaz;
  - scădere: coral;
  - staționare: gri-albăstrui;
  - date vechi/problemă: galben;
- markerul selectat:
  - mai mare;
  - contur dublu;
  - halou discret;
  - adus în față.

Nu folosi clustering; sunt puține stații.

### Popup

Stilizează popupul, nu folosi aspectul implicit Leaflet.

Conținut:

```text
NUME STAȚIE
Km ...

Nivel actual
Variație 24 h
Temperatura
Data observației
Starea datelor

[Deschide analiza]
```

### Controale

Include:

- căutare după stație;
- reset extindere;
- centrare pe stația selectată;
- legendă;
- fullscreen;
- opțional selector de basemap.

### Sincronizare

- clic pe marker → încarcă și afișează stația în panoul analitic;
- schimbarea stației păstrează intervalul temporal;
- selecția este reflectată în URL;
- pagina poate fi distribuită prin link.

Exemplu:

`?station=giurgiu&range=30d&chart=level`

## 17. Panoul stației

La selectarea unei stații afișează:

- nume;
- km fluvial;
- nivel actual;
- variație 24 h;
- temperatură;
- data observației;
- data prognozei;
- stare calitate;
- butoane de download.

Taburi obligatorii:

1. `Evoluție și prognoză`
2. `Variație zilnică`
3. `Temperatura apei`
4. `Prognoze anterioare`
5. `Evaluarea prognozelor`

Include și un modul separat `Compară stații`.

## 18. Graficul principal — Evoluție și prognoză

Acesta este elementul central al aplicației.

Pe aceeași axă temporală afișează:

- observațiile istorice: linie continuă albastră;
- observația cea mai recentă: marker mai mare;
- ultima ediție de prognoză: linie violet întreruptă;
- zona viitoare: fundal violet foarte pal;
- linie verticală la momentul relevant;
- etichete clare `Observat` și `Prognozat`.

Folosește aceeași axă Y, în cm față de mira stației.

Nu conecta artificial zilele lipsă.
Folosește `connectgaps: false`.

### Particularitatea ediției de prognoză

Ultima ediție de prognoză poate avea puncte-țintă care au trecut deja și pentru care există observații.

Afișează:

- punctele prognozate încă viitoare: linie întreruptă și marker plin;
- punctele prognozate deja realizate: marker conturat;
- observația corespondentă, dacă există;
- eroarea în tooltip.

### Tooltip observație

Include:

- data;
- nivel observat;
- variație 24 h;
- temperatură;
- stare calitate.

### Tooltip prognoză

Include:

- data-țintă;
- nivel prognozat;
- orizont;
- data emiterii;
- starea validării XML–HTML;
- observația și eroarea, dacă data a trecut.

## 19. Interval temporal și navigare

Deasupra graficelor:

- `7 zile`
- `30 zile`
- `90 zile`
- `1 an`
- `Tot`
- două date calendar: `De la` / `Până la`

Sub graficul principal activează un range slider temporal.

Reguli:

- în primele 30 de zile de arhivă: afișează tot istoricul;
- ulterior: implicit ultimele 30 de zile;
- intervalul selectat se păstrează între taburi;
- zoomul și deplasarea se păstrează când este posibil;
- buton `Resetare interval`.

## 20. Graficul variației zilnice

Grafic de bare:

- valori pozitive deasupra liniei zero;
- valori negative sub linia zero;
- zero pentru staționare;
- semne + / − / 0;
- tooltip cu:
  - data;
  - variația;
  - descriere textuală `creștere`, `scădere`, `staționare`;
  - nivelul rezultat.

Păstrează aceeași selecție temporală ca graficul principal.

## 21. Graficul temperaturii apei

Grafic separat:

- linie;
- marker zilnic;
- axă Y în °C;
- min/max pentru interval;
- tooltip exact;
- fără a suprapune temperatura pe axa nivelului.

Nu folosi o a doua axă peste graficul cotelor.

## 22. Prognoze anterioare

Creează un selector:

`Prognoză emisă la: [data]`

Pentru ediția selectată afișează:

- observațiile dinaintea emiterii;
- cele cinci puncte prognozate;
- observațiile realizate ulterior;
- diferența dintre prognoză și observație.

Utilizatorul trebuie să poată vedea:

- ce se prognoza la o dată trecută;
- ce s-a observat în realitate;
- eroarea pentru fiecare orizont.

Nu suprascrie edițiile vechi de prognoză.

## 23. Evaluarea prognozelor

Afișează pentru stația selectată:

- numărul de perechi;
- MAE;
- RMSE;
- bias;
- procent ±5 cm;
- procent ±10 cm;
- procent ±20 cm.

Afișează și un grafic pe orizonturi:

- 24 h
- 48 h
- 72 h
- 96 h
- 120 h

Poate fi un bar chart cu MAE sau RMSE.

Aplică pragurile de maturitate:

- sub 10: date insuficiente;
- 10–29: rezultate preliminare;
- minimum 30: rezultate normale.

## 24. Compararea stațiilor

Permite selectarea a maximum 4 stații.

Nu compara implicit cotele absolute.

Moduri obligatorii:

### A. Schimbare față de prima zi selectată

Pentru fiecare stație:

`nivel_zi - nivel_prima_zi`

Toate liniile pornesc din 0 cm.

### B. Variație zilnică

Compară direct variația în 24 h.

Poți adăuga ulterior un mod normalizat, dar nu este obligatoriu în prima versiune.

Afișează un mesaj metodologic clar:

`Cotele absolute sunt raportate la mire locale diferite și nu sunt direct comparabile între stații.`

## 25. Exportul fiecărui grafic ca PNG

Fiecare grafic trebuie să aibă în antet două butoane vizibile și stilizate:

- `Extinde`
- `Descarcă PNG`

Nu lăsa exportul ascuns numai în toolbar-ul implicit Plotly.

### Cerințe pentru PNG

Exportul trebuie să reflecte exact:

- stația sau stațiile selectate;
- graficul activ;
- intervalul vizibil;
- zoomul curent;
- seriile activate/dezactivate;
- ediția de prognoză selectată;
- titlul;
- legenda;
- unitățile.

Adaugă temporar în layoutul de export:

- titlul complet;
- intervalul;
- sursa;
- data generării.

Exemplu:

```text
GIURGIU — Evoluția nivelului și prognoza
Interval: 05.07.2026–03.08.2026

Sursa datelor: AFDJ; prognoze hidrologice publicate prin AFDJ
Generat: 03.08.2026 16:25 Europe/Bucharest
```

După export, restabilește layoutul interactiv.

Folosește o funcție comună bazată pe `Plotly.toImage()` sau `Plotly.downloadImage()`.

Cerințe tehnice:

- PNG;
- fundal alb;
- minimum aproximativ 1800 × 1000 px;
- scale 2×;
- legendă completă;
- fără butoanele interfeței în imagine;
- fără titluri tăiate;
- fără margini insuficiente.

Nume predictibile:

```text
nivel_dunare_giurgiu_evolutie_prognoza_2026-07-05_2026-08-03.png
nivel_dunare_giurgiu_variatie_2026-07-05_2026-08-03.png
nivel_dunare_giurgiu_temperatura_2026-07-05_2026-08-03.png
nivel_dunare_giurgiu_prognoza_emisa_2026-08-01.png
nivel_dunare_giurgiu_evaluare_prognoze.png
nivel_dunare_comparatie_giurgiu_braila_2026-07-05_2026-08-03.png
```

## 26. Fullscreen pentru grafice

Butonul `Extinde` trebuie să:

- deschidă graficul aproape full-screen;
- păstreze starea, zoomul, seriile și intervalul;
- permită în continuare download PNG și CSV;
- funcționeze pe desktop și mobil;
- se închidă prin buton, Escape și gest rezonabil pe mobil.

## 27. Fereastra Info

Creează un modal modern și accesibil care explică:

- ce reprezintă cota;
- ce reprezintă variația;
- ce reprezintă prognozele 24–120 h;
- faptul că mirele locale au zerouri de referință diferite;
- de ce cotele absolute între stații nu sunt direct comparabile;
- cum se selectează o stație;
- cum se schimbă perioada;
- cum se explorează prognozele vechi;
- cum se descarcă PNG și CSV;
- data de la care începe arhiva;
- sursa oficială;
- faptul că aplicația este informativă și nu înlocuiește comunicările oficiale pentru navigație.

Modalul trebuie să fie navigabil cu tastatura și să închidă corect focusul.

## 28. Tabelul stațiilor

Sub zona principală include un tabel modern:

- stație;
- km;
- nivel;
- variație;
- temperatură;
- data observației;
- data prognozei;
- stare.

Funcții:

- căutare;
- sortare;
- filtrare creștere/scădere/staționare/stale;
- clic pe rând → selectează stația pe hartă și în grafice;
- download CSV.

Ordinea implicită poate fi după km fluvial, explicată clar.

## 29. Stări de date și erori

Interfața trebuie să gestioneze elegant:

- date actualizate;
- sursă neactualizată azi;
- stație lipsă temporar;
- prognoză indisponibilă;
- zero ambiguu în XML;
- mismatch XML–HTML;
- eroare de încărcare;
- istoric insuficient;
- scoruri de prognoză insuficiente;
- interval fără date.

Nu afișa stack traces sau mesaje tehnice brute utilizatorului.

Afișează detalii tehnice numai într-o secțiune avansată din Info sau status.

## 30. GitHub Actions — colectare

Creează `.github/workflows/update-data.yml`.

Cerințe:

- `workflow_dispatch`;
- minimum două rulări programate zilnic, la minute care nu sunt `00`;
- timpi UTC suficient de târzii pentru a surprinde actualizarea sursei pe tot parcursul anului;
- scriptul rămâne idempotent, astfel încât rularea de siguranță să nu creeze duplicate;
- `permissions: contents: write`;
- `concurrency` pentru a evita două rulări simultane;
- checkout;
- setup Python;
- cache pip;
- instalare dependencies;
- rulare ingest;
- validare;
- construire date publice;
- teste;
- commit numai dacă există modificări;
- push pe `main`;
- artefacte de diagnostic la eșec;
- loguri clare.

Poți folosi, de exemplu, două ferestre UTC precum:

- `04:17 UTC`
- `07:23 UTC`

Documentează faptul că actualizarea publică poate apărea cu întârziere.

Commitul automat trebuie să aibă un mesaj clar, de exemplu:

`data: update AFDJ observations 2026-08-03`

Nu crea commit gol.

## 31. GitHub Actions — deploy Pages

Creează `.github/workflows/deploy-pages.yml`.

Cerințe:

- deploy din folderul `public`;
- rulează la push pe `main` când se modifică:
  - `public/**`
  - `data/public/**`
  - fișierele frontend;
- `workflow_dispatch`;
- `actions/configure-pages`;
- `actions/upload-pages-artifact`;
- `actions/deploy-pages`;
- permisiuni corecte:
  - `contents: read`
  - `pages: write`
  - `id-token: write`
- concurrency pentru Pages;
- copiază/sincronizează datele publice în `public/data` înainte de upload;
- nu publica arhiva tehnică internă decât prin linkuri explicite și controlate.

Configurează GitHub Pages să folosească GitHub Actions.

## 32. Teste obligatorii

Creează teste reale.

### Parser XML

- root corect;
- item-uri detectate;
- toate câmpurile critice;
- flattening complet;
- identificatori;
- coordonate;
- forecasturi.

### Normalizare

- numere negative;
- zero;
- virgulă/punct;
- whitespace;
- date ISO;
- timezone;
- valori lipsă;
- km;
- temperatură.

### Forecast availability

Testează toate cele cinci cazuri XML–HTML descrise mai sus, în special:

- XML 0 + HTML gol;
- XML 0 + HTML 0;
- XML nonzero + HTML gol;
- mismatch;
- HTML indisponibil.

### Idempotency

- aceeași captură rulată de două ori nu dublează observațiile;
- nu dublează prognozele;
- nu creează commit logic nou;
- hashurile sunt stabile.

### Schema evolution

- tag nou;
- tag lipsă;
- câmp critic lipsă;
- câmp necritic nou.

### Forecast scoring

- target date matching;
- MAE;
- RMSE;
- bias;
- praguri ±5/10/20.

### Public outputs

- JSON valid;
- CSV valid;
- GeoJSON valid;
- toate stațiile au coordonate;
- fișiere per stație existente;
- status valid;
- linkuri de download valide.

Rulează toate testele local înainte de commit.

## 33. Smoke test local

Creează un server local și un smoke test.

Pași:

1. pornește aplicația local;
2. verifică pagina principală;
3. verifică încărcarea `status.json`;
4. verifică `latest.geojson`;
5. verifică cel puțin trei stații;
6. verifică fișierele JSON per stație;
7. verifică lipsa erorilor HTTP 404 pentru resursele principale;
8. verifică faptul că pagina poate fi servită dintr-un subpath GitHub Pages.

Testează în special:

- harta;
- selectarea stației;
- graficul principal;
- schimbarea intervalului;
- taburile;
- popupul;
- tabelul;
- Info;
- fullscreen;
- butonul PNG;
- butonul CSV.

Dacă nu poți automatiza complet testul vizual, creează și completează un checklist manual în `docs/USER_GUIDE.md`.

## 34. Documentație

### README.md

Include:

- scop;
- captură de ecran dacă poate fi generată;
- sursa datelor;
- arhitectură;
- rulare locală;
- actualizare manuală;
- GitHub Actions;
- GitHub Pages;
- structura repository-ului;
- linkuri către CSV-uri;
- limitări;
- licență;
- disclaimer.

### DATA_DICTIONARY.md

Documentează:

- toate câmpurile canonice;
- unități;
- chei;
- valori raw/normalized;
- quality flags;
- forecast availability;
- target date;
- scoruri.

### ARCHITECTURE.md

Documentează fluxul:

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

### OPERATIONS.md

Include:

- rulare locală;
- rulare manuală GitHub Action;
- interpretarea logurilor;
- refacerea datelor publice;
- depanarea;
- schimbarea programului;
- tratarea unei modificări de schemă.

### FORECAST_METHODOLOGY.md

Explică:

- issue date;
- lead hours;
- target date;
- validarea XML–HTML;
- zero ambiguu;
- evaluarea prognozelor;
- formulele MAE/RMSE/bias;
- limitări.

### USER_GUIDE.md

Explică folosirea hărții, graficelor, selecției, comparației, PNG și CSV.

## 35. Licență și disclaimer

Adaugă o licență open-source adecvată pentru cod, preferabil MIT, dacă nu există deja o alegere în repository.

Adaugă disclaimer vizibil:

- datele provin din sursa publică AFDJ;
- prognozele sunt cele publicate prin sursa oficială;
- aplicația este informativă;
- nu înlocuiește avizele oficiale, informațiile de navigație sau deciziile autorităților;
- momentul afișării în aplicație poate fi ulterior momentului publicării la sursă.

Respectă atribuirea basemapului și a bibliotecilor.

## 36. Performanță

- nu încărca global toate datele istorice la startup;
- folosește fișiere per stație;
- păstrează JSON compact;
- lazy loading;
- cache în memorie;
- debouncing pentru resize și filtre;
- nu redesena harta inutil;
- nu recrea instanța Plotly complet la fiecare interacțiune dacă `Plotly.react` este suficient;
- nu bloca UI;
- păstrează funcționalitatea rezonabilă pentru mai mulți ani de date.

## 37. Accesibilitate

- contrast WCAG rezonabil;
- focus vizibil;
- navigare cu tastatura;
- ARIA labels;
- butoane cu text sau tooltip;
- harta are alternativă prin tabel;
- semnificația nu este transmisă numai prin culoare;
- modalul Info și fullscreen gestionează corect focusul;
- preferința `prefers-reduced-motion` este respectată.

## 38. Prima rulare și datele inițiale

După implementare:

1. rulează colectorul pe sursa live;
2. arhivează XML-ul;
3. generează flat raw cu toate tagurile;
4. generează observațiile;
5. generează prognozele în format lung;
6. rulează validarea HTML;
7. generează fișierele publice;
8. rulează testele;
9. pornește aplicația local;
10. efectuează smoke test;
11. verifică manual cel puțin:
    - Baziaș;
    - Orșova;
    - Giurgiu;
    - Galați;
    - Sulina.

Nu inventa istoric anterior primei capturi.
Folosește numai date reale disponibile.

Poți importa captura existentă din audit ca prima captură istorică numai dacă:

- XML-ul brut original este prezent;
- hash-ul este verificat;
- data capturii este cunoscută;
- importul este documentat ca provenind din audit;
- nu există risc de duplicare cu rularea live.

## 39. Git și commituri

Realizează commituri logice, de exemplu:

1. `chore: initialize Danube level monitoring project`
2. `feat: add AFDJ ingestion and archival pipeline`
3. `feat: add forecast history and verification`
4. `feat: add interactive map and station dashboard`
5. `feat: add chart PNG and CSV exports`
6. `ci: add scheduled data update and Pages deployment`
7. `docs: add architecture operations and user guides`

Nu face commit cu:

- credențiale;
- tokenuri;
- fișiere temporare;
- cache Python;
- medii virtuale;
- capturi inutile;
- loguri mari.

## 40. Criterii de acceptanță

Proiectul este considerat complet numai dacă:

- [ ] XML-ul live este descărcat și validat.
- [ ] Toate tagurile XML sunt păstrate în arhiva flat raw.
- [ ] Schema este monitorizată.
- [ ] Observațiile sunt arhivate idempotent.
- [ ] Prognozele 24–120 h sunt arhivate ca ediții istorice.
- [ ] Zero-urile ambigue sunt tratate prin verificarea HTML.
- [ ] Coordonatele sunt folosite în hartă.
- [ ] Harta este modernă, responsive și sincronizată cu graficele.
- [ ] Graficul principal combină observațiile și prognoza.
- [ ] Variația are grafic separat.
- [ ] Temperatura are grafic separat.
- [ ] Prognozele anterioare pot fi explorate.
- [ ] Evaluarea prognozelor este implementată.
- [ ] Comparația între stații este implementată în moduri metodologic corecte.
- [ ] Intervalele 7/30/90/365/tot și datele custom funcționează.
- [ ] Range sliderul funcționează.
- [ ] Zilele lipsă nu sunt conectate artificial.
- [ ] Fiecare grafic poate fi extins.
- [ ] Fiecare grafic poate fi descărcat individual ca PNG high-resolution.
- [ ] Datele vizibile pot fi descărcate ca CSV.
- [ ] Descărcările globale funcționează.
- [ ] Interfața este în română.
- [ ] Designul este modern și coerent.
- [ ] Accesibilitatea de bază este implementată.
- [ ] Testele trec.
- [ ] GitHub Actions actualizează datele.
- [ ] GitHub Pages publică aplicația.
- [ ] README și documentația sunt complete.
- [ ] Repository-ul este publicat.
- [ ] URL-ul GitHub Pages este funcțional.

## 41. Raportul final Codex

La final, afișează un raport clar cu:

1. repository-ul local;
2. repository-ul GitHub;
3. URL-ul GitHub Pages;
4. branch-ul;
5. ultimul commit;
6. lista principalelor fișiere create;
7. structura datelor;
8. numărul stațiilor colectate;
9. data observațiilor;
10. data ediției de prognoză;
11. numărul observațiilor canonice;
12. numărul prognozelor canonice;
13. zero-uri ambigue identificate;
14. mismatchuri XML–HTML;
15. rezultate teste;
16. rezultate smoke test;
17. status GitHub Actions;
18. status deploy Pages;
19. limitări sau probleme rămase;
20. comenzile exacte pentru:
    - rulare locală;
    - actualizare manuală;
    - pornire server local;
    - rerulare teste.

Nu te opri la generarea fișierelor. Rulează, verifică, publică și raportează rezultatul.
