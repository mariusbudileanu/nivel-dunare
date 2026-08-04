# Audit tehnic al surselor oficiale dunărene

Data auditului: 2026-08-04. Acesta este un audit tehnic read-only, nu o integrare de producție și nu o analiză juridică. Probele brute sunt locale, sub `_audit_source/danube_international/20260804T100138Z/`, ignorate de Git. User-Agent: `NivelDunareResearchAudit/1.0 (+https://github.com/mariusbudileanu/nivel-dunare)`. Fiecare probă HTTP principală a folosit un singur GET, fără retry, cookie, proxy, stealth sau ocolirea controalelor.

## Metodă și limite

Ordinea investigației a fost: documentație oficială, endpoint structurat, HTML/JavaScript, apoi o singură navigare Chromium unde a fost necesară descoperirea requesturilor. Statutul `official` înseamnă că URL-ul este pe domeniul instituției; `documented` cere documentație instituțională explicită. Un JSON intern nu este numit API stabil. Statusurile GitHub/Hetzner sunt `not-tested` în afara AFDJ; nu sunt extrapolate din rezultatul local.

Fișierele locale per sursă conțin cererea, antetele, corpul brut, hashul, schema, eșantionul de stații, DNS mascat și sumarul. IP-urile sunt mascate în rapoarte. Conținutul dinamic a fost inspectat cu profil Chromium nou, fără cookie-uri reutilizate. Pentru paginile APPD curente și forecast, browserul a confirmat HTML server-rendered și absența requesturilor XHR/fetch pentru date.

## Inventarul documentației oficiale

Toate paginile de mai jos au fost accesate la 2026-08-04. Citatul este deliberat scurt; concluzia nu extinde sensul textului instituțional.

| Țară | Document / limbă / statut | Citat tehnic scurt | Concluzie | Neclaritate |
|---|---|---|---|---|
| DE | PEGELONLINE REST Webservice / DE / documentație oficială curentă | „REST-API” și resurse versionate v2 | API stabil; JSON și resurse timeseries | SLA/rate limit numeric |
| DE | HyDAS / DE / beta 0.1.0 | „test and evaluation purposes” | nu se recomandă pentru producție | calendarul stabilizării |
| DE | Downloads, FAQ, WFS / DE / oficial | „DL-DE-Zero-2.0” | download/OGC și licență explicită | acoperire per timeseries |
| AT | RIS Open Services / EN-DE / oficial | „test without registration” | cheia `opendata` este pentru portalul de test | acordul de republicare |
| AT | OpenAPI Opendata / EN / contract oficial | query `VIADONAU_PARTNER_KEY` | list/status/forecast sunt documentate | rate limit/SLA |
| SK | SHMÚ Water levels / EN / pagină oficială | „operational and unchecked” | date curente + temperatură, contract HTML | licență, API, datum |
| SK | SHMÚ forecast / SK / pagină oficială | „updated four times a day” | prognoze 48 h | schema/termeni |
| HU | Hydroinfo Danube / EN / tabel oficial | antete nivel, variație, debit, temperatură | 25 HU primare, restul republicate | licență/API |
| HR | Water levels / EN / aplicație oficială | „Water levels” | scriptul oficial cheamă JSON intern | contractul endpointului și staleness |
| HR | FAIRway forecast / EN / informare oficială | „maximum of five days” | prognoza descrisă nu este feed stabil | acces/reutilizare |
| RS | RHMZ current conditions / EN / portal oficial | „Forecast for 2 to 4 days” | pagini oficiale pentru nivel/debit/temp/prognoză | API, timezone, licență |
| BG | APPD hydrology + forecasts + Open Data / EN / oficial | tabele „water level”, „discharge”, „forecast”, plus date istorice | HTML curent și forecast separat de arhiva PDF | ID-uri stație, unitate/ediție forecast |
| RO | AFDJ Cotele Dunării + XML / RO / feed oficial neversionat | câmpuri Drupal/XML publice | 23 stații și prognoze 24–120 h | licență/API formal |

