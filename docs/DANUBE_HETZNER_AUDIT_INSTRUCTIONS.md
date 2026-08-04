# Instrucțiuni de audit pe Hetzner

Aceste comenzi rulează probe read-only într-un output separat. Nu configurează systemd, nu fac push și nu accesează `/home/marius/ais-blacksea`.

## Verificări înainte

```bash
sudo systemctl is-active ais-blacksea
free -h
df -h /
cd /home/marius/nivel-dunare
git status --short
```

`sudo` este folosit numai pentru citirea statusului serviciului. Oprește auditul dacă AIS nu este `active` sau dacă resursele sunt insuficiente; nu modifica serviciul.

## HTTP simplu

Folosește venv-ul proiectului și un director nou:

```bash
cd /home/marius/nivel-dunare
python3 -m venv .venv-audit
. .venv-audit/bin/activate
python -m scripts.audit_danube_sources --source de --http-only --max-requests 2 --output-dir /home/marius/danube-audit/de-$(date -u +%Y%m%dT%H%M%SZ)
python -m scripts.audit_danube_sources --all --http-only --max-requests 12 --output-dir /home/marius/danube-audit/all-$(date -u +%Y%m%dT%H%M%SZ)
```

Scriptul preferă `curl` dacă există și cade controlat pe biblioteca standard. Nu instala nimic pentru auditul HTTP dacă Python/curl sunt deja prezente. Nu repeta un 401/403/429.

## Browser opțional

Instalează Playwright numai în venv-ul de audit și numai dacă este aprobat consumul de spațiu. Chromium este o navigare diagnostică, nu un mecanism de ingestie:

```bash
. /home/marius/nivel-dunare/.venv-audit/bin/activate
python -m pip install 'playwright==1.54.0'
python -m playwright install chromium
python -m scripts.audit_danube_sources --source hr --browser --max-requests 2 --output-dir /home/marius/danube-audit/hr-browser-$(date -u +%Y%m%dT%H%M%SZ)
```

Nu instala dependențe de sistem cu root fără aprobare explicită. Fără stealth, proxy, profil persistent sau cookie-uri.

## Raport din probe existente

```bash
python -m scripts.audit_danube_sources --report-from /home/marius/danube-audit/NUME_RUN --report-output /home/marius/danube-audit/NUME_RUN/comparison/report.md
sha256sum /home/marius/danube-audit/NUME_RUN/*/response_body.bin
```

Returnează întregul folder al runului printr-un canal sigur; înainte de publicare verifică mascarea IP-urilor și absența cookie-urilor/secretelor. Nu copia raw-ul în Git.

## Verificări după

```bash
sudo systemctl is-active ais-blacksea
free -h
df -h /
cd /home/marius/nivel-dunare
git status --short
```

Criteriu: AIS rămâne `active`, worktree-ul nu s-a schimbat, iar fiecare țară are `summary.json`, `raw_sha256.json` și corpul brut. Compară status, content-type, dimensiune și SHA cu proba locală; diferența de hash la date live este normală și trebuie explicată prin timestamp/conținut, nu considerată automat eroare.