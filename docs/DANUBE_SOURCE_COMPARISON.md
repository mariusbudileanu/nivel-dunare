# Comparația surselor Dunării

Scorurile 1–5 sunt orientative la 2026-08-04. Pentru `Effort`, 5 înseamnă efort mic; pentru celelalte, 5 este favorabil. Clasele sunt per endpoint/canal, nu etichete exclusive ale furnizorului.

| Sursă | Clasă | API maturity | Completeness | Metadata | Legal clarity | Reliability | Effort | Production suitability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PEGELONLINE DE | A/G | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| DoRIS AT | A | 5 | 4 | 5 | 3 | 4 | 4 | 4 |
| SHMÚ SK | C | 2 | 3 | 2 | 1 | 3 | 2 | 2 |
| Hydroinfo HU | C/G | 2 | 4 | 2 | 1 | 3 | 3 | 2 |
| Vodni Putovi HR | D | 1 | 2 | 1 | 1 | 1 | 2 | 1 |
| RHMZ RS | C | 2 | 4 | 2 | 1 | 3 | 2 | 2 |
| APPD BG curent/prognoză/arhivă | C/C/E | 2 | 4 | 3 | 5 | 3 | 2 | 3 |
| AFDJ RO | B | 3 | 4 | 3 | 1 | 3* | 4 | 4* |

`*` AFDJ este potrivit prin Hetzner, nu din GitHub-hosted runners.

## Justificare APPD

- Hidrologia curentă este HTML semantic server-rendered, UTF-8: 8 stații principale și 12 automate, cu km și ediție datată. Contractul este neversionat, deci clasa C și `partial`, nu API.
- Prognozele sunt HTML semantic cu 5 stații și câte 6 zile, min/central/max. Nu sunt demonstrate data ediției, unitatea, referința sau identificatorii stațiilor; clasa C, adaptor `partial`.
- Open Data este index documentar cu 55 linkuri PDF și 6 stații istorice: clasa E. Nu este combinat conceptual cu paginile curente.
- Termenii oficiali cer atribuirea EAEMDR și indicarea transformărilor, perioadei și domeniului, ceea ce crește claritatea juridică față de auditul anterior.

## Matrice funcțională

| Sursă | Curent | Istoric | Prognoză | Debit | Temperatură | Variație | Coordonate | km | Gauge zero/datum | Timp declarat |
|---|---|---|---|---|---|---|---|---|---|---|
| DE | yes | yes | partial | partial | partial | calculabil | yes | yes | yes | CET caveat/download |
| AT | yes | yes | yes | unknown | unknown | yes | yes | yes | yes/Adriatic | timestamp în răspuns |
| SK | yes | unknown | 48 h | unknown | yes | partial | unknown | unknown | unknown | local/nespecificat |
| HU | yes | partial | 6 zile | yes | yes | yes | unknown | unknown | unknown | momente în antet |
| HR | stale | 10 valori | pagina descrie 5 zile | no demonstrat | no demonstrat | calculabil | unknown | partial | datum unknown | date fără zonă |
| RS | yes | 30 zile/anual | 2–4 zile | yes | yes | calculabil | unknown | unknown | unknown | nespecificat |
| BG | yes, 8+12 | PDF 2020–2025 + istoric | 5 stații × 6 zile, min/central/max | main: 6 valori + 2 blank | main+auto | 24 h numeric; auto 6 h categoric | unknown | yes | unknown | ediție current; forecast target DD.MM |
| RO | yes | arhivă proiect | 24–120 h | no | yes | yes | yes | yes | no | date separate în XML |

Pentru BG, celula goală de debit este `null`, nu zero. Forecastul păstrează unitatea, parametrul și anul țintei ca indisponibile până la clarificare; nu se presupune `cm` doar din context.

## Operațional

| Sursă | GitHub | Hetzner | Local | Schimbare | Implementare |
|---|---|---|---|---|---|
| RO | 403 | 200 | 200 XML | medie | pipeline existent imediat; adaptor numai după paritate |
| DE | not-tested | not-tested | 200 JSON | scăzută REST | primul adaptor API nou |
| BG | not-tested | not-tested | 200 HTML UTF-8 | mediu-ridicată | parser conservator + fixtures + schema alert |
| AT | not-tested | not-tested | 200 cu test key; 403 fără | medie | după cheie permanentă/acord |
| SK | not-tested | not-tested | 200 HTML | mediu-ridicată | parser HTML cu fixture |
| RS | not-tested | not-tested | 200 HTML | mediu-ridicată | parsere per pagină |
| HU | not-tested | not-tested | 200 HTML | mediu-ridicată | HU primary + validator extern |
| HR | not-tested | not-tested | 200 JSON stale | ridicată | suspendat |

## Ordine finală

1. RO AFDJ: automatizare imediată Hetzner, fără refactor disruptiv.
2. DE PEGELONLINE.
3. BG APPD.
4. AT DoRIS după partner key și clarificare.
5. SK SHMÚ.
6. RS RHMZ.
7. HU Hydroinfo numai HU primary și validator pentru externe.
8. HR suspendată.