Nu au fost identificate în mod demonstrat servicii CKAN/DCAT/SPARQL/SensorThings/GraphQL pentru aceste fluxuri. Pentru DE sunt demonstrate REST, download, WFS/WMS/SOS; pentru AT, RIS/OpenAPI. Absența din audit nu dovedește inexistența.

## Robots și contacte

S-a făcut exact o cerere `robots.txt` per domeniu, cu User-Agent transparent și pauză de o secundă. Rezultatul descrie politica crawlerelor, nu acordă sau retrage drepturi de reutilizare și nu înlocuiește termenii.

| Domeniu | HTTP / rezultat observat | Impact conservator | Contact public pentru clarificare |
|---|---|---|---|
| pegelonline.wsv.de | 404, fără politică robots disponibilă | se aplică volum minim și documentația serviciului | contactul WSV/PEGELONLINE din portal |
| doris.bmimi.gv.at | 404 HTML | folosește numai OpenAPI și cheia autorizată | `doris-info@viadonau.org` pentru partner key |
| shmu.sk | 200; interzice `/data/` și `/api/`, nu pagina HTML auditată | nu s-au accesat rutele interzise | contact SHMÚ public |
| hydroinfo.hu | 404 HTML | audit minim al tabelului public | contact OVF/Hydroinfo public |
| vodniputovi.hr | 200 dar corp HTML, nu reguli robots valide | nu se interpretează ca permisiune | contact Agencija za vodne putove |
| hidmet.gov.rs | 200, `Disallow:` gol | audit minim al paginilor oficiale | contact RHMZ public |
| appd-bg.org | 200 dar corp HTML, nu reguli robots valide | numai indexul și documentele linkate | contact APPD public |
| afdj.ro | 200 Drupal robots; rutele publice auditate nu sunt interzise | rămâne valabilă limitarea și blocarea GitHub cunoscută | contact AFDJ public |

Fișierele robots brute sunt păstrate numai local, ignorate de Git. Unde adresa tehnică exactă nu a fost publicată în documentația accesată, auditul nu inventează un e-mail; recomandarea este solicitarea prin pagina instituțională de contact, cerând explicit acces automat, frecvență, caching, atribuire și republicare.

## Probe suplimentare ale URL-urilor inițiale

| Țară | Status / URL final | Tip / bytes | SHA-256 | Concluzie |
|---|---|---|---|---|
| DE | 200 / același URL | HTML / 11,769 | `2152d6995d7e0daffedde09500016dded14cf3f92f9586f4841bdba90649e230` | aplicație; REST este preferat |
| AT | 200 / domeniul curent `doris.bmimi.gv.at` | HTML / 32,691 | `23cd2804da2948932472e935cfa0046771ea5c547d821e22d47551593e0fcc7e` | portal; OpenAPI este sursa structurată |
| SK | 200 / același URL HTTP | frameset Windows-1250 / 711 | `6931d5fde7b3eb4c83ce1fcfa6d7c7e79cc9acb57ef7ab39dd144f700fae14c3` | serviciu legacy încă accesibil; SHMÚ este preferat |
| HU | 200 / HTTPS | HTML / 8,736 | `a5dc5fcc2e3ffd79c7657288827587ed0bbe44ae497e0b6a24dbf2999c6b6ee4` | navigare; tabelul `dunhif` este preferat |
| HR | 200 / același URL | HTML / 9,854 | `3948332ff8db21553df5ca606321ea24b0c4d824cd5f6844742df55bd401e5a8` | browserul a descoperit JSON-ul intern |
| RS | 200 / HTTPS | HTML / 21,010 | `8a5b2b3cfe3c4a2c45ebc57bbaaf109d25de9cbf7aaf976c46ac9d981a05c7c7` | portal; subpagina hidrologică este preferată |
| BG | 301→200 / homepage | HTML / 55,043 | `abb7d2fb510622a0dd1926b375ec55e2cc6d4847033a2d547ed077103c68f436` | ruta `exploration` este legacy |
| RO | 200 local / pagina AFDJ | HTML | vezi arhiva existentă de validare XML–HTML | nu s-a repetat auditul Cloudflare complet |
## Portaluri și surse oficiale alternative

