# AFDJ 403 diagnostic report

Generated: `2026-08-03T18:17:40.630962+00:00`

This report is evidence-oriented. Body phrase detection is indicative and does not reveal the exact AFDJ/Cloudflare rule.

## Baseline audit

- Production workflow: `.github/workflows/update-data.yml`; run inspected: [30826804988](https://github.com/mariusbudileanu/nivel-dunare/actions/runs/30826804988).
- The production curl wire profile used `--location`, `--compressed`, `--retry 3`, `--retry-all-errors`, a 2-second retry delay, a 15-second connect timeout, and a 90-second per-attempt maximum.
- Its configured request headers were the Chrome 140 User-Agent, `Accept-Language: ro-RO,ro;q=0.9,en;q=0.8`, the AFDJ table referer, and the XML Accept value shown in `request.json`.
- No HTTP version was forced; curl negotiated its default through ALPN. Run 30826804988 did not use verbose/header capture, so its negotiated version is not demonstrated.
- Run 30826804988 logged four curl error-22 results for HTTP 403. `--fail` did not retain the error body, no header dump existed, and the workflow removed both temporary download files; only the status summary survived.
- The separate standard-library downloader in `scripts/afdj_core.py` uses three maximum attempts, a 25-second timeout, the same browser-like User-Agent plus Accept/Accept-Language/Cache-Control/Referer, default redirects, and raises a non-retryable 403 without archiving its body.

## Comparative results

| environment | operating_system | client_profile | public_ip_masked | asn | provider | resolved_server_ip | HTTP_status | HTTP_version | TLS_version | Server | CF-RAY | CF-Mitigated | CF-Cache-Status | Content-Type | body_size | body_sha256 | response_classification |
|---|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---:|---|---|
| github-macos | Darwin | playwright-chromium | 13.105.117.xxx | AS8075 | Microsoft Corporation | 172.67.190.160 | 403 | h2 | TLS 1.3 | cloudflare | a25747121dd4eaa0-DFW |  |  | text/html; charset=UTF-8 | 4902 | b92648d28b2acf1e20889b9bca0dfaab3a78ea697c730a54d005db07356998fe | cloudflare-block-page |
| github-macos | Darwin | production-profile | 13.105.117.xxx | AS8075 | Microsoft Corporation | 104.21.51.230 | 403 | 2 | TLSv1.3 | cloudflare | a25746ca4df80c24-DFW |  |  | text/html; charset=UTF-8 | 4543 | 05a2598d70b6b74840d95414bec99f618019a367265db989a9f781de5437935e | cloudflare-block-page |
| github-macos | Darwin | transparent-minimal | 13.105.117.xxx | AS8075 | Microsoft Corporation | 172.67.190.160 | 403 | 2 | TLSv1.3 | cloudflare | a25746eb8af078b7-DFW |  |  | text/html; charset=UTF-8 | 4543 | d380e85755a08a55e9a7482c1054618a9200f68306576accdca6181fce38ecbe | cloudflare-block-page |
| github-ubuntu | Linux | playwright-chromium | 4.236.159.xxx | AS8075 | Microsoft Corporation | 104.21.51.230 | 403 | h2 | TLS 1.3 | cloudflare | a257474ce97a6529-IAD |  |  | text/html; charset=UTF-8 | 4901 | ed96285bb5f6d43e5edeb42e52e20316d85b1d44157ba300c48fdf929bf3d701 | cloudflare-block-page |
| github-ubuntu | Linux | production-profile | 4.236.159.xxx | AS8075 | Microsoft Corporation | 104.21.51.230 | 403 | 2 | TLSv1.3 | cloudflare | a25747076c1d8d9b-IAD |  |  | text/html; charset=UTF-8 | 4542 | 74f5654383593dede4587d1364ecab09837d0d6a828a84decb25968616cc2259 | cloudflare-block-page |
| github-ubuntu | Linux | transparent-minimal | 4.236.159.xxx | AS8075 | Microsoft Corporation | 172.67.190.160 | 403 | 2 | TLSv1.3 | cloudflare | a25747286da1c207-IAD |  |  | text/html; charset=UTF-8 | 4542 | 70071b118226efef0373370930ff2eb09a0b78830968e5e468e008593dd96f29 | cloudflare-block-page |
| github-windows | Windows | playwright-chromium | 57.154.4.xxx | AS8075 | Microsoft Corporation | 104.21.51.230 | 403 | h2 | TLS 1.3 | cloudflare | a2574790bdab5025-LAX |  |  | text/html; charset=UTF-8 | 4899 | 1e757cafa83a390264385ddebc18f5aeabd0f942c4c7a1bc76b1f22b090052a3 | cloudflare-block-page |
| github-windows | Windows | production-profile | 57.154.4.xxx | AS8075 | Microsoft Corporation | 104.21.51.230 | 403 | 1.1 |  | cloudflare | a257473818d75025-LAX |  |  | text/html; charset=UTF-8 | 4540 | 1637afe1c5e89f9d41b937e5f5ab9545ddb1e7353a542a2df10c6bd85868ebf9 | cloudflare-block-page |
| github-windows | Windows | transparent-minimal | 57.154.4.xxx | AS8075 | Microsoft Corporation | 172.67.190.160 | 403 | 1.1 |  | cloudflare | a2574758dec4b81f-LAX |  |  | text/html; charset=UTF-8 | 4540 | 8a135d25af4dd6a4ba2f3b86d3f45657dfc395041352cecc6576f964e93ccf46 | cloudflare-block-page |
| local-windows | Windows | playwright-chromium | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | [2a06:98c1:3121::8] | 200 | h2 | TLS 1.3 | cloudflare | a25741106e87e4b9-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62541 | 9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c | xml-well-formed |
| local-windows | Windows | production-profile | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | 2a06:98c1:3120::8 | 200 | 1.1 |  | cloudflare | a257408ecc630545-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62543 | 9c86253432d07ac29f27f943cda2f8f3f4db583c78db55c6553e53e62f646edc | xml-well-formed |
| local-windows | Windows | transparent-minimal | 82.78.233.xxx | AS8708 | DIGI ROMANIA S.A. | 2a06:98c1:3120::8 | 200 | 1.1 |  | cloudflare | a25740c42af0e4b4-OTP |  | DYNAMIC | text/xml; charset=UTF-8 | 62541 | 9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c | xml-well-formed |

## Body identity and Ray IDs

- `05a2598d70b6b74840d95414bec99f618019a367265db989a9f781de5437935e`: github-macos / production-profile; CF-RAY: a25746ca4df80c24-DFW
- `1637afe1c5e89f9d41b937e5f5ab9545ddb1e7353a542a2df10c6bd85868ebf9`: github-windows / production-profile; CF-RAY: a257473818d75025-LAX
- `1e757cafa83a390264385ddebc18f5aeabd0f942c4c7a1bc76b1f22b090052a3`: github-windows / playwright-chromium; CF-RAY: a2574790bdab5025-LAX
- `70071b118226efef0373370930ff2eb09a0b78830968e5e468e008593dd96f29`: github-ubuntu / transparent-minimal; CF-RAY: a25747286da1c207-IAD
- `74f5654383593dede4587d1364ecab09837d0d6a828a84decb25968616cc2259`: github-ubuntu / production-profile; CF-RAY: a25747076c1d8d9b-IAD
- `8a135d25af4dd6a4ba2f3b86d3f45657dfc395041352cecc6576f964e93ccf46`: github-windows / transparent-minimal; CF-RAY: a2574758dec4b81f-LAX
- `9c6081bfcd62dd7f24dacdeae7c7254a3aa669cedef526312cf7de24cd25929c`: local-windows / playwright-chromium, local-windows / transparent-minimal; CF-RAY: a25740c42af0e4b4-OTP, a25741106e87e4b9-OTP
- `9c86253432d07ac29f27f943cda2f8f3f4db583c78db55c6553e53e62f646edc`: local-windows / production-profile; CF-RAY: a257408ecc630545-OTP
- `b92648d28b2acf1e20889b9bca0dfaab3a78ea697c730a54d005db07356998fe`: github-macos / playwright-chromium; CF-RAY: a25747121dd4eaa0-DFW
- `d380e85755a08a55e9a7482c1054618a9200f68306576accdca6181fce38ecbe`: github-macos / transparent-minimal; CF-RAY: a25746eb8af078b7-DFW
- `ed96285bb5f6d43e5edeb42e52e20316d85b1d44157ba300c48fdf929bf3d701`: github-ubuntu / playwright-chromium; CF-RAY: a257474ce97a6529-IAD

## Normalized block-page template comparison

This comparison replaces only the displayed Cloudflare Ray ID and displayed client IP with placeholders. Raw artifacts and exact-body hashes above remain unchanged.

- `2bce37ea0615d46c340d03cc6571ed9f72edfaf512db33cb5b3fb2c3a8c785a8`; Cloudflare beacon script: `present`; github-macos / playwright-chromium, github-ubuntu / playwright-chromium, github-windows / playwright-chromium
- `9c7b0b29b1bd39b9f5676c72e4d6168f3eed0708a73549479e5e2910ae8a0c4a`; Cloudflare beacon script: `absent`; github-macos / production-profile, github-macos / transparent-minimal, github-ubuntu / production-profile, github-ubuntu / transparent-minimal, github-windows / production-profile, github-windows / transparent-minimal

## Conclusions

### Demonstrated

- Local HTTP statuses captured: `[200, 200, 200]`.
- GitHub-hosted runner HTTP statuses captured: `[403, 403, 403, 403, 403, 403, 403, 403, 403]`.
- Every row above is backed by raw headers, `response_body.bin`, `response_full.txt`, timings, and SHA-256 files in the diagnostic artifacts.
- Observed response classifications: `['cloudflare-block-page', 'xml-well-formed']`.
- Every GitHub client/OS combination returned a Cloudflare-branded 403 block page containing `Sorry, you have been blocked` and a request-specific CF-RAY.
- `CF-Mitigated` was absent in every GitHub response. The evidence demonstrates a Cloudflare block page, not a `cf-mitigated: challenge` response.
- Advisory egress lookups identified the GitHub runner networks as: `['AS8075 / Microsoft Corporation']`; both services' raw answers remain in `network.json`.
- CF-RAY suffixes observed across the run: `['DFW', 'IAD', 'LAX']`. They are reported as observed Cloudflare colo codes without inferring the blocking rule.
- Local transparent curl and local Chromium received byte-identical XML bodies.

### Probable

- The observed difference is associated with the execution environment. IP/ASN reputation or provider classification is plausible, but not demonstrated by the HTTP response alone.

### Unknown without AFDJ/Cloudflare access

- The exact WAF rule, bot score, reputation signal, owner configuration, and corresponding Cloudflare Security Event.
- Whether a geographic, ASN, datacenter, or client rule is decisive when multiple variables differ simultaneously.

## Exact unique HTTP 403 responses


### Body SHA-256 `05a2598d70b6b74840d95414bec99f618019a367265db989a9f781de5437935e`

- Environments: github-macos / production-profile
- Size: `4543` bytes
- Decoding: `UTF-8`

#### Header variant `28d0cb9bd9ccf10d571395cd25e950816db4f367c7b9ea0ec4a43d12d5909330` — github-macos / production-profile

```http
HTTP/2 403 
date: Mon, 03 Aug 2026 18:09:59 GMT
content-type: text/html; charset=UTF-8
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
expires: Thu, 01 Jan 1970 00:00:01 GMT
referrer-policy: same-origin
x-frame-options: SAMEORIGIN
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=bXxIlUjtE%2BOPaf8TqGg%2FlnZZ428LkDlP%2B%2B8SYHhW4Wkdo2OdsoS8uYI9FWt147wb6NCEq7AqUoLps1HY3tRDp17jUWIy7%2Fr%2FfC9%2F%2BtZihb%2BhC9gGbE7tsPCYR7YHKQ%3D%3D"}]}
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
content-encoding: gzip
server: cloudflare
cf-ray: a25746ca4df80c24-DFW
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a25746ca4df80c24</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">13.105.117.182</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `1637afe1c5e89f9d41b937e5f5ab9545ddb1e7353a542a2df10c6bd85868ebf9`

- Environments: github-windows / production-profile
- Size: `4540` bytes
- Decoding: `UTF-8`

#### Header variant `2f19dcd384ff3b48c8303c890603bd290f9cf4b40fe7d0cee92ae6ccdc21aa55` — github-windows / production-profile

```http
HTTP/1.1 403 Forbidden
Date: Mon, 03 Aug 2026 18:10:16 GMT
Content-Type: text/html; charset=UTF-8
Transfer-Encoding: chunked
Connection: keep-alive
Cache-Control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
Expires: Thu, 01 Jan 1970 00:00:01 GMT
Referrer-Policy: same-origin
X-Frame-Options: SAMEORIGIN
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=IhrAmD9rmWUPy7%2BNVP0Vjp3Awl03WqNKNTLeClu28ox5T79O%2B2LYaeJ2SIU8P2PrpJ61%2F7SjzGcNl3cCuCxjCZUzYCRnKG95qAV%2FRfImr5zSKVx6YzbSxsDWFZOe9Q%3D%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Content-Encoding: gzip
Server: cloudflare
CF-RAY: a257473818d75025-LAX
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a257473818d75025</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">57.154.4.48</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `1e757cafa83a390264385ddebc18f5aeabd0f942c4c7a1bc76b1f22b090052a3`

- Environments: github-windows / playwright-chromium
- Size: `4899` bytes
- Decoding: `UTF-8`

#### Header variant `5072be137a2af0edd6c7c59e17e1395b9039ab9db2bdc5e86a6c6bee6a10d403` — github-windows / playwright-chromium

```http
HTTP/2 403
alt-svc: h3=":443"; ma=86400
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
cf-ray: a2574790bdab5025-LAX
content-encoding: zstd
content-type: text/html; charset=UTF-8
date: Mon, 03 Aug 2026 18:10:31 GMT
expires: Thu, 01 Jan 1970 00:00:01 GMT
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
referrer-policy: same-origin
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=bwWS%2Bx%2BsbtmNaSnf%2F7DblWwP1vRH7BKteOpBUA6U2%2BJ7BGAXz5ZXCnWJv4lYZHBL9SAJJgaIOH3%2FDR63KDlxn57PfqlthfUIWThrq7Xkmvsnf%2FwSPu9Y7J9k"}]}
server: cloudflare
server-timing: cfEdge;dur=4,cfOrigin;dur=0
x-frame-options: SAMEORIGIN
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a2574790bdab5025</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">57.154.4.48</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/v4513226cdae34746b4dedf0b4dfa099e1781791509496" integrity="sha512-ZE9pZaUXND66v380QUtch/5sE9tPFh2zg45pR2PB0CVkCtOREv2AJKkSidISWkysEuQ0EH8faUU5du78bx87UQ==" data-cf-beacon='{"version":"2024.11.0","token":"cd0ccc7063214c3095d4b4edd3916b50","r":1}' crossorigin="anonymous"></script>
</body>
</html>
```


### Body SHA-256 `70071b118226efef0373370930ff2eb09a0b78830968e5e468e008593dd96f29`

- Environments: github-ubuntu / transparent-minimal
- Size: `4542` bytes
- Decoding: `UTF-8`

#### Header variant `4ced8ab3d190b7b8f04a40a761eb0e3c085188c21bfe3c451259ec57a29461ce` — github-ubuntu / transparent-minimal

```http
HTTP/2 403 
date: Mon, 03 Aug 2026 18:10:14 GMT
content-type: text/html; charset=UTF-8
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
expires: Thu, 01 Jan 1970 00:00:01 GMT
referrer-policy: same-origin
x-frame-options: SAMEORIGIN
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=484nJ8lPQJtIvCuNDqUN0sDyQpy12pecxvNo2cPJaQBY5tG8m0wHj%2B58CdLoxPFjemo6Iz8OXoa6jAWlCMUYNuIMyKkvYMEnJi738psb6of2P3MVehvnkGZl"}]}
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
server: cloudflare
cf-ray: a25747286da1c207-IAD
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a25747286da1c207</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">4.236.159.151</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `74f5654383593dede4587d1364ecab09837d0d6a828a84decb25968616cc2259`

- Environments: github-ubuntu / production-profile
- Size: `4542` bytes
- Decoding: `UTF-8`

#### Header variant `d1b63b4cc9d57ebab9cedde9af2a99fc76fd2779fce59d53975e598bc5318c41` — github-ubuntu / production-profile

```http
HTTP/2 403 
date: Mon, 03 Aug 2026 18:10:09 GMT
content-type: text/html; charset=UTF-8
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
expires: Thu, 01 Jan 1970 00:00:01 GMT
referrer-policy: same-origin
x-frame-options: SAMEORIGIN
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=SeICayopdCUhBHk4OeFLxhme1pRyokTaKszwCYZ%2Flqa18zm%2FtUR6%2Bx36ZAxRAcHl%2BntbLep5sKAIVBahtpQFDHI22XD5FHR2LQryvw6P2vL1PcmBiNO%2BYfLZsPEVFA%3D%3D"}]}
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
content-encoding: zstd
server: cloudflare
cf-ray: a25747076c1d8d9b-IAD
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a25747076c1d8d9b</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">4.236.159.151</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `8a135d25af4dd6a4ba2f3b86d3f45657dfc395041352cecc6576f964e93ccf46`

- Environments: github-windows / transparent-minimal
- Size: `4540` bytes
- Decoding: `UTF-8`

#### Header variant `85c58afbb9acfdffbeeb2c0320a91c26cdbfcfd2174965a356511d7a8049157d` — github-windows / transparent-minimal

```http
HTTP/1.1 403 Forbidden
Date: Mon, 03 Aug 2026 18:10:22 GMT
Content-Type: text/html; charset=UTF-8
Transfer-Encoding: chunked
Connection: keep-alive
Cache-Control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
Expires: Thu, 01 Jan 1970 00:00:01 GMT
Referrer-Policy: same-origin
X-Frame-Options: SAMEORIGIN
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=1TNE4zm9cXhxly0dRy%2BUQCRkGr77M61KdSwDAwH0TDSY9HL9691DOS7hCtZ%2Fvv7RbTt13NSG7JXdsYQwkZSRYUylzRMwO3RvMUyuapxSgMe5qek1XaEeeI%2Bo"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Server: cloudflare
CF-RAY: a2574758dec4b81f-LAX
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a2574758dec4b81f</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">57.154.4.48</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `b92648d28b2acf1e20889b9bca0dfaab3a78ea697c730a54d005db07356998fe`

- Environments: github-macos / playwright-chromium
- Size: `4902` bytes
- Decoding: `UTF-8`

#### Header variant `ea20a597fd2d0c8e8e20821601702d1a4ba88c8c18fe9c04a306ba021f13aabb` — github-macos / playwright-chromium

```http
HTTP/2 403
alt-svc: h3=":443"; ma=86400
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
cf-ray: a25747121dd4eaa0-DFW
content-encoding: zstd
content-type: text/html; charset=UTF-8
date: Mon, 03 Aug 2026 18:10:10 GMT
expires: Thu, 01 Jan 1970 00:00:01 GMT
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
referrer-policy: same-origin
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=24cr%2Fs67PrEzCszbdmD%2Fw%2Bee%2B1jOou28h%2BOd0oRlB%2BXlV9gtRz3A0ECCrJbFL218BNX4FwmGqQBGUX%2BSlySLVBvvz0Yi%2BwwIqW06p6u1hvYpMYKNuB%2BXApHM"}]}
server: cloudflare
server-timing: cfEdge;dur=3,cfOrigin;dur=0
x-frame-options: SAMEORIGIN
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a25747121dd4eaa0</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">13.105.117.183</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/v4513226cdae34746b4dedf0b4dfa099e1781791509496" integrity="sha512-ZE9pZaUXND66v380QUtch/5sE9tPFh2zg45pR2PB0CVkCtOREv2AJKkSidISWkysEuQ0EH8faUU5du78bx87UQ==" data-cf-beacon='{"version":"2024.11.0","token":"cd0ccc7063214c3095d4b4edd3916b50","r":1}' crossorigin="anonymous"></script>
</body>
</html>
```


### Body SHA-256 `d380e85755a08a55e9a7482c1054618a9200f68306576accdca6181fce38ecbe`

- Environments: github-macos / transparent-minimal
- Size: `4543` bytes
- Decoding: `UTF-8`

#### Header variant `25a945c928614146f858be8a91e6c3234937d6475f7cd876393b6f7b363d71be` — github-macos / transparent-minimal

```http
HTTP/2 403 
date: Mon, 03 Aug 2026 18:10:04 GMT
content-type: text/html; charset=UTF-8
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
expires: Thu, 01 Jan 1970 00:00:01 GMT
referrer-policy: same-origin
x-frame-options: SAMEORIGIN
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=V4BNjUSiY0HVozT5VCeklOpQvbJOCFXdqqVGdzcX46IMA%2BV7gGc38dYgi0KXd4ccWQUi4U1A22axQNBZWz5Z98IevydlzmTaDQDRiX8kUT%2BPsSoLMn8HCd8T"}]}
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
server: cloudflare
cf-ray: a25746eb8af078b7-DFW
alt-svc: h3=":443"; ma=86400
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a25746eb8af078b7</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">13.105.117.183</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
</body>
</html>
```


### Body SHA-256 `ed96285bb5f6d43e5edeb42e52e20316d85b1d44157ba300c48fdf929bf3d701`

- Environments: github-ubuntu / playwright-chromium
- Size: `4901` bytes
- Decoding: `UTF-8`

#### Header variant `ae53a3bddfbdbb4b0ff2abc65f41484890e20e2d8c138e79f185719f8225b984` — github-ubuntu / playwright-chromium

```http
HTTP/2 403
alt-svc: h3=":443"; ma=86400
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
cf-ray: a257474ce97a6529-IAD
content-encoding: zstd
content-type: text/html; charset=UTF-8
date: Mon, 03 Aug 2026 18:10:20 GMT
expires: Thu, 01 Jan 1970 00:00:01 GMT
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
referrer-policy: same-origin
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=JUkVOpmZNPJZUtdnzsvCDHUDez%2FCSF5gnFFdy%2FWK%2Bpwo9yryH1yIgu96zDpiZ4yZ%2FOwhaVlO6aCurwDublBsl25YIoUKeKWvEBAWxUxQzYOXFnMlnZxe6Bas"}]}
server: cloudflare
server-timing: cfEdge;dur=2,cfOrigin;dur=0
x-frame-options: SAMEORIGIN
```

```html
<!DOCTYPE html>
<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->
<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->
<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!--<![endif]-->
<head>
<title>Attention Required! | Cloudflare</title>
<meta charset="UTF-8" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="X-UA-Compatible" content="IE=Edge" />
<meta name="robots" content="noindex, nofollow" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<link rel="stylesheet" id="cf_styles-css" href="/cdn-cgi/styles/cf.errors.css" />
<!--[if lt IE 9]><link rel="stylesheet" id='cf_styles-ie-css' href="/cdn-cgi/styles/cf.errors.ie.css" /><![endif]-->
<style>body{margin:0;padding:0}</style>


<!--[if gte IE 10]><!-->
<script>
  if (!navigator.cookieEnabled) {
    window.addEventListener('DOMContentLoaded', function () {
      var cookieEl = document.getElementById('cookie-alert');
      cookieEl.style.display = 'block';
    })
  }
</script>
<!--<![endif]-->

</head>
<body>
  <div id="cf-wrapper">
    <div class="cf-alert cf-alert-error cf-cookie-error" id="cookie-alert" data-translate="enable_cookies">Please enable cookies.</div>
    <div id="cf-error-details" class="cf-error-details-wrapper">
      <div class="cf-wrapper cf-header cf-error-overview">
        <h1 data-translate="block_headline">Sorry, you have been blocked</h1>
        <h2 class="cf-subheadline"><span data-translate="unable_to_access">You are unable to access</span> afdj.ro</h2>
      </div><!-- /.header -->

      <div class="cf-section cf-highlight">
        <div class="cf-wrapper">
          <div class="cf-screenshot-container cf-screenshot-full">
            
              <span class="cf-no-screenshot error"></span>
            
          </div>
        </div>
      </div><!-- /.captcha-container -->

      <div class="cf-section cf-wrapper">
        <div class="cf-columns two">
          <div class="cf-column">
            <h2 data-translate="blocked_why_headline">Why have I been blocked?</h2>

            <p data-translate="blocked_why_detail">This website is using a security service to protect itself from online attacks. The action you just performed triggered the security solution. There are several actions that could trigger this block including submitting a certain word or phrase, a SQL command or malformed data.</p>
          </div>

          <div class="cf-column">
            <h2 data-translate="blocked_resolve_headline">What can I do to resolve this?</h2>

            <p data-translate="blocked_resolve_detail">You can email the site owner to let them know you were blocked. Please include what you were doing when this page came up and the Cloudflare Ray ID found at the bottom of this page.</p>
          </div>
        </div>
      </div><!-- /.section -->

      <div class="cf-error-footer cf-wrapper w-240 lg:w-full py-10 sm:py-4 sm:px-8 mx-auto text-center sm:text-left border-solid border-0 border-t border-gray-300">
    <p class="text-13">
      <span class="cf-footer-item sm:block sm:mb-1">Cloudflare Ray ID: <strong class="font-semibold">a257474ce97a6529</strong></span>
      <span class="cf-footer-separator sm:hidden">&bull;</span>
      <span id="cf-footer-item-ip" class="cf-footer-item hidden sm:block sm:mb-1">
        Your IP:
        <button type="button" id="cf-footer-ip-reveal" class="cf-footer-ip-reveal-btn">Click to reveal</button>
        <span class="hidden" id="cf-footer-ip">4.236.159.151</span>
        <span class="cf-footer-separator sm:hidden">&bull;</span>
      </span>
      <span class="cf-footer-item sm:block sm:mb-1"><span>Performance &amp; security by</span> <a rel="noopener noreferrer" href="https://www.cloudflare.com/5xx-error-landing" id="brand_link" target="_blank">Cloudflare</a></span>
      
    </p>
    <script>(function(){function d(){var b=a.getElementById("cf-footer-item-ip"),c=a.getElementById("cf-footer-ip-reveal");b&&"classList"in b&&(b.classList.remove("hidden"),c.addEventListener("click",function(){c.classList.add("hidden");a.getElementById("cf-footer-ip").classList.remove("hidden")}))}var a=document;document.addEventListener&&a.addEventListener("DOMContentLoaded",d)})();</script>
  </div><!-- /.error-footer -->

    </div><!-- /#cf-error-details -->
  </div><!-- /#cf-wrapper -->

  <script>
    window._cf_translation = {};
    
    
  </script>
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/v4513226cdae34746b4dedf0b4dfa099e1781791509496" integrity="sha512-ZE9pZaUXND66v380QUtch/5sE9tPFh2zg45pR2PB0CVkCtOREv2AJKkSidISWkysEuQ0EH8faUU5du78bx87UQ==" data-cf-beacon='{"version":"2024.11.0","token":"cd0ccc7063214c3095d4b4edd3916b50","r":1}' crossorigin="anonymous"></script>
</body>
</html>
```


## Reproduction

```bash
python -m scripts.diagnose_afdj_access \
  --environment-label <LABEL> \
  --output-dir <DIRECTOR>
```

Return the entire output directory, including `_shared`, every profile subfolder, and `comparison_summary.json`.
