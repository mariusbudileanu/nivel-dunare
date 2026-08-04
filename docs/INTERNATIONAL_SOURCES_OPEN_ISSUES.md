# International Danube sources — open issues

Date: 2026-08-04

## Blocking publication

| Source | Demonstrated fact | Required resolution |
|---|---|---|
| viadonau AT | The implementation falls back to the public opendata test key. | Obtain a permanent DoRIS partner key and provide it as DORIS_PARTNER_KEY; do not commit it. |
| SHMÚ SK | Iža returned an official water-temperature value of 46.2 °C in the 2026-08-04 live run. | Confirm sensor/unit quality with SHMÚ; keep the adapter fail-closed while the value exceeds the configured plausible range. |
| Croatian waterways HR | The audited response's newest observation was 2026-03-12. | Confirm the intended current endpoint or restoration of feed updates with the operator. The adapter will reopen automatically only for observations no older than seven days. |
| APPD BG | Current pages expose names and river kilometres but no demonstrated stable institutional station IDs. | Obtain an official identifier registry or explicit operator confirmation. Do not promote application slugs into `source_station_id`. |
| APPD BG | The five tables visually describe forecasts, but a machine-readable parameter/unit/issue-time contract is not documented on the audited page. | Obtain official schema documentation before downstream publication. Raw `DD.MM` and table values remain reviewable. |
| Hidmet RS | Normal TLS certificate validation failed during audit. | The source owner must repair the public certificate chain, or publish a verifiable official alternative. Never bypass TLS validation. |

## Metadata gaps

- Official WGS84 coordinates are missing for one included PEGELONLINE station (`KACHLET WEHR UP`) and all audited SK, HU, HR and BG station rows.
- SHMÚ pages supply local date/time but no explicit textual timezone. The adapter uses `Europe/Bratislava` because the source is the Slovak national service; this mapping should be confirmed before publication policy is finalized.
- Croatian and Hungarian rows provide a date without a time or offset. The adapter deliberately leaves local and UTC datetimes blank.
- APPD automated direction is categorical (`up`, `down`, `nochange`), not a numeric six-hour delta.
- Hydroinfo's English forecast is narrative. No numeric forecast can be extracted from the audited page.

## Non-blocking engineering follow-up

- Obtain official test credentials for DoRIS and add a secret-backed, read-only live workflow run only after project approval.
- Request formal station metadata exports from SHMÚ, OVF, DHMZ/Croatian waterways and APPD.
- Add live-schema notification routing on the future Hetzner integration; do not weaken fail-closed validation.
- Decide retention policy for `data/archive/<source>/<year>/<month>/` before enabling any scheduler.
- Review cross-border matches manually. Republished rows are validation context, never an automatic primary-source replacement.

## Explicitly out of scope

No production schedule, systemd unit, AFDJ code, canonical/public data, frontend, Pages deploy or automatic merge is part of this implementation.