- DE: PEGELONLINE REST, downloads și OGC; HyDAS numai beta. Datele viadonau din răspuns sunt republicări, nu devin date WSV.
- AT: DoRIS RIS Open Services și OpenAPI; cheia permanentă se solicită instituției.
- SK: SHMÚ este succesorul oficial folosit; URL-ul Povodia inițial nu este considerat endpoint actual echivalent.
- HU: Hydroinfo web/mobile; rândurile externe sunt agregare/validare.
- HR: pagina Agencija și portalul mobil Hrvatske vode sunt distincte; proveniența nu se combină automat.
- RS: paginile engleză/sârbă RHMZ și subpaginile `prognoza`, `bezprognoza`, `opseg`.
- BG: APPD are trei canale distincte: `hidrology-en` pentru current, `forecasts-en` pentru prognoze și Open Data pentru arhiva PDF; ruta veche `exploration` este retrasă/redirecționată.
- RO: XML și HTML AFDJ; arhiva locală a proiectului este derivată, nu sursă instituțională alternativă.
## Rezumat demonstrat

| Țară | Furnizor | Endpoint recomandat pentru audit/integrări viitoare | Local | Corp | Stații/rânduri Dunăre | Clasă | Recomandare |
|---|---|---|---:|---|---:|---|---|
| DE | WSV PEGELONLINE | REST v2 `stations.json?waters=DONAU` + timeseries | 200 | JSON | 27 (18 WSV, 9 viadonau republicate) | A/G | prima integrare, filtrând `agency` |
| AT | viadonau DoRIS | OpenAPI `/gauge/list` și `/gauge/status` | 200 | JSON | 10 | A | prima integrare după cheie permanentă și confirmarea reutilizării |
| SK | SHMÚ | `hydro_vod_all` | 200 | HTML static | 13 | C | parser fragil; clarificare instituțională |
| HU | OVF Hydroinfo | `tables/dunhif.html` | 200 | HTML static | 93 (25 primare, 68 republicate) | C/G | sursă primară numai pentru ID-urile HU; restul validare |
| HR | Agencija za vodne putove | `getwaterstuff.php` intern | 200 | JSON | 3 | D | nu integra: răspunsul era stale la audit |
| RS | RHMZ | `hidrologija/izvestajne/index.php` | 200 | HTML static | 13 | C | prototip după clarificarea termenilor |
| BG | APPD | `hidrology-en`; `forecasts-en`; Open Data | 200 | HTML UTF-8 + PDF | 8 main + 12 auto; 5 forecast; 6 istoric | C/C/E | parser conservator partial + fixtures și schema alert |
| RO | AFDJ | `/tabel_cotele_dunarii/xml` | 200 local | XML | 23 | B | păstrează ingestia existentă pe Hetzner |

Numărul nu este o deduplicare a stațiilor fizice. PEGELONLINE și Hydroinfo republică stații străine, iar inventarul păstrează proveniența.

## Germania — PEGELONLINE / WSV

1. Instituție: Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV); serviciu: PEGELONLINE.
2. Endpoint: REST API v2, oficial și documentat. Lista auditată a întors 27 rânduri `DONAU`; câmpul `agency` separă 18 stații WSV de 9 rânduri operate de viadonau.
3. Identificatori: UUID, număr, shortname/longname. Formate: JSON pentru resurse, CSV/PNG pentru măsurători; servicii WFS/WMS/SOS și download sunt documentate separat.
4. Date: nivel curent și serii, debit/temperatură unde există timeseries, coordonate, kilometru, gauge zero și datum. REST păstrează maximum 31 de zile/30 de zile per solicitare conform secțiunii folosite; serviciul download oferă perioade mai mari și date nevalidate.
5. Timp: timestampurile și intervalele sunt furnizate de timeseries; documentația download avertizează că timestampurile sunt CET inclusiv vara. Normalizarea trebuie să păstreze regula sursei, nu să presupună CEST.
6. Calitate: datele curente pot fi nevalidate; lipsa timeseries trebuie tratată ca disponibilitate parțială, nu zero.
7. HyDAS este declarat beta/test (`0.1.0`) și pagina recomandă REST stabil pentru producție; nu este recomandat.
8. Reutilizare: DL-DE-Zero-2.0 este explicită în FAQ. Rate limit numeric neidentificat; ETag/cache și paginare `limit/offset` sunt documentate.
9. Probă: HTTP 200, JSON, 25,009 bytes, SHA-256 `f599fde0b9117b5fc3154663119b294777ba922fe1ae397c80b16ddbc70ab75a`.
10. Încredere: ridicată pentru API și licență; medie pentru acoperirea tuturor mărimilor pe fiecare stație.

