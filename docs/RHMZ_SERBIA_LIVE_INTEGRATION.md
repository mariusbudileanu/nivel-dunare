# RHMZ Serbia live integration

Date: 2026-08-06
Diagnostic workflow: `diagnose-rhmz-access.yml`
Corrected run: [31083512217](https://github.com/mariusbudileanu/nivel-dunare/actions/runs/31083512217)

## Demonstrated transport result

| Runner | Client | Hostname | DNS | HTTP | TLS result | Content type | Bytes | SHA-256 | Expected HTML table |
|---|---|---|---|---:|---|---|---:|---|---|
| `ubuntu-latest` | curl/OpenSSL | `www.hidmet.gov.rs` | `79.101.42.78` | no response | failed: `unable to get local issuer certificate` | n/a | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | no |
| `ubuntu-latest` | curl/OpenSSL | `hidmet.gov.rs` | `79.101.42.78` | no response | failed: `unable to get local issuer certificate` | n/a | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | no |
| `windows-latest` | `curl.exe`/Schannel | `www.hidmet.gov.rs` | `79.101.42.78` | 200 | success | `text/html; charset=UTF-8` | 185,985 | `45738d8b1b5d4d9ec1ed3e3736473dd41fa86ab936add356f55ea55c1622c881` | yes |
| `windows-latest` | `curl.exe`/Schannel | `hidmet.gov.rs` | `79.101.42.78` | 200 | success | `text/html; charset=UTF-8` | 185,985 | `45738d8b1b5d4d9ec1ed3e3736473dd41fa86ab936add356f55ea55c1622c881` | yes |

`Invoke-WebRequest` also returned HTTP 200 for both hostnames, with the same 185,985-byte daily document and expected table. Python `urllib` and `requests` with certifi failed on both runners with the same issuer-chain verification error. Ubuntu curl offered HTTP/2 and HTTP/1.1 but failed before HTTP negotiation. Windows Schannel negotiated HTTP/1.1.

OpenSSL received the leaf `CN=hidmet.gov.rs`, valid 2026-06-08 through 2026-09-06, and the Let's Encrypt `YR2` issuer certificate, valid 2025-09-03 through 2028-09-02, whose issuer is `ISRG Root YR`. The standard Ubuntu trust bundle did not complete that path and returned verify code 20. This evidence demonstrates a trust-path difference between the tested runners; it does not prove an RHMZ access-control rule. No supplemental CA bundle is shipped because Windows Schannel already validates the official HTTPS endpoint using the system trust store.

The earlier run `31083359590` had a diagnostic portability defect (`curl.exe` was invoked on Linux); it is retained as audit history but is not used as Ubuntu transport evidence. Commit `fc04b457caae0979e7aa575ce6869d86a5c989fe` corrected the diagnostic, and run `31083512217` completed both jobs.

## Official payloads and parser contract

All requests use `https://www.hidmet.gov.rs` and preserve URL, capture time, status, content type, encoding, raw bytes and SHA-256. The real fixture set contains 28 captured official HTML documents: daily index, NRT index, central forecast, 13 individual daily/report pages and 12 detailed NRT pages.

The adapter implements:

- daily Danube index discovery and all 13 station pages;
- NRT index discovery and 12 detailed series pages;
- central point forecast as primary evidence;
- individual `prognoza`, valid empty `bezprognoza` and non-point `opseg` range handling;
- negative levels, `*` as not published, `-` as unavailable and no missing-to-zero conversion;
- the source-declared daily time `06:00 UTC`;
- the NRT source offset, original time, normalized UTC, observed cadence and capture delay;
- stable overlap deduplication by station, stream, parameter and source observation date/time.

The first validated GitHub live capture (`period=7`) produced 13 stations, 2,309 NRT observations, 39 daily observations and 36 point forecasts. There are 12 NRT streams; Slankamen (`hm_id=42040`) remains daily-only. The observed NRT cadence in that capture was 30 minutes, 60 minutes or variable with a 30/60-minute median, depending on station. The demonstrated page selector accepts 7-day overlap and 30-day maximum backfill.

Canonical station identifiers are the official `hm_id` values:

| hm_id | Station | Primary stream |
|---:|---|---|
| 42010 | Bezdan | NRT |
| 42015 | Apatin | NRT |
| 42020 | Bogojevo | NRT |
| 42030 | Backa Palanka | NRT |
| 42035 | Novi Sad | NRT |
| 42040 | Slankamen | daily |
| 42045 | Zemun | NRT |
| 42050 | Pancevo | NRT |
| 42055 | Smederevo | NRT |
| 42060 | Banatska Palanka | NRT |
| 42065 | Veliko Gradiste | NRT |
| 42070 | Golubac | NRT |
| 42095 | Prahovo | NRT |

The existing 13 physical locations and reviewed coordinates are unchanged: 12 manually verified exact station coordinates and one accepted approximate locality coordinate. Twelve added NRT identities are data streams, not new station records or map markers.

## Persistent workflow and safety boundary

`.github/workflows/update-serbia-data.yml` uses a read-only `collect-serbia` job on `windows-latest`. `curl.exe` must report the Schannel backend. It performs standard HTTPS and hostname verification, archives raw bytes and metadata, parses candidate files and uploads an immutable artifact. A read-only Linux job downloads that artifact, validates references and the full public contract, runs repository/frontend/unit checks and creates a checksummed product. Only the final controlled Linux publisher has `contents: write`; it applies an explicit international-data whitelist and refuses concurrent international changes.

Schedules are independent of the generic daily workflow:

- NRT every three hours at minute 17;
- NRT seven-day reconciliation daily at 00:47 UTC;
- daily table via a UTC trigger pair gated to 10:20 Europe/Belgrade;
- forecast via a UTC trigger pair gated to 12:35 Europe/Belgrade.

The UTC pairs plus `Europe/Belgrade` gates are DST-safe. A manual `period=30`, `profile=all` run performs the initial maximum backfill.

RS NRT, daily and forecast keep separate component attempt/success/error/failure/transport/runner/request fields. A rejected or empty component cannot replace its last-known-good. Forecast failure does not erase NRT, NRT failure does not erase daily, and a failed collection preserves all previously validated station rows. Raw payload artifacts provide page-level evidence for diagnosis.

## Frontend activation

The branch retains the legacy suspended public snapshot until a validated post-merge live publication. After RS observations exist, source state becomes complete/available/scheduled/current with source-provisional validation. Each physical marker continues to aggregate its streams. The popup presents the latest NRT level, observed cadence, capture delay, provisional warning, daily level/discharge/temperature and point forecasts where demonstrated. RO and EN messages are exact source-policy translations; no permanent 30–60 minute claim is hardcoded.

## Repeat commands

```text
gh workflow run diagnose-rhmz-access.yml --ref fix/serbia-rhmz-live-integration
gh workflow run update-serbia-data.yml --ref main -f profile=all -f period=30 -f action=dry-run
gh workflow run update-serbia-data.yml --ref main -f profile=all -f period=30 -f action=publish
python -m unittest discover -s tests -v
python -m scripts.validate_repository
python -m scripts.validate_international_public_data
```

## Remaining limitations

- Ubuntu's tested standard OpenSSL trust store does not complete the current chain; collection remains on Windows/Schannel unless a future Linux runner demonstrates standard validation.
- RHMZ marks automatic data provisional and unvalidated; the application preserves that classification.
- Individual page failure is fail-soft through component last-known-good, but the collector intentionally does not manufacture a partial replacement from missing pages.
- Source publication timing and telemetry delay can vary; cadence and delay are derived from each capture.
