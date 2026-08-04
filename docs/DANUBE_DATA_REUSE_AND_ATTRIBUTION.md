# Reutilizare și atribuire

Analiză tehnică la 2026-08-04, nu consultanță juridică. Accesibilitatea publică nu înlocuiește termenii furnizorului.

| Furnizor/titular | Licență/termeni demonstrați | Atribuire/transformări | Recomandare |
|---|---|---|---|
| WSV PEGELONLINE | DL-DE-Zero-2.0 | proveniență tehnică păstrată | integrare permisă |
| viadonau DoRIS | open services + disclaimer; test key public | republicarea necesită clarificare | partner key și răspuns scris |
| SHMÚ | date operative/necontrolate; licență neidentificată | necunoscut | clarificare |
| OVF Hydroinfo | licență explicită neidentificată | separă OVF de sursele străine | clarificare |
| Agencija/Hrvatske vode | endpoint intern și contract neclar | nu redistribui ca feed fără acord | suspendat |
| RHMZ Serbia | termeni automați neidentificați | păstrează instituția și starea datelor | clarificare |
| EAEMDR/APPD Bulgaria | termeni expliciți pe pagina Open Data | atribuire și indicarea transformărilor obligatorii | parser candidat cu respectarea exactă a termenilor |
| AFDJ România | feed public, fără licență explicită identificată | păstrează AFDJ, momentul și transformările | clarificare |

## Termenii APPD/EAEMDR demonstrați

Pagina oficială Open Data stabilește condiții aplicabile datelor primare și datelor prelucrate/agregate/combinate:

1. EAEMDR trebuie indicată clar și vizibil ca sursă a datelor primare.
2. Originea, acuratețea ori statutul oficial nu pot fi prezentate în mod înșelător și reputația instituției nu poate fi afectată.
3. Orice transformare trebuie indicată explicit, iar utilizatorul răspunde pentru corectitudinea rezultatului.
4. Folosirea comercială/promotională a mărcii sau logo-ului necesită consimțământ scris explicit.
5. Redistribuirea originalului neprelucrat nu trebuie să distorsioneze valorile și trebuie să prezinte corect perioada și domeniul în forma publicată.
6. Pagina menționează cadrul dreptului bulgar și directivele UE; acest audit nu interpretează efectul juridic dincolo de textul publicat.

Pentru integrare, atribuirea minimă propusă este: `Source: Executive Agency for Exploration and Maintenance of the Danube River (EAEMDR/APPD), <source URL>, captured <UTC>. Transformed by nivel-dunare; transformation: <description>; source period/scope: <as published>.` Logo-ul nu se folosește fără consimțământ.

Datele HTML curente și forecasturile sunt canale operaționale distincte de arhiva Open Data/PDF. Termenii sunt publicați pe pagina Open Data și sunt referința demonstrată pentru regulile de atribuire; implementarea trebuie totuși să confirme instituțional aplicabilitatea exactă asupra redistribuirii automate a paginilor curente.

## Reguli conservatoare comune

- Pentru fiecare valoare: link sursă, rolurile operator/source/captured-via, moment captură, hash și transformare.
- Nu republica documentația sau corpurile brute în Git; arhivele operaționale au retenție și acces controlat.
- Nu folosi cheia DoRIS `opendata` ca acces permanent.
- Nu atribui OVF datele stațiilor străine; Hydroinfo este `captured_via` pentru acele rânduri.
- Cere răspuns scris privind acces automat, frecvență, caching, republicare, atribuire, istoric și contact operațional acolo unde lipsesc.

## Dovezi

- PEGELONLINE: https://www.pegelonline.wsv.de/webservice/faq
- DoRIS: https://www.doris.bmimi.gv.at/services/ris-open-services
- SHMÚ: https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id=5140
- Hydroinfo: https://www.hydroinfo.hu/tables/dunhif.html
- Croația: https://www.vodniputovi.hr/en/services/waterlevels/
- Serbia: https://www.hidmet.gov.rs/eng/hidrologija/naslovna_stanje.php
- Bulgaria current: https://www.appd-bg.org/hidrology-en
- Bulgaria forecasts: https://www.appd-bg.org/forecasts-en
- Bulgaria Open Data/terms: https://www.appd-bg.org/pages-en?id=opendata
- România: https://afdj.ro/ro/cotele-dunarii