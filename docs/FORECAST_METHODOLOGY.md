# Metodologia prognozelor

## Ediție, orizont și țintă

`forecast_issue_datetime` este momentul ediției din XML. Pentru fiecare orizont `lead_hours`, aplicația calculează `target_datetime = forecast_issue_datetime + lead_hours`. Edițiile vechi nu sunt suprascrise.

## Validarea XML–HTML și zero-ul ambiguu

Tabelul HTML este selectat după antetele semantice, nu după indecși globali. Regulile sunt:

1. XML și HTML numerice egale: prognoză validă, confirmată;
2. XML `0` și HTML gol: indisponibilă, zero ambiguu;
3. XML nonzero și HTML gol: indisponibilă, mismatch de disponibilitate;
4. valori numerice diferite: valoarea XML este păstrată ca disponibilă, dar marcată mismatch;
5. HTML neparseabil: nonzero rămâne disponibil cu avertizare, zero rămâne ambiguu și indisponibil.

La probleme, HTML-ul este arhivat comprimat în diagnostics.

## Evaluare

Prognoza este potrivită cu observația prin `station_id + target_date`. Pentru erorile `e = forecast - observed`:

- MAE = media valorilor `|e|`;
- RMSE = rădăcina mediei `e²`;
- bias = media lui `e`;
- se calculează și procentul `|e| ≤ 5`, `≤ 10`, `≤ 20` cm.

Sub 10 perechi apare „Date insuficiente”, între 10 și 29 „Rezultate preliminare”, iar de la 30 „Rezultate consolidate”. Indicatorii sunt calculați de această aplicație; nu sunt publicați de AFDJ sau INHGA.

## Limitări

Potrivirea zilnică nu substituie o evaluare hidrologică oficială. Edițiile și observațiile pot avea ore diferite, date lipsă sau corecții ulterioare, toate păstrate prin `corrections.csv`.