Dovezi: [REST](https://www.pegelonline.wsv.de/webservice/dokuRestapi), [HyDAS beta](https://www.pegelonline.wsv.de/webservice/hydas), [downloads](https://www.pegelonline.wsv.de/webservice/downloads), [FAQ/licență](https://www.pegelonline.wsv.de/webservice/faq), [WFS](https://www.pegelonline.wsv.de/webservice/wfsAktuell).

## Austria — viadonau / DoRIS

1. Instituție: viadonau – Österreichische Wasserstraßen-Gesellschaft mbH; serviciu: DoRIS RIS Open Services.
2. Pagina DoRIS este portal/documentație; datele sunt servite de `opendata2.doris-info.at`. OpenAPI documentează query security `VIADONAU_PARTNER_KEY`.
3. Portalul de test publică cheia demonstrativă `opendata`; fără cheie, aceeași rută a întors 403 JSON `Partner key required`. Pentru utilizare permanentă trebuie solicitată cheie partener, deci cheia de test nu este o soluție de producție.
4. Gauge list: 10 rânduri, incluzând Schwedenbrücke pe Donaukanal; câmpuri `objectID`, nume, km, lat/lon, `zpg` în metri peste Adriatic Sea, praguri/caracteristici și `hasForecast`.
5. Gauge status: nivel curent în cm, diferență, `measureDate`, istoric și prognoze cu valoare/min/max. Debitul/temperatura nu au fost demonstrate în endpointurile auditate.
6. Probă cu cheia publică de test: 200 JSON, 2,443 bytes, SHA-256 `88098e7d4eb53b8e10fc67c7155cba394ab6fcdc02d99e81979301916ef49dda`.
7. Termeni: portalul numește serviciul open, dar păstrează un disclaimer de fiabilitate și cere cheie pentru utilizare permanentă. Republicarea automatizată și atribuirea necesită confirmare scrisă.
8. Încredere: ridicată pentru schemă/autentificare; medie pentru condițiile de reutilizare.

Dovezi: [RIS Open Services](https://www.doris.bmimi.gv.at/services/ris-open-services), [Swagger UI](https://opendata2.doris-info.at/swagger-ui/index.html), [OpenAPI JSON](https://opendata2.doris-info.at/v3/api-docs/Opendata).

## Slovacia — SHMÚ

1. URL-ul vechi Povodia nu a fost tratat ca sursă curentă; succesorul oficial identificat este Slovenský hydrometeorologický ústav (SHMÚ).
2. Endpointul este un tabel HTML semantic server-rendered, nu un API documentat. Au fost extrase 13 opțiuni Dunaj cu ID instituțional.
3. Pagina expune nivel și temperatură a apei la 15 minute și marchează datele drept operative/necontrolate. Pagina oficială de prognoze descrie profile la 48 h actualizate de patru ori pe zi.
4. Istoricul structurat, descărcarea bulk, coordonatele, km, gauge zero/datum și termenii pentru republicare automată nu au fost demonstrate.
5. Probă: 200, `text/html`, 113,046 bytes, SHA-256 `c8fd871523fe66ff00f839c6905892c535a9df36d917f24ead03c2a90b4f5c7b` (hashul complet se află în proba locală).
6. Clasă C; integrare numai după fixture-uri de regresie și clarificarea reutilizării. Încredere medie.

Dovezi: [niveluri SHMÚ](https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id=5140), [prognoze SHMÚ](https://www.shmu.sk/sk/index.php?id=hydro_vod_forecast&page=1&sort=sn-asc).

## Ungaria — OVF Hydroinfo

1. Furnizor: Országos Vízügyi Főigazgatóság (OVF), Hydroinfo.
2. Tabelul Dunării este HTML static. Au fost identificate 93 rânduri: 25 cu ID-uri maghiare (prefix `4`) și 68 străine republicate. Doar primele sunt candidate ca sursă primară HU; celelalte sunt clasa G pentru validare.
3. Câmpuri: cod, stație, râu, nivel seara precedentă/dimineața, variație, debit, temperatură, gheață. Pagina mobilă publică prognoze pe șase zile.
4. Nu a fost găsit un API oficial documentat. Coordonate, gauge zero/datum, istoric bulk și licență explicită nu au fost demonstrate.
5. Probă: 200 HTML, 303,091 bytes, SHA-256 `5e1308a42817c07edfaedbf4e105f41f3a42c18db705e168e5ed8ac761b840a6`; 25 stații primare enumerate în inventar.
6. Clasă C/G. Integrarea trebuie să păstreze `source_provider` și rolul `primary/republished`. Încredere ridicată pentru separare, medie pentru stabilitatea HTML.

Dovezi: [tabel Dunăre](https://www.hydroinfo.hu/tables/dunhif.html), [niveluri mobile](https://www.hydroinfo.hu/mobil/en/hydro.php), [prognoze](https://www.hydroinfo.hu/mobil/en/hydroinfo.php), [informații](https://www.hydroinfo.hu/mobil/en/hidro/info.php).

## Croația — Agencija za vodne putove

1. Pagina oficială dinamică execută un GET fără parametri către `dhmz_vodostaji/getwaterstuff.php` și afișează Aljmaš, Batina și Vukovar.
2. Browserul real a confirmat requestul intern; endpointul a întors JSON cu ID-urile 5001, 5170, 5070 și câte 10 înregistrări.
3. La 2026-08-04, cele mai noi date din răspuns erau 2026-03-12. Proba JSON: 1,685 bytes, SHA-256 `564293d6c1b4e1587f49d88bac5326bba7b0fd2db5f364cb8f319a973e855dee`. Acest fapt demonstrat exclude folosirea curentă în producție până la remedierea/confirmarea instituțională.
4. Pagina FAIRway descrie prognoze de până la cinci zile și avertizează că sunt utile pentru ape mici, nu pentru ape mari. Scriptul paginii include praguri locale, dar nu dovedește datum/coordonate/licență.
5. Hrvatska voda are un portal mobil oficial distinct; Dalj și Ilok sunt păstrate în inventar ca stații oficiale posibile, nu ca rânduri ale endpointului auditat.
6. Clasă D. Nu integra acum; încredere ridicată pentru staleness și descoperirea endpointului, joasă pentru stabilitatea contractului intern.

Dovezi: [water levels](https://www.vodniputovi.hr/en/services/waterlevels/), [FAIRway forecast](https://vodniputovi.hr/en/eu-projects/fairway/water-level-forecast-available-in-croatia/), [Hrvatske vode mobile](https://mvodostaji.voda.hr/).

## Serbia — RHMZ

1. Furnizor: Republic Hydrometeorological Service of Serbia (RHMZ).
2. Pagina de stații de raportare este HTML static și a furnizat 13 stații DUNAV cu ID-uri `hm_id`. Linkurile separă stații cu prognoză, fără prognoză și cu interval.
3. Portalul descrie starea zilnică/anuală, ultimele 30 zile, prognoze 2–4 zile, debit, temperatură și valori caracteristice; nu a fost găsit un API oficial documentat.
4. Alfabetul original trebuie păstrat, iar transliterarea trebuie stocată ca alias, nu suprascrisă. Fusul orar și termenii automați nu au fost demonstrați.
5. Probă: 200 HTML, 73,556 bytes, SHA-256 `7c9369f22882c6c10ff666a829d6613809a74a9bbf9e27006bf7068ee68663ca`.
6. Clasă C; integrare după testarea paginilor secundare și clarificarea reutilizării. Încredere medie.

Dovezi: [overview](https://www.hidmet.gov.rs/eng/hidrologija/naslovna_stanje.php), [reporting stations](https://www.hidmet.gov.rs/eng/hidrologija/izvestajne/index.php), [radio hydrology](https://hidmet.gov.rs/eng/hidrologija/radio.php).

## Bulgaria — APPD / EAEMDR

1. Furnizor: Executive Agency for Exploration and Maintenance of the Danube River (EAEMDR/APPD). Au fost reauditate separat tabelul curent, prognozele și arhiva Open Data; furnizorul nu mai este clasificat exclusiv E.
2. `https://www.appd-bg.org/hidrology-en` este HTML semantic server-rendered, în engleză, UTF-8, fără API JSON/XML demonstrat și fără requesturi XHR/fetch pentru date. Ediția capturată are titlul datat `04.08.2026`.
3. Tabelul principal are 8 stații: Novo Selo, Vidin, Lom, Oryahovo, Nikopol, Svishtov, Ruse și Silistra. Câmpuri: stație, km, nivel cm, debit m³/s, diferență 24 h cm și temperatura apei °C. Debitul este gol la Vidin și Nikopol; celula goală se mapează la `null`, niciodată zero.
4. Tabelul automat are 12 stații: Novo Selo, Gomotartsi, Lom, Kozloduj, Oryahovo, Bajkal, Nikopol, Svishtov, Ruse, Ryahovo, Malak Preslavets și `Силистра`. Numele original chirilic este păstrat, iar aliasul ASCII este `Silistra`. Câmpuri: km, nivel, variația ultimelor 6 ore și temperatura apei. Variația este categorială prin `down.gif`, `nochange.gif`, `up.gif`, normalizată `down|no_change|up` cu raw-ul păstrat; nu este inventată o variație numerică.
5. Nota paginii spune că după 07:00 valorile gri reprezintă ziua precedentă până la introducerea celor curente, apoi valorile devin albastre. Aceasta este o regulă de calitate parțială, nu un timestamp per rând. Structura tabelului este semantică, dar neversionată și deci fragilă la schimbare.
6. `https://www.appd-bg.org/forecasts-en` este HTML oficial server-rendered. Publică Oryahovo, Nikopol, Svishtov, Ruse și Silistra, câte 6 date țintă (`DD.MM`), cu rânduri `min`, `forecast` (central) și `max`; aceleași valori sunt incluse în array-uri JavaScript inline. Nu este demonstrat un API.
7. Pagina forecast nu tipărește data ediției, anul țintă, unitatea sau referința nivelului și nu expune identificator instituțional al stației. Contextul sugerează nivel, dar `forecast_parameter`, unitatea și referința rămân indisponibile până la clarificare. Parserul poate arhiva raw și structura, dar adaptorul rămâne `partial`.
8. `https://www.appd-bg.org/pages-en?id=opendata` este indexul documentar separat: 55 linkuri PDF observate, inclusiv medii zilnice 2020–2025 pentru Novo Selo, Lom, Oryahovo, Svishtov, Ruse și Silistra și documente istorice de nivel/debit/temperatură. Acesta rămâne clasa E; PDF-urile nu sunt confundate cu current/forecast.
9. Termenii Open Data cer atribuirea clară și vizibilă a EAEMDR inclusiv pentru date procesate/agregate/combinate, indicarea explicită a transformărilor, prezentarea nedistorsionată a perioadei și domeniului și interzic reprezentarea înșelătoare. Folosirea comercială/promoțională a mărcii/logo-ului cere consimțământ scris.
10. Probe locale, câte un GET fără retry: hydrology 200, 74.033 bytes, SHA-256 `f642c1d8298e18b3512429c8102a44cf3d63b1fcb866e14277cf67dc87f65b6c`; forecasts 200, 37.375 bytes, `d6b6f22491e438f149499c2ffd7d903313fdd6b2d2bc1f28b36115d67115d0ac`; Open Data 200, 34.004 bytes, `ff158f705314554995ad217d6e5289637e30dad80e4170aa9acbab0948f3f590`.
11. Clasificare finală: C pentru hidrologie curentă, C pentru forecast, E pentru arhiva PDF. Încredere ridicată pentru conținutul capturat și separarea canalelor; medie pentru stabilitatea HTML; necunoscut pentru ID-urile instituționale și metadatele forecast absente.

Dovezi: [hidrologie curentă](https://www.appd-bg.org/hidrology-en), [prognoze](https://www.appd-bg.org/forecasts-en), [Open Data și termeni](https://www.appd-bg.org/pages-en?id=opendata).

## România — AFDJ, etalon

1. Endpointul XML oficial furnizează 23 stații, nume/UUID, km, nivel, variație, temperatură, date și prognoze 24–120 h; HTML-ul este folosit în pipeline pentru verificare. Datele existente includ coordonate, dar gauge zero/datum vertical nu este furnizat de feedul auditat.
2. Rezultat cunoscut, fără repetarea investigației Cloudflare: local 200; Hetzner 200; GitHub-hosted Ubuntu/Windows/macOS și Chromium 403 block page Cloudflare.
3. Rularea Hetzner demonstrată anterior: 23 stații; `observation_date=2026-08-04`; `forecast_issue_date=2026-08-03`; `ambiguous_zero_count=40`; `xml_html_mismatch_count=0`.
4. Probă locală din acest audit: 200 XML, 62,540 bytes, SHA-256 `ee17f15dad710a992b22fe8e1d19d6242732d1c61b5088d0768452c0738a163d`.
5. Clasă B: endpoint oficial structurat, fără documentație API/versionare formală. Reutilizarea/atribuirea necesită clarificare instituțională. Încredere ridicată pentru schema observată și diferența de acces, medie pentru stabilitate juridică.

Dovezi: [pagina AFDJ](https://afdj.ro/ro/cotele-dunarii), [XML AFDJ](https://afdj.ro/ro/tabel_cotele_dunarii/xml), raportul existent `docs/AFDJ_403_DIAGNOSTIC_REPORT.md`.

## Separarea concluziilor

### DEMONSTRAT

- La 2026-08-04, endpointurile recomandate au răspuns local cu 200 și corpurile/formatele din tabel.
- PEGELONLINE și DoRIS au documentație oficială structurată; HyDAS este beta.
- DoRIS cere partner key; cheia publică este de test, iar lipsa cheii întoarce 403 JSON.
- Hydroinfo amestecă stații HU primare și străine republicate.
- JSON-ul croat era vechi cu aproape cinci luni.
- APPD publică HTML semantic oficial pentru current și forecast, separat de arhiva PDF; clasificarea este C/C/E.
- AFDJ: local și Hetzner 200, GitHub-hosted 403, conform auditului anterior.

### PROBABIL

- HTML-urile SHMÚ, Hydroinfo și RHMZ pot fi parsate conservator cu fixture-uri și monitorizare de schemă.
- DoRIS ar fi operațional robust după obținerea cheii permanente.

### NECUNOSCUT

- Rate limits numerice pentru majoritatea surselor; disponibilitatea exactă per câmp și stație; SLA; retenția completă; fusul orar când nu este declarat; motivele tehnice pentru lipsa datelor croate recente.
- Accesul din GitHub și Hetzner pentru toate sursele, cu excepția AFDJ.

### NECESITĂ TEST HETZNER

- Aceeași comandă HTTP pentru DE/AT/SK/HU/HR/RS/BG, comparând status, hash, DNS și timp; instrucțiunile sunt în `DANUBE_HETZNER_AUDIT_INSTRUCTIONS.md`.

### NECESITĂ CLARIFICARE INSTITUȚIONALĂ

- Reutilizarea/republicarea pentru AT, SK, HU, HR, RS și RO; aplicabilitatea exactă a termenilor APPD asupra redistribuirii automate current/forecast; acces permanent DoRIS; contractul și actualitatea endpointului HR; ID-urile și metadatele forecast APPD; API/descărcare oficială pentru SHMÚ, Hydroinfo și RHMZ.

## Recomandare

Ordinea operațională este: AFDJ RO imediat pe Hetzner fără refactor disruptiv; apoi adaptor nou PEGELONLINE DE; APPD BG cu parser conservator și fixtures; DoRIS AT după cheie/acord; SHMÚ SK; RHMZ RS; Hydroinfo HU numai primar pentru HU și validator extern; Croația suspendată. AFDJ intră în `SourceAdapter` numai după paritate, iar frontendul multi-provider este ulterior.