# Roadmap de implementare a surselor Dunării

Auditul este read-only. Ordinea operațională este separată de dezvoltarea modelului canonic: AFDJ nu așteaptă finalizarea sistemului multinațional.

## Ordine operațională

1. **România — AFDJ:** automatizarea imediată a pipeline-ului existent pe Hetzner, cu cinci rulări zilnice, fără refactorizare disruptivă și fără schimbarea outputurilor.
2. **Germania — PEGELONLINE:** primul adaptor API nou; REST v2, UUID și licență clară.
3. **Bulgaria — APPD:** parser conservator separat pentru hidrologie și prognoze, fixture-uri, schema fingerprint și alarmă la schimbarea HTML.
4. **Austria — DoRIS:** numai după partner key permanent și clarificarea reutilizării.
5. **Slovacia — SHMÚ:** parser HTML după clarificarea termenilor.
6. **Serbia — RHMZ:** parsere per pagină, cu timezone și reutilizare clarificate.
7. **Ungaria — Hydroinfo:** sursă primară numai pentru stațiile HU; validator extern pentru rândurile republicate.
8. **Croația:** suspendată până când datele sunt actuale și contractul endpointului este clarificat.

## Ordinea dezvoltării modelului

### Faza 0 — audit și probe

Inventare cu proveniență, endpointuri distincte, contracte minime, termeni și teste. Acceptare: referințe valide, lipsă→`null`, nicio modificare de producție.

### Faza 1 — infrastructură comună fără migrarea AFDJ

Schema canonică versionată, rolurile provider, metadate temporale, `SourceAdapter`, arhivare/hash, stare per sursă, lock, staging, fixtures și alerte. Un adaptor fake trebuie să poată eșua fără a bloca altul.

### Faza 2 — adaptoare noi

PEGELONLINE DE, apoi APPD BG. APPD rămâne `partial` până când sunt rezolvate ID-ul stației și metadatele forecast lipsă. DoRIS AT urmează numai după cheia permanentă și acord.

### Faza 3 — paritate și migrarea opțională AFDJ

Se compară adaptorul candidat AFDJ cu fluxul existent pentru toate cele 23 de stații, zero ambiguu, prognoze și outputuri. Migrarea se face numai după paritate demonstrată; până atunci etapa A rămâne autoritatea operațională.

### Faza 4 — surse HTML fragile

SHMÚ, RHMZ și Hydroinfo. Parserele cer golden fixtures și fail-soft la schimbare. Hydroinfo nu preia rolul de sursă pentru rândurile străine.

### Faza 5 — validare încrucișată

Rândurile republicate sunt numai semnale de validare. Fără coordonate, km, ID sau metadate instituționale, `match_confidence=low|unknown` și `human_review_required=yes`.

### Faza 6 — frontend multi-provider

Manifest, selectoare, hartă, status, metodologie și comparații hidrometrice sigure, păstrând compatibilitatea AFDJ. Această fază este ulterioară și nu este modificată de audit.

## Plan per țară

| Țară | Poziție | Dependențe | Acceptare | Suspendare/oprire |
|---|---:|---|---|---|
| RO | 1 | Hetzner existent | 5 rulări, aceleași outputuri, izolare AIS | acces retras; păstrează ultimul valid |
| DE | 2 | model minim | UUID/proveniență/unități, 18 WSV separate | REST/licență se schimbă |
| BG | 3 | fixture HTML, termeni aplicați | 8 main + 12 auto, forecast 5×6, lipsă→null, schema alert | HTML neidentificabil sau metadate critice insuficiente pentru publicare |
| AT | 4 | partner key, răspuns reutilizare | list/status/forecast și datum validate | fără acces/republicare |
| SK | 5 | termeni, fixture | 13 ID-uri, nivel/temp/forecast | licență neclară persistent ori HTML instabil |
| RS | 6 | termeni, timezone | 13 ID-uri și pagini secundare validate | contract instabil/fără acord |
| HU | 7 | reguli primary/republished | 25 HU primare; externe numai validator | proveniență/licență imposibil de stabilit |
| HR | 8 | date fresh, contract oficial | endpoint documentat și date curente | rămâne stale/nedocumentat |

## Criterii transversale

- Nicio valoare lipsă transformată în zero; unitatea, timezone-ul și datum-ul sunt explicite ori `unknown`.
- Contractele minime de stație, observație și prognoză sunt verificate; sursele incomplete rămân `partial`.
- Teste offline obligatorii; live smoke cu volum mic și fără retry pe 401/403/429.
- Acceptarea juridică este separată de acceptarea tehnică.
- Orice schimbare de contract blochează doar furnizorul afectat.