# Plan de extindere a frontendului

Frontendul va continua să consume artefacte statice versionate din GitHub Pages; nu va apela Hetzner și nu va conține chei de furnizor.

## Experiență și informație

- Selector de țară și furnizor, cu URL reproducibil (`?country=de&provider=pegelonline_de&station=...`).
- Hartă cu toate stațiile, clustering/filtrare, sectoare ale Dunării și legendă distinctă pe furnizor și stare (`fresh/stale/error`). Stațiile transfrontaliere rămân entități separate până la un match revizuit.
- Card per stație: nume original/alias, nivel local, variație, debit, temperatură, prognoze și momentul ultimei actualizări; câmpurile indisponibile nu devin zero.
- Toggle între nivel local și nivel absolut numai când gauge zero și datum sunt cunoscute. Comparațiile locale afișează avertismentul: cotele la mire diferite nu sunt comparabile longitudinal.
- Grafic de prognoză cu issue time, lead time și bandă min/max; comparația între stații folosește variații/anomalii sau același datum.
- Filtre accesibile din tastatură, stare loading/error per furnizor, unități și timezone vizibile.

## Transparență

Pagină metodologică per furnizor: instituție, endpoint, clasă, actualizare, calitate, conversii, licență/atribuire și link oficial. Footer/exports păstrează sursa și mențiunea transformărilor. Export CSV/JSON cu schema version, provider și capture time.

Starea globală nu ascunde erorile parțiale: fiecare furnizor are `last_attempt`, `last_success`, `data_time` și mesaj. Dacă o sursă este stale, markerii pot rămâne vizibili dar marcați și excluși implicit din comparații curente.

## Compatibilitate AFDJ

Ruta și forma actuală AFDJ rămân compatibile. Un manifest nou poate lista furnizorii și versiunile, iar loaderul folosește adaptor de prezentare. Lansarea se face feature-flagged: întâi manifest fără schimbare vizuală, apoi selector, hartă multinațională și comparații.

## Infografic și partajare

Slide infografic generat din date publice, QR către URL-ul filtrat, minimapă a stației și link permanent bazat pe `global_station_id`. QR-ul nu conține date dinamice sau tokenuri. Capturile/slide-urile includ timestamp, sursă și avertisment de comparabilitate.

## Performanță și accesibilitate

Fișiere separate per țară/provider, manifest mic, cache cu hash de conținut, lazy loading pentru serii. Marcatori virtualizați/clusterizați, contrast și text alternativ, tabel alternativ hărții, preferința reduced-motion. Nicio dependență runtime de VM-ul Hetzner.