# AFDJ cloud probe instructions

Acest ghid rulează același diagnostic neintruziv în alte medii. Niciun exemplu de mai jos nu a fost executat de proiect fără credențialele și infrastructura operatorului respectiv.

## Cerințe

- Python 3.12;
- `curl` disponibil în `PATH`;
- spațiu pentru artefacte;
- pentru profilul Chromium: `playwright==1.54.0`, `tzdata==2025.2` și browserul Chromium aferent.

Instalarea reproductibilă a clientului Chromium:

```bash
python -m pip install --disable-pip-version-check playwright==1.54.0 tzdata==2025.2
python -m playwright install chromium
```

Pe Linux poate fi necesar, cu privilegii adecvate:

```bash
python -m playwright install --with-deps chromium
```

Comanda de sondare este aceeași în toate mediile:

```bash
python -m scripts.diagnose_afdj_access \
  --environment-label <LABEL> \
  --output-dir <DIRECTOR>
```

Comanda execută o singură dată cele trei profiluri aprobate, cu pauze între ele. Nu folosește proxy, cookie-uri persistente, pluginuri stealth, CAPTCHA sau mecanisme de rezolvare a challenge-urilor.

## GitLab CI

Într-un job manual, după checkout și instalarea cerințelor:

```yaml
afdj-diagnostic:
  when: manual
  script:
    - python -m pip install --disable-pip-version-check playwright==1.54.0 tzdata==2025.2
    - python -m playwright install chromium
    - python -m scripts.diagnose_afdj_access --environment-label gitlab-ci --output-dir diagnostics
  artifacts:
    when: always
    paths:
      - diagnostics/
```

## Azure DevOps

Într-un stage pornit manual:

```yaml
steps:
  - checkout: self
  - script: python -m pip install --disable-pip-version-check playwright==1.54.0 tzdata==2025.2
  - script: python -m playwright install chromium
  - script: python -m scripts.diagnose_afdj_access --environment-label azure-devops --output-dir diagnostics
  - task: PublishPipelineArtifact@1
    inputs:
      targetPath: diagnostics
      artifact: afdj-diagnostic
    condition: always()
```

## VPS Linux

```bash
git clone https://github.com/mariusbudileanu/nivel-dunare.git
cd nivel-dunare
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check playwright==1.54.0 tzdata==2025.2
python -m playwright install --with-deps chromium
python -m scripts.diagnose_afdj_access --environment-label vps-linux --output-dir diagnostics
```

Nu rula comanda în cron. O singură execuție este suficientă pentru comparația inițială.

## AWS, Azure VM și Google Cloud VM

Pe o instanță temporară, după checkout și instalarea cerințelor, folosește respectiv etichete precum:

```bash
python -m scripts.diagnose_afdj_access --environment-label aws-vm --output-dir diagnostics
python -m scripts.diagnose_afdj_access --environment-label azure-vm --output-dir diagnostics
python -m scripts.diagnose_afdj_access --environment-label gcp-vm --output-dir diagnostics
```

Nu presupune că rezultatul reprezintă întregul provider. Regiunea, ASN-ul, familia IP și imaginea instanței trebuie păstrate în artefact.

## VM sau rețea din România

```bash
python -m scripts.diagnose_afdj_access --environment-label romania-vm --output-dir diagnostics
```

Eticheta trebuie să descrie mediul fără a publica adresa IP rezidențială. Într-un raport public se folosește numai `public_ip_masked`.

## Hotspot mobil

Rulează local dintr-un checkout curat, conectat la hotspot, o singură dată:

```bash
python -m scripts.diagnose_afdj_access --environment-label mobile-hotspot --output-dir diagnostics
```

Folderul poate conține IP-ul public complet și trebuie tratat ca material privat, neverificat în Git.

## Ce trebuie returnat

Returnează întregul director indicat prin `--output-dir`, fără a selecta numai fișierele rezumative. Sunt necesare:

- `_shared/`;
- toate cele trei subfoldere de profil;
- `request.json`, `environment.json`, `dns.json`, `network.json`;
- antetele, `response_body.bin` și `response_full.txt`;
- `curl_verbose.txt`, consola Chromium și request failures;
- `timings.json`, `summary.json`, `sha256.json`;
- `comparison_summary.json`;
- screenshotul, dacă profilul Chromium a întâlnit o pagină 403/challenge.

Pentru a genera un raport comparativ din mai multe directoare returnate:

```bash
python -m scripts.diagnose_afdj_access \
  --report-from <DIRECTOR_1> <DIRECTOR_2> \
  --report-output docs/AFDJ_403_DIAGNOSTIC_REPORT.md
```

Rezultatele serviciilor de geolocație/ASN sunt orientative. Ele nu demonstrează regula WAF sau motivul exact al unei blocări.