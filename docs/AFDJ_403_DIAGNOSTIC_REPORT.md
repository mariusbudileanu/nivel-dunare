# AFDJ 403 diagnostic report

Generated: `2026-08-03T18:07:59.030374+00:00`

This report is evidence-oriented. Body phrase detection is indicative and does not reveal the exact AFDJ/Cloudflare rule.

## Comparative results

| environment | operating_system | client_profile | public_ip_masked | asn | provider | resolved_server_ip | HTTP_status | HTTP_version | TLS_version | Server | CF-RAY | CF-Mitigated | CF-Cache-Status | Content-Type | body_size | body_sha256 | response_classification |
|---|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---:|---|---|
| local-windows | Windows | playwright-chromium | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | [2a06:98c1:3121::8] | 200 | h2 | TLS 1.3 | cloudflare | a25741106e87e4b9-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62541 | 9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c | xml-well-formed |
| local-windows | Windows | production-profile | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | 2a06:98c1:3120::8 | 200 | 1.1 |  | cloudflare | a257408ecc630545-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62543 | 9c86253432d07ac29f27f943cda2f8f3f4db583c78db55c6553e53e62f646edc | xml-well-formed |
| local-windows | Windows | transparent-minimal | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | 2a06:98c1:3120::8 | 200 | 1.1 |  | cloudflare | a25740c42af0e4b4-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62541 | 9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c | xml-well-formed |

## Body identity and Ray IDs

- `9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c`: local-windows / playwright-chromium, local-windows / transparent-minimal; CF-RAY: a25740c42af0e4b4-OTP, a25741106e87e4b9-OTP
- `9c86253432d07ac29f27f943cda2f8f3f4db583c78db55c6553e53e62f646edc`: local-windows / production-profile; CF-RAY: a257408ecc630545-OTP

## Conclusions

### Demonstrated

- Local HTTP statuses captured: `[200, 200, 200]`.
- Every row above is backed by raw headers, `response_body.bin`, `response_full.txt`, timings, and SHA-256 files in the diagnostic artifacts.
- Observed response classifications: `['xml-well-formed']`.

### Probable

- Any association with IP/ASN, client fingerprint, geography, or provider remains a hypothesis unless the comparative rows isolate that variable.

### Unknown without AFDJ/Cloudflare access

- The exact WAF rule, bot score, reputation signal, owner configuration, and corresponding Cloudflare Security Event.
- Whether a geographic, ASN, datacenter, or client rule is decisive when multiple variables differ simultaneously.

## Exact unique HTTP 403 responses

No HTTP 403 body was present in the supplied artifacts.

## Reproduction

```bash
python -m scripts.diagnose_afdj_access \
  --environment-label <LABEL> \
  --output-dir <DIRECTOR>
```

Return the entire output directory, including `_shared`, every profile subfolder, and `comparison_summary.json`.